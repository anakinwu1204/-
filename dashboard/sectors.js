const $=s=>document.querySelector(s),fmt=(n,d=2)=>Number(n).toLocaleString('zh-TW',{maximumFractionDigits:d}),signed=n=>`${n>0?'+':''}${fmt(n)}%`;
const color=s=>s>=60?'#3ee0c2':s<40?'#ff647c':'#ffc857',formatCap=n=>n>=1e12?`${fmt(n/1e12,2)} 兆`:n>=1e8?`${fmt(n/1e8,0)} 億`:`${fmt(n/1e6,0)} 百萬`;
const groupsByIndustry={
 '水泥':['水泥','水泥其他'],
 '食品':['食品製造','飲料食品','油脂飼料','食品其他'],
 '塑膠':['塑化','石化原料','塑膠加工','塑膠其他'],
 '紡織纖維':['機能紡織','聚酯尼龍','織布染整','成衣製鞋','紡織纖維其他'],
 '電器電纜':['電線電纜','電器電纜其他'],
 '化學生技醫療':['生技製藥','原料藥CDMO','生物新藥','醫療器材','眼科視覺','醫美保健','特用化學','基礎化學肥料','塗料接著劑','化學其他','生技醫療其他'],
 '化學':['特用化學','基礎化學肥料','塗料接著劑','化學其他'],
 '生技醫療':['生技製藥','原料藥CDMO','生物新藥','醫療器材','眼科視覺','醫美保健','生技醫療其他'],
 '玻璃陶瓷':['玻璃陶瓷','玻纖布','TGV玻璃基板','玻璃陶瓷其他'],
 '造紙':['造紙','造紙其他'],
 '鋼鐵':['鋼鐵','不鏽鋼特殊鋼','鋼構工程','扣件線材','鋼鐵其他'],
 '橡膠':['輪胎橡膠','橡膠其他'],
 '汽車':['汽車整車','汽車零組件','汽車照明','電動車零組件','汽車精密件','汽車其他'],
 '半導體':['晶圓代工','封裝測試','矽晶圓','功率半導體','化合物半導體','半導體材料','記憶體','半導體設備','IC設計','半導體其他'],
 '電子零組件':['PCB','ABF載板','CCL銅箔基板','玻纖布','TGV玻璃基板','被動元件','石英元件','連接器線材','電池模組','軸承鉸鏈','電子零組件其他'],
 '電腦及週邊設備':['AI伺服器','散熱','電源供應','電腦及週邊設備其他'],
 '通信網路':['光通訊','網通','網通設備','射頻天線','石英元件','通信網路其他'],
 '電機機械':['重電','工具機','傳動元件','工業工具','機器人','電機機械其他'],
 '光電':['面板','LED光電','光學鏡頭','觸控電子紙','安控影像','TGV玻璃基板','光電其他'],
 '電子通路':['半導體通路','電子通路其他'],
 '資訊服務':['資安','系統整合','資訊服務其他'],
 '其他電子':['電子檢測','設備工程','機器人','電源供應','其他電子其他'],
 '建材營造':['營建','建設開發','工程承攬','建材營造其他'],
 '航運':['貨櫃航運','散裝航運','航空','航太造船','物流港口','航運其他'],
 '觀光餐旅':['飯店餐旅','飯店住宿','連鎖餐飲','旅行休閒','觀光餐旅其他'],
 '金融保險':['金控銀行','銀行','證券期貨','保險','金融保險其他'],
 '貿易百貨':['百貨零售','生活零售','服飾通路','貿易百貨其他'],
 '油電燃氣':['石化能源','油電燃氣其他'],
 '綠能環保':['太陽能','風力發電','能源服務','環保','環保處理','綠能環保其他'],
 '數位雲端':['雲端服務','數位雲端其他'],
 '運動休閒':['自行車','運動健身','運動休閒其他'],
 '居家生活':['居家生活','居家生活其他'],
 '其他':['文化創意其他','農業科技其他','其他綜合','其他上市櫃']
};
let datasets={};
function draw(data){
 const sectors=data.sectors,top=[...sectors].sort((a,b)=>b.strength-a.strength).slice(0,3),isTheme=true;
 $('#viewTitle').textContent='細分族群盤勢';
 $('#gridTitle').textContent='全部細分族群';
 $('#gridHint').textContent='依族群總市值由大到小排序';
 $('#backToSectors').hidden=true;
 $('#asof').textContent=`資料截至 ${data.date} · ${data.count} 個細分族群`;
 $('#headline').textContent=`領先族群：${top.map(x=>x.sector).join('、')}`;
 const market=data.market||{},marketText=`大盤風險 ${fmt(market.risk_score,1)}分、近3日 ${signed(market.return_3d_pct)}，族群相對分以 ${(Number(market.factor||1)*100).toFixed(0)}% 市況係數折減。`;
 $('#summary').textContent=sectors.length?`${marketText} 近5日相對大盤最強為${top[0].sector} ${signed(top[0].relative_5d_pct)}；大盤偏弱時，領先僅代表抗跌，不直接視為極強。`:'目前沒有可用的細分族群資料。';
 $('#leaders').innerHTML=top.map((x,i)=>`<article class="panel leader" style="--sector-color:${color(x.strength)}"><small>強勢排行 ${i+1} · ${fmt(x.strength,1)}分</small><strong>${x.sector}</strong><span>5日 ${signed(x.return_5d_pct)} · 相對大盤 ${signed(x.relative_5d_pct)}${x.members?` · ${x.members.join('、')}`:''}</span></article>`).join('');
 $('#sectorRows').innerHTML=sectors.map(x=>{const c=color(x.strength),children=groupsByIndustry[x.sector],clickable=!isTheme&&children,members=x.members?x.members.join('、'):clickable?children.join('、'):'證交所官方產業類股指數',stocks=isTheme&&x.member_details?`<div class="stock-grid">${x.member_details.map(s=>{const tone=s.daily_return_pct>=0?'#3ee0c2':'#ff647c';return `<div class="stock-box" style="--stock-color:${tone}"><strong>${s.code} ${s.name}</strong><div class="stock-price">${fmt(s.close,2)} 元</div><div class="stock-move">${s.change>0?'+':''}${fmt(s.change,2)} · ${signed(s.daily_return_pct)}</div></div>`}).join('')}</div>`:'',metric=(label,value)=>`<div class="metric"><small>${label}</small><b style="color:${Number(value)>=0?'#3ee0c2':'#ff647c'}">${signed(value)}</b></div>`;return `<article class="panel sector-card ${clickable?'clickable':''}" style="--card-color:${c}" ${clickable?`data-industry="${x.sector}"`:''}><div class="sector-card-head"><div><span class="tag" style="color:${c};background:${c}20">${x.state}</span><h4>${x.sector}</h4><small>族群市值 ${formatCap(x.market_cap)}</small></div><div class="sector-score"><strong>${fmt(x.strength,1)}</strong><small>強弱分</small></div></div><div class="metric-grid">${metric('當日',x.daily_return_pct)}${metric('近5日',x.return_5d_pct)}${metric('相對大盤5日',x.relative_5d_pct)}${metric('相對大盤20日',x.relative_20d_pct)}</div><div class="member-list">${isTheme?'個股當日表現':`細分內容：${members}`}${x.breadth_pct==null?'':`<br>上漲家數：${fmt(x.breadth_pct,1)}%`}${stocks}</div>${clickable?'<div class="drill-hint">查看細分族群 →</div>':''}</article>`}).join('');
}
async function load(attempt=1){try{const r=await fetch('/api/themes',{headers:{Accept:'application/json'},cache:'no-store'}),data=await r.json();if(!r.ok)throw Error(data.error||'資料讀取失敗');datasets={themes:data};draw(data)}catch(e){if(attempt<4){setTimeout(()=>load(attempt+1),3000);return}$('#error').hidden=false;$('#error').textContent=`族群資料暫時無法讀取：${e.message}`}}load();
