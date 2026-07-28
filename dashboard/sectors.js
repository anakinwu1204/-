const $=s=>document.querySelector(s),fmt=(n,d=2)=>Number(n).toLocaleString('zh-TW',{maximumFractionDigits:d}),signed=n=>`${n>0?'+':''}${fmt(n)}%`;
const color=s=>s>=60?'#3ee0c2':s<40?'#ff647c':'#ffc857';
const groupsByIndustry={
 '水泥':['水泥'],
 '食品':['食品製造'],
 '塑膠':['塑化'],
 '紡織纖維':['機能紡織'],
 '電器電纜':['電線電纜'],
 '化學生技醫療':['生技製藥','醫療器材','特用化學'],
 '化學':['特用化學'],
 '生技醫療':['生技製藥','醫療器材'],
 '玻璃陶瓷':['玻璃陶瓷'],
 '造紙':['造紙'],
 '鋼鐵':['鋼鐵'],
 '橡膠':['輪胎橡膠'],
 '汽車':['汽車整車','汽車零組件'],
 '半導體':['記憶體','半導體設備','IC設計'],
 '電子零組件':['PCB','ABF載板','CCL銅箔基板','被動元件'],
 '電腦及週邊設備':['AI伺服器','散熱'],
 '通信網路':['光通訊','網通'],
 '電機機械':['重電','機器人'],
 '光電':['面板','LED光電','光學鏡頭'],
 '電子通路':['半導體通路'],
 '資訊服務':['資安','系統整合'],
 '其他電子':['電子檢測','機器人'],
 '建材營造':['營建'],
 '航運':['貨櫃航運','散裝航運','航空'],
 '觀光餐旅':['飯店餐旅'],
 '金融保險':['金控銀行','保險'],
 '貿易百貨':['百貨零售'],
 '油電燃氣':['石化能源'],
 '綠能環保':['太陽能','環保'],
 '數位雲端':['雲端服務'],
 '運動休閒':['自行車','運動健身'],
 '居家生活':['居家生活'],
 '其他':['其他綜合']
};
let datasets={};
function draw(data,{industry=null}={}){
 const sectors=data.sectors,top=sectors.slice(0,3),weak=sectors.slice(-3).reverse(),isTheme=Boolean(industry);
 $('#viewTitle').textContent=isTheme?`${industry}產業細分族群`:'證交所官方產業';
 $('#gridTitle').textContent=isTheme?`${industry}細分族群`:'全部官方產業';
 $('#gridHint').textContent=isTheme?'依市況調整後強弱分排序':'點擊卡片查看細分族群';
 $('#backToSectors').hidden=!isTheme;
 $('#asof').textContent=`資料截至 ${data.date} · ${data.count} 個${isTheme?'細分族群':'產業'}`;
 $('#headline').textContent=isTheme?`${industry}：${sectors.map(x=>x.sector).join('、')}`:`領先產業：${top.map(x=>x.sector).join('、')}`;
 const market=data.market||{},marketText=`大盤風險 ${fmt(market.risk_score,1)}分、近3日 ${signed(market.return_3d_pct)}，族群相對分以 ${(Number(market.factor||1)*100).toFixed(0)}% 市況係數折減。`;
 $('#summary').textContent=sectors.length?`${marketText} 近5日相對大盤最強為${top[0].sector} ${signed(top[0].relative_5d_pct)}；大盤偏弱時，領先僅代表抗跌，不直接視為極強。`:`${industry}目前尚未設定細分族群。`;
 $('#leaders').innerHTML=top.map((x,i)=>`<article class="panel leader" style="--sector-color:${color(x.strength)}"><small>強勢排行 ${i+1} · ${fmt(x.strength,1)}分</small><strong>${x.sector}</strong><span>5日 ${signed(x.return_5d_pct)} · 相對大盤 ${signed(x.relative_5d_pct)}${x.members?` · ${x.members.join('、')}`:''}</span></article>`).join('');
 $('#sectorRows').innerHTML=sectors.map(x=>{const c=color(x.strength),children=groupsByIndustry[x.sector],clickable=!isTheme&&children,members=x.members?x.members.join('、'):clickable?children.join('、'):'證交所官方產業類股指數',stocks=isTheme&&x.member_details?`<div class="stock-table-wrap"><table class="stock-table"><thead><tr><th>股票</th><th>收盤價</th><th>漲跌</th><th>漲跌幅</th></tr></thead><tbody>${x.member_details.map(s=>{const tone=s.daily_return_pct>=0?'#3ee0c2':'#ff647c';return `<tr><td>${s.code} ${s.name}</td><td>${fmt(s.close,2)}</td><td style="color:${tone}">${s.change>0?'+':''}${fmt(s.change,2)}</td><td style="color:${tone};font-weight:800">${signed(s.daily_return_pct)}</td></tr>`}).join('')}</tbody></table></div>`:'',metric=(label,value)=>`<div class="metric"><small>${label}</small><b style="color:${Number(value)>=0?'#3ee0c2':'#ff647c'}">${signed(value)}</b></div>`;return `<article class="panel sector-card ${clickable?'clickable':''}" style="--card-color:${c}" ${clickable?`data-industry="${x.sector}"`:''}><div class="sector-card-head"><div><span class="tag" style="color:${c};background:${c}20">${x.state}</span><h4>${x.sector}</h4></div><div class="sector-score"><strong>${fmt(x.strength,1)}</strong><small>強弱分</small></div></div><div class="metric-grid">${metric('當日',x.daily_return_pct)}${metric('近5日',x.return_5d_pct)}${metric('相對大盤5日',x.relative_5d_pct)}${metric('相對大盤20日',x.relative_20d_pct)}</div><div class="member-list">${isTheme?'個股當日表現':`細分內容：${members}`}${x.breadth_pct==null?'':`<br>上漲家數：${fmt(x.breadth_pct,1)}%`}${stocks}</div>${clickable?'<div class="drill-hint">查看細分族群 →</div>':''}</article>`}).join('');
 document.querySelectorAll('[data-industry]').forEach(el=>el.addEventListener('click',()=>openIndustry(el.dataset.industry)));
}
function openIndustry(industry){
 const names=groupsByIndustry[industry]||[],items=datasets.themes.sectors.filter(x=>names.includes(x.sector));
 draw({...datasets.themes,sectors:items,count:items.length},{industry});
}
$('#backToSectors').addEventListener('click',()=>draw(datasets.sectors));
async function load(attempt=1){try{const [tr,sr]=await Promise.all(['/api/themes','/api/sectors'].map(url=>fetch(url,{headers:{Accept:'application/json'},cache:'no-store'})));datasets={themes:await tr.json(),sectors:await sr.json()};if(!tr.ok||!sr.ok)throw Error('資料讀取失敗');draw(datasets.sectors)}catch(e){if(attempt<4){setTimeout(()=>load(attempt+1),3000);return}$('#error').hidden=false;$('#error').textContent=`產業資料暫時無法讀取：${e.message}`}}load();
