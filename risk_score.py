#!/usr/bin/env python3
"""台股大盤風險分數：10（最低風險）到 100（最高風險）。"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean, pstdev


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def to_risk_score(safety_score: float) -> float:
    """將原始風險分整體加10分，並將最高值限制在100分。"""
    return clamp(110 - safety_score, 10, 100)


def lerp(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x <= x0:
        return y0
    if x >= x1:
        return y1
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


def pct_change(current: float, previous: float) -> float:
    return 0.0 if previous == 0 else (current / previous - 1.0) * 100.0


@dataclass
class Score:
    date: str
    total: float
    risk_level: str
    technical: float
    volume: float
    margin: float
    institutional: float
    metrics: dict[str, float]


REQUIRED = {
    "date", "close", "volume", "margin_balance", "turnover_value",
    "foreign_net", "investment_trust_net", "dealer_net",
}
OPTIONAL = {"margin_maintenance_pct", "margin_top10_concentration_pct",
            "margin_hhi", "margin_top3_industry_concentration_pct",
            "short_margin_ratio_pct", "high_margin_cap_exposure_pct"}


def load_csv(path: Path) -> list[dict[str, float | str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV 缺少欄位: {', '.join(sorted(missing))}")
        rows = []
        for raw in reader:
            keys = REQUIRED | (OPTIONAL & set(raw))
            rows.append({k: (raw[k] if k == "date" else float(raw[k] or 0)) for k in keys})
    rows.sort(key=lambda row: str(row["date"]))
    if len(rows) < 120:
        raise ValueError("至少需要 120 個交易日，才能計算半年線")
    return rows


def technical_components(close: float, ma20: float, ma60: float, ma120: float,
                         ma60_slope_20d: float, return_20d: float,
                         drawdown_60d: float) -> dict[str, float]:
    """技術風險四因子，各分數皆為 0（高風險）至 100（低風險）。"""
    distance = pct_change(close, ma60)
    if distance < -5:
        position = lerp(distance, -12, -5, 5, 40)
    elif distance <= 0:
        position = lerp(distance, -5, 0, 40, 65)
    elif distance <= 5:
        position = lerp(distance, 0, 5, 68, 90)
    else:
        position = lerp(distance, 5, 15, 90, 45)

    trend = (25 if close > ma20 else 0) + (25 if ma20 > ma60 else 0)
    trend += (25 if ma60 > ma120 else 0) + (25 if ma60_slope_20d > 0 else 0)

    if return_20d < 0:
        momentum = lerp(return_20d, -15, 0, 10, 60)
    elif return_20d <= 8:
        momentum = lerp(return_20d, 0, 8, 60, 90)
    else:
        momentum = lerp(return_20d, 8, 20, 90, 45)  # 急漲過熱

    # drawdown_60d 為負數：0~-5% 健康，低於 -10% 明顯轉弱。
    if drawdown_60d >= -5:
        drawdown = lerp(drawdown_60d, -5, 0, 75, 95)
    elif drawdown_60d >= -10:
        drawdown = lerp(drawdown_60d, -10, -5, 45, 75)
    else:
        drawdown = lerp(drawdown_60d, -25, -10, 5, 45)
    return {"position": clamp(position), "trend": clamp(trend),
            "momentum": clamp(momentum), "drawdown": clamp(drawdown)}


def technical_score(close: float, ma20: float, ma60: float, ma120: float,
                    ma60_slope_20d: float, return_20d: float,
                    drawdown_60d: float, recent_distances: list[float],
                    return_3d: float = 0.0, decline_streak: int = 0) -> float:
    parts = technical_components(close, ma20, ma60, ma120, ma60_slope_20d,
                                 return_20d, drawdown_60d)
    score = (parts["position"] * .35 + parts["trend"] * .30 +
             parts["momentum"] * .15 + parts["drawdown"] * .20)
    # 極端乖離（相對近 60 日分布）加上溫和扣分。
    if len(recent_distances) >= 20:
        sigma = pstdev(recent_distances)
        if sigma > 0:
            distance = pct_change(close, ma60)
            z = (distance - fmean(recent_distances)) / sigma
            score -= max(0.0, abs(z) - 2.0) * 5.0
    # 月線下方的短期回落不能因20日比較基期移動而被判定為改善。
    if close < ma20 and return_3d < -1:
        score -= min(8.0, abs(return_3d) * 1.5)
    if close < ma20 and decline_streak >= 2:
        score -= min(6.0, (decline_streak - 1) * 2.0)
    return clamp(score)


def volume_components(volume_ratio: float, daily_return: float, margin_3d: float,
                      previous_day_ratio: float = 1.0,
                      volume_cv20: float = 0.2,
                      price_below_ma20: bool = False,
                      return_3d: float = 0.0) -> dict[str, float]:
    # 量能常態：0.8~1.2 倍最佳，極度量縮或爆量皆降低安全分。
    if volume_ratio < .8:
        normality = lerp(volume_ratio, .4, .8, 20, 70)
    elif volume_ratio <= 1.2:
        normality = lerp(volume_ratio, .8, 1.2, 72, 85)
    elif volume_ratio <= 1.5:
        normality = lerp(volume_ratio, 1.2, 1.5, 82, 65)
    else:
        normality = lerp(volume_ratio, 1.5, 2.2, 60, 25)

    # 價量確認：急跌爆量偏危險；急漲量縮或融資追價也扣分。
    if daily_return >= 1.5:
        if volume_ratio < .8:
            confirmation = 30
        elif volume_ratio > 1.5 and margin_3d > 3:
            confirmation = 20
        elif volume_ratio <= 1.5:
            confirmation = 78
        else:
            confirmation = 58
    elif daily_return <= -1.5:
        if volume_ratio > 1.2:
            confirmation = 22
        elif volume_ratio < .8:
            confirmation = 38
        else:
            confirmation = 48
    elif abs(daily_return) <= .5:
        confirmation = 82 if .7 <= volume_ratio <= 1.3 else 52
    else:
        confirmation = 68 if .8 <= volume_ratio <= 1.3 else 55
    # 指數位於月線下且近3日回落時，量比低於0.8代表承接不足，不視為平穩量縮。
    if price_below_ma20 and return_3d < -1 and volume_ratio < .8:
        confirmation = min(confirmation, 42)

    if previous_day_ratio < .6:
        day_comparison = lerp(previous_day_ratio, .3, .6, 25, 55)
    elif previous_day_ratio <= 1.3:
        day_comparison = lerp(previous_day_ratio, .6, 1.0, 60, 82) if previous_day_ratio <= 1 else lerp(previous_day_ratio, 1, 1.3, 82, 68)
    else:
        day_comparison = lerp(previous_day_ratio, 1.3, 2.0, 65, 25)

    if volume_cv20 <= .2:
        stability = 85
    elif volume_cv20 <= .4:
        stability = lerp(volume_cv20, .2, .4, 85, 65)
    elif volume_cv20 <= .7:
        stability = lerp(volume_cv20, .4, .7, 65, 35)
    else:
        stability = 25
    return {"normality": clamp(normality), "confirmation": clamp(confirmation),
            "day_comparison": clamp(day_comparison), "stability": clamp(stability)}


def volume_score(volume_ratio: float, daily_return: float, margin_3d: float,
                 previous_day_ratio: float = 1.0,
                 volume_cv20: float = .2,
                 price_below_ma20: bool = False,
                 return_3d: float = 0.0) -> float:
    parts = volume_components(volume_ratio, daily_return, margin_3d,
                              previous_day_ratio, volume_cv20,
                              price_below_ma20, return_3d)
    return clamp(parts["normality"] * .40 + parts["confirmation"] * .35 +
                 parts["day_comparison"] * .10 + parts["stability"] * .15)


def margin_maintenance_score(maintenance_pct: float) -> float:
    """市場加權維持率分數；130% 為法規追繳警戒線。"""
    if maintenance_pct < 130:
        return lerp(maintenance_pct, 100, 130, 0, 15)
    if maintenance_pct < 150:
        return lerp(maintenance_pct, 130, 150, 15, 40)
    if maintenance_pct < 160:
        return lerp(maintenance_pct, 150, 160, 40, 60)
    if maintenance_pct < 170:
        return lerp(maintenance_pct, 160, 170, 60, 75)
    if maintenance_pct < 180:
        return lerp(maintenance_pct, 170, 180, 75, 90)
    return lerp(maintenance_pct, 180, 200, 90, 100)


def margin_structure_score(top10_pct: float, hhi: float, top3_industry_pct: float,
                           short_margin_ratio_pct: float,
                           high_cap_exposure_pct: float) -> float:
    top10 = lerp(top10_pct, 20, 60, 92, 25)
    hhi_score = lerp(hhi, 80, 500, 92, 25)
    industry = lerp(top3_industry_pct, 35, 75, 90, 30)
    high_cap = lerp(high_cap_exposure_pct, 3, 30, 92, 25)
    if short_margin_ratio_pct <= 20:
        balance = 80
    elif short_margin_ratio_pct <= 30:
        balance = lerp(short_margin_ratio_pct, 20, 30, 80, 60)
    else:
        balance = lerp(short_margin_ratio_pct, 30, 60, 60, 20)
    return clamp(top10 * .35 + hhi_score * .15 + industry * .20 +
                 high_cap * .20 + balance * .10)


def margin_score(change_3d: float, change_5d: float, change_20d: float,
                 daily_return: float, distance_ma60: float,
                 maintenance_pct: float = 0.0, return_20d: float = 0.0,
                 change_streak: int = 0, margin_vs_ma20_pct: float = 0.0,
                 excess_growth_20d: float = 0.0,
                 structure_score: float = 0.0) -> float:
    if change_3d < -3:
        # 跌勢中急減偏向斷頭／停損；反彈中急減才是健康去槓桿。
        score = 38 if daily_return < 0 and return_20d < 0 else 90
        if daily_return > 0:
            score += 5
    elif change_3d <= 3:
        score = 70 - change_3d * 2
    else:
        score = 40 - min(15, (change_3d - 3) * 3)
        if change_3d > 5 and distance_ma60 >= -5:
            score -= 10
    if change_20d > 10:
        score -= 10
    elif change_20d < -10:
        score += 5
    if change_5d > 5:
        score -= 5
    if change_streak >= 5:
        score -= min(15, (change_streak - 4) * 2.5)
    elif change_streak <= -5:
        score += 5 if return_20d >= 0 else -10
    if margin_vs_ma20_pct > 5:
        score -= min(10, margin_vs_ma20_pct - 5)
    if excess_growth_20d > 5:
        score -= min(15, (excess_growth_20d - 5) * 1.5)
    change_score = clamp(score)
    if maintenance_pct <= 0:
        return change_score
    maintenance = margin_maintenance_score(maintenance_pct)
    if structure_score > 0:
        return clamp(change_score * .50 + maintenance * .30 + structure_score * .20)
    return clamp(change_score * .625 + maintenance * .375)


def institutional_score(foreign_ratio: float, trust_ratio: float,
                        dealer_ratio: float, total_ratio: float,
                        total_streak: int, volume_ratio: float,
                        strength_20d_z: float = 0.0,
                        strength_5d_z: float = 0.0,
                        previous_foreign_ratio: float = 0.0,
                        previous_trust_ratio: float = 0.0,
                        previous_dealer_ratio: float = 0.0) -> float:
    # 外資方向權重最高；各比率皆為買賣超／成交值（%）。
    directional = 0.60 * foreign_ratio + 0.25 * trust_ratio + 0.15 * dealer_ratio
    score = lerp(directional, -5, 5, 35, 90)
    if abs(total_ratio) <= 2:
        score = 70 + directional * 2
    # 短線 5 日占 40%、中期 20 日占 60%，合計最多影響 ±18 分。
    combined_strength = strength_5d_z * 0.40 + strength_20d_z * 0.60
    score += max(-3.0, min(3.0, combined_strength)) * 6.0
    # 籌碼方向翻轉：賣轉買提高安全分、買轉賣降低安全分。
    # 以外資／投信／自營商 60%／25%／15% 加權；占成交值不足0.05%視為雜訊。
    reversal_adjustment = 0.0
    for current, previous, weight in (
        (foreign_ratio, previous_foreign_ratio, .60),
        (trust_ratio, previous_trust_ratio, .25),
        (dealer_ratio, previous_dealer_ratio, .15),
    ):
        if abs(current) < .05 or abs(previous) < .05 or current * previous >= 0:
            continue
        strength = lerp(abs(current), .05, 2.0, .25, 1.0)
        reversal_adjustment += (1 if current > 0 else -1) * 12 * weight * strength
    score += reversal_adjustment
    if total_ratio > 5 and total_streak >= 3:
        score = max(score, 88)
    elif total_ratio < -5 and total_streak <= -3:
        score = min(score, 40)
    if trust_ratio > 0 and foreign_ratio < 0 and volume_ratio < 0.8:
        score = min(score, 72)  # 投信承接不抵銷外資量縮賣壓
    return clamp(score)


def classify(total: float) -> str:
    if total >= 80:
        return "高風險"
    if total >= 60:
        return "中高風險"
    if total >= 40:
        return "中低風險"
    return "低風險"


def calculate(rows: list[dict[str, float | str]]) -> Score:
    i = len(rows) - 1
    row = rows[i]
    closes = [float(r["close"]) for r in rows]
    share_volumes = [float(r["volume"]) for r in rows]
    turnover_values = [float(r["turnover_value"]) for r in rows]
    margins = [float(r["margin_balance"]) for r in rows]
    close = closes[i]
    ma20, ma60, ma120 = fmean(closes[-20:]), fmean(closes[-60:]), fmean(closes[-120:])
    prior_ma60 = fmean(closes[-80:-20])
    ma60_slope_20d = pct_change(ma60, prior_ma60)
    return_20d = pct_change(close, closes[i - 20])
    drawdown_60d = pct_change(close, max(closes[-60:]))
    avg_turnover5, avg_turnover20 = (fmean(turnover_values[-5:]),
                                    fmean(turnover_values[-20:]))
    volume_ratio5 = turnover_values[i] / avg_turnover5 if avg_turnover5 else 0
    volume_ratio_previous_day = (turnover_values[i] / turnover_values[i - 1]
                                 if turnover_values[i - 1] else 0)
    volume_ratio = turnover_values[i] / avg_turnover20 if avg_turnover20 else 0
    volume_cv20 = (pstdev(turnover_values[-20:]) / avg_turnover20
                   if avg_turnover20 else 0)
    daily_return = pct_change(close, closes[i - 1])
    return_3d = pct_change(close, closes[i - 3])
    decline_streak = 0
    for end in range(i, 0, -1):
        if closes[end] >= closes[end - 1]:
            break
        decline_streak += 1
    margin_3d = pct_change(margins[i], margins[i - 3])
    margin_5d = pct_change(margins[i], margins[i - 5])
    margin_20d = pct_change(margins[i], margins[i - 20])
    margin_ma20 = fmean(margins[-20:])
    margin_vs_ma20 = pct_change(margins[i], margin_ma20)
    margin_excess_growth_20d = margin_20d - return_20d
    last_direction = 1 if margins[i] > margins[i - 1] else -1 if margins[i] < margins[i - 1] else 0
    margin_change_streak = 0
    if last_direction:
        for end in range(i, 0, -1):
            direction = 1 if margins[end] > margins[end - 1] else -1 if margins[end] < margins[end - 1] else 0
            if direction != last_direction:
                break
            margin_change_streak += last_direction
    distance_ma60 = pct_change(close, ma60)
    estimated_margin_maintenance = float(row.get("margin_maintenance_pct", 0.0))
    structure_values = {key: float(row.get(key, 0.0)) for key in
                        ("margin_top10_concentration_pct", "margin_hhi",
                         "margin_top3_industry_concentration_pct",
                         "short_margin_ratio_pct", "high_margin_cap_exposure_pct")}
    has_structure = all(value > 0 for value in structure_values.values())
    current_structure_score = (margin_structure_score(
        structure_values["margin_top10_concentration_pct"], structure_values["margin_hhi"],
        structure_values["margin_top3_industry_concentration_pct"],
        structure_values["short_margin_ratio_pct"],
        structure_values["high_margin_cap_exposure_pct"]
    ) if has_structure else 0.0)
    current_margin_speed_score = margin_score(
        margin_3d, margin_5d, margin_20d, daily_return, distance_ma60, 0.0,
        return_20d, margin_change_streak, margin_vs_ma20,
        margin_excess_growth_20d, 0.0)
    distances = []
    for end in range(max(59, i - 59), i + 1):
        local_ma = fmean(closes[end - 59:end + 1])
        distances.append(pct_change(closes[end], local_ma))
    technical_parts = technical_components(close, ma20, ma60, ma120,
                                           ma60_slope_20d, return_20d, drawdown_60d)
    volume_parts = volume_components(volume_ratio, daily_return, margin_3d,
                                     volume_ratio_previous_day, volume_cv20,
                                     close < ma20, return_3d)

    turnover = float(row["turnover_value"])
    ratios = {
        key: (float(row[key]) / turnover * 100 if turnover else 0.0)
        for key in ("foreign_net", "investment_trust_net", "dealer_net")
    }
    previous_row = rows[i - 1]
    previous_turnover = float(previous_row["turnover_value"])
    previous_ratios = {
        key: (float(previous_row[key]) / previous_turnover * 100
              if previous_turnover else 0.0)
        for key in ("foreign_net", "investment_trust_net", "dealer_net")
    }
    total_ratio = sum(ratios.values())
    prior_institutional_ratios = []
    for prior in rows[max(0, i - 20):i]:
        prior_turnover = float(prior["turnover_value"])
        prior_net = sum(float(prior[k]) for k in
                        ("foreign_net", "investment_trust_net", "dealer_net"))
        prior_institutional_ratios.append(
            prior_net / prior_turnover * 100 if prior_turnover else 0.0)
    prior_20d_mean = fmean(prior_institutional_ratios)
    prior_20d_sigma = pstdev(prior_institutional_ratios)
    institutional_strength_20d_z = ((total_ratio - prior_20d_mean) / prior_20d_sigma
                                    if prior_20d_sigma > 0 else 0.0)
    prior_5d = prior_institutional_ratios[-5:]
    prior_5d_mean = fmean(prior_5d)
    prior_5d_sigma = pstdev(prior_5d)
    institutional_strength_5d_z = ((total_ratio - prior_5d_mean) / prior_5d_sigma
                                   if prior_5d_sigma > 0 else 0.0)
    institutional_strength_combined_z = (institutional_strength_5d_z * 0.40 +
                                         institutional_strength_20d_z * 0.60)
    signs = []
    for r in reversed(rows):
        net = sum(float(r[k]) for k in ("foreign_net", "investment_trust_net", "dealer_net"))
        signs.append(1 if net > 0 else -1 if net < 0 else 0)
        if len(signs) > 1 and signs[-1] != signs[0]:
            break
    streak = signs[0] * (len(signs) - (1 if len(signs) > 1 and signs[-1] != signs[0] else 0))

    # 各因子函式沿用既有「安全分」規則，統一在輸出邊界反轉為風險分。
    safety_scores = {
        "technical": technical_score(close, ma20, ma60, ma120, ma60_slope_20d,
                                     return_20d, drawdown_60d, distances,
                                     return_3d, decline_streak),
        "volume": volume_score(volume_ratio, daily_return, margin_3d,
                               volume_ratio_previous_day, volume_cv20,
                               close < ma20, return_3d),
        "margin": margin_score(margin_3d, margin_5d, margin_20d, daily_return,
                               distance_ma60, estimated_margin_maintenance, return_20d,
                               margin_change_streak, margin_vs_ma20,
                               margin_excess_growth_20d, current_structure_score),
        "institutional": institutional_score(
            ratios["foreign_net"], ratios["investment_trust_net"], ratios["dealer_net"],
            total_ratio, streak, volume_ratio, institutional_strength_20d_z,
            institutional_strength_5d_z, previous_ratios["foreign_net"],
            previous_ratios["investment_trust_net"], previous_ratios["dealer_net"]),
    }
    scores = {key: to_risk_score(value) for key, value in safety_scores.items()}
    total = fmean(scores.values())
    metrics = {"close": close, "ma20": ma20, "ma60": ma60, "ma120": ma120,
               "distance_ma60_pct": distance_ma60,
               "volume": share_volumes[i],
               "turnover_value": turnover_values[i],
               "avg_turnover_value_5d": avg_turnover5,
               "volume_ratio_previous_day": volume_ratio_previous_day,
               "volume_ratio_5d": volume_ratio5, "volume_ratio_20d": volume_ratio,
               "volume_cv_20d": volume_cv20,
               "volume_normality_score": to_risk_score(volume_parts["normality"]),
               "volume_confirmation_score": to_risk_score(volume_parts["confirmation"]),
               "volume_day_comparison_score": to_risk_score(volume_parts["day_comparison"]),
               "volume_stability_score": to_risk_score(volume_parts["stability"]),
               "ma60_slope_20d_pct": ma60_slope_20d,
               "return_3d_pct": return_3d,
               "decline_streak": float(decline_streak),
               "return_20d_pct": return_20d, "drawdown_60d_pct": drawdown_60d,
               "technical_position_score": to_risk_score(technical_parts["position"]),
               "technical_trend_score": to_risk_score(technical_parts["trend"]),
               "technical_momentum_score": to_risk_score(technical_parts["momentum"]),
               "technical_drawdown_score": to_risk_score(technical_parts["drawdown"]),
               "daily_return_pct": daily_return, "margin_change_3d_pct": margin_3d,
               "margin_change_5d_pct": margin_5d, "margin_change_20d_pct": margin_20d,
               "margin_change_streak": float(margin_change_streak),
               "margin_vs_ma20_pct": margin_vs_ma20,
               "margin_excess_growth_20d_pct": margin_excess_growth_20d,
               "margin_speed_score": to_risk_score(current_margin_speed_score),
               "estimated_margin_maintenance_pct": estimated_margin_maintenance,
               "margin_maintenance_score": (to_risk_score(margin_maintenance_score(estimated_margin_maintenance))
                                            if estimated_margin_maintenance > 0 else 0.0),
               "margin_structure_score": (to_risk_score(current_structure_score)
                                            if current_structure_score > 0 else 0.0),
               **structure_values,
               "institutional_net_ratio_pct": total_ratio,
               "foreign_net_ratio_pct": ratios["foreign_net"],
               "investment_trust_net_ratio_pct": ratios["investment_trust_net"],
               "dealer_net_ratio_pct": ratios["dealer_net"],
               "previous_foreign_net_ratio_pct": previous_ratios["foreign_net"],
               "previous_investment_trust_net_ratio_pct": previous_ratios["investment_trust_net"],
               "previous_dealer_net_ratio_pct": previous_ratios["dealer_net"],
               "foreign_reversal": (1.0 if ratios["foreign_net"] > .05
                                    and previous_ratios["foreign_net"] < -.05 else
                                    -1.0 if ratios["foreign_net"] < -.05
                                    and previous_ratios["foreign_net"] > .05 else 0.0),
               "investment_trust_reversal": (
                   1.0 if ratios["investment_trust_net"] > .05
                   and previous_ratios["investment_trust_net"] < -.05 else
                   -1.0 if ratios["investment_trust_net"] < -.05
                   and previous_ratios["investment_trust_net"] > .05 else 0.0),
               "dealer_reversal": (1.0 if ratios["dealer_net"] > .05
                                   and previous_ratios["dealer_net"] < -.05 else
                                   -1.0 if ratios["dealer_net"] < -.05
                                   and previous_ratios["dealer_net"] > .05 else 0.0),
               "institutional_5d_avg_ratio_pct": prior_5d_mean,
               "institutional_20d_avg_ratio_pct": prior_20d_mean,
               "institutional_strength_5d_z": institutional_strength_5d_z,
               "institutional_strength_20d_z": institutional_strength_20d_z,
               "institutional_strength_combined_z": institutional_strength_combined_z,
               "institutional_streak": float(streak)}
    return Score(str(row["date"]), round(total, 1), classify(total),
                 *(round(scores[k], 1) for k in ("technical", "volume", "margin", "institutional")),
                 {k: round(v, 4) for k, v in metrics.items()})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, help="每日大盤 CSV")
    parser.add_argument("--json", action="store_true", help="輸出 JSON")
    args = parser.parse_args()
    result = calculate(load_csv(args.csv))
    if args.json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    else:
        print(f"{result.date} 風險分數：{result.total:.1f}/100（{result.risk_level}）")
        print(f"技術 {result.technical:.1f}｜量能 {result.volume:.1f}｜融資 {result.margin:.1f}｜法人 {result.institutional:.1f}")


if __name__ == "__main__":
    main()
