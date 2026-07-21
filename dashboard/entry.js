const $=s=>document.querySelector(s),fmt=(n,d=2)=>Number(n).toLocaleString('zh-TW',{maximumFractionDigits:d}),signed=(n,s='')=>`${n>0?'+':''}${fmt(n)}${s}`;
function render(data){
 const l=data.latest,m=l.metrics,above=m.distance_ma60_pct>0,slope=m.ma60_slope_20d_pct>0,momentum=m.return_20d_pct>=-5&&m.return_20d_pct<=8;
 const strong=l.total<=20,ready=l.total<=25&&above&&slope,pullback=l.total<=35&&above&&slope&&momentum;
 let state;
 if(strong)state={label:'適合分批做多',title:'低風險窗口已出現',copy:'總風險分數進入強訊號區；下一交易日分批進場，預計持有五個交易日後出場。',color:'#3ee0c2'};
 else if(ready)state={label:'適合分批做多',title:'趨勢與風險條件吻合',copy:'風險分數偏低，且指數位置與季線方向符合準備訊號。避免一次投入全部資金。',color:'#3ee0c2'};
 else if(pullback)state={label:'可考慮分批',title:'回檔布局條件成立',copy:'趨勢仍具支撐，20日動能位於回測較有利區間，可評估小額分批進場。',color:'#5b9cff'};
 else {const passed=[l.total<=35,above,slope,momentum].filter(Boolean).length;state=passed>=3?{label:'接近條件',title:'等待最後一項確認',copy:'多數條件已成立，但仍有條件未通過；目前以觀察為主。',color:'#ffc857'}:{label:'暫不適合',title:'尚未出現做多窗口',copy:'風險或趨勢條件尚未吻合，等待條件改善，不需勉強進場。',color:'#ff647c'}}
 $('#entryHero').style.setProperty('--signal',state.color);$('#signal').style.setProperty('--signal',state.color);$('#signal span').textContent=state.label;$('#entryTitle').textContent=state.title;$('#entryCopy').textContent=`${state.copy} 固定獲利了結週期：進場後第 5 個交易日收盤。`;$('#riskScore').textContent=fmt(l.total,1);$('#riskScore').style.color=state.color;$('#asof').textContent=`依 ${l.date} 收盤資料判斷 · 下一交易日適用 · 持有 5 個交易日`;
 const items=[
  ['總風險 ≤35',l.total<=35,`${fmt(l.total,1)} 分`,'回檔布局的基本風險門檻'],
  ['指數高於季線',above,`${signed(m.distance_ma60_pct,'%')}`,'確認指數仍位於季線之上'],
  ['季線斜率為正',slope,`${signed(m.ma60_slope_20d_pct,'%')}`,'確認季線方向向上'],
  ['20日報酬 -5%～+8%',momentum,`${signed(m.return_20d_pct,'%')}`,'排除跌勢過強或短線過熱']
 ];
 $('#conditions').innerHTML=items.map(([n,ok,v,d])=>`<article class="panel condition" style="--condition:${ok?'#3ee0c2':'#ff647c'}"><small>${ok?'已通過':'未通過'}</small><strong>${v}</strong><p>${n}<br>${d}</p></article>`).join('');
 $('#checklist').innerHTML=items.map(([n,ok,v])=>`<div class="check-row"><span class="check-icon" style="color:${ok?'#3ee0c2':'#ff647c'}">${ok?'✓':'×'}</span><span>${n}</span><span class="check-value">${v}</span></div>`).join('');
}
async function load(){try{const r=await fetch('/api/dashboard',{headers:{Accept:'application/json'}}),d=await r.json();if(!r.ok)throw Error(d.error||'資料讀取失敗');render(d)}catch(e){$('#error').hidden=false;$('#error').textContent=e.message}}
load();
