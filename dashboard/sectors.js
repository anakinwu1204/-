const $=s=>document.querySelector(s),fmt=(n,d=2)=>Number(n).toLocaleString('zh-TW',{maximumFractionDigits:d}),signed=n=>`${n>0?'+':''}${fmt(n)}%`;
const color=s=>s>=60?'#3ee0c2':s<40?'#ff647c':'#ffc857';
const groupsByIndustry={
 '半導體':['記憶體','半導體設備','IC設計'],
 '電子零組件':['PCB','ABF載板','CCL銅箔基板'],
 '電腦及週邊設備':['AI伺服器','散熱'],
 '通信網路':['光通訊','網通'],
 '電機機械':['重電','機器人']
};
let datasets={};
function draw(data,{industry=null}={}){
 const sectors=data.sectors,top=sectors.slice(0,3),weak=sectors.slice(-3).reverse(),isTheme=Boolean(industry);
 $('#viewTitle').textContent=isTheme?`${industry}產業細分族群`:'證交所官方產業';
 $('#backToSectors').hidden=!isTheme;
 $('#asof').textContent=`資料截至 ${data.date} · ${data.count} 個${isTheme?'細分族群':'產業'}`;
 $('#headline').textContent=isTheme?`${industry}：${sectors.map(x=>x.sector).join('、')}`:`領先產業：${top.map(x=>x.sector).join('、')}`;
 $('#summary').textContent=sectors.length?`近5日相對大盤最強為${top[0].sector} ${signed(top[0].relative_5d_pct)}；相對較弱為${weak[0].sector} ${signed(weak[0].relative_5d_pct)}。轉強代表5日相對強度翻正但20日仍落後，轉弱則相反。`:`${industry}目前尚未設定細分族群。`;
 $('#leaders').innerHTML=top.map((x,i)=>`<article class="panel leader" style="--sector-color:${color(x.strength)}"><small>強勢排行 ${i+1}</small><strong>${x.sector}</strong><span>5日 ${signed(x.return_5d_pct)} · 相對大盤 ${signed(x.relative_5d_pct)}${x.members?` · ${x.members.join('、')}`:''}</span></article>`).join('');
 $('#sectorRows').innerHTML=sectors.map(x=>{const c=color(x.strength),children=groupsByIndustry[x.sector],clickable=!isTheme&&children,members=x.members?`<small title="${x.members.join('、')}">${x.members.join('、')}</small>`:clickable?`<small>點擊查看：${children.join('、')}</small>`:'';return `<tr><td><span class="${clickable?'sector-link':''}" ${clickable?`data-industry="${x.sector}"`:''}><strong>${x.sector}</strong><br>${members}</span></td><td><span class="tag" style="color:${c};background:${c}20">${x.state}</span></td><td style="color:${x.daily_return_pct>=0?'#3ee0c2':'#ff647c'}">${signed(x.daily_return_pct)}</td><td>${signed(x.return_5d_pct)}</td><td>${signed(x.return_20d_pct)}</td><td>${signed(x.relative_5d_pct)}</td><td>${signed(x.relative_20d_pct)}</td><td>${x.breadth_pct==null?'—':`${fmt(x.breadth_pct,1)}%`}</td><td><span class="meter" style="--meter:${c};--width:${x.strength}%"><i></i></span> ${fmt(x.strength,1)}</td></tr>`}).join('');
 document.querySelectorAll('[data-industry]').forEach(el=>el.addEventListener('click',()=>openIndustry(el.dataset.industry)));
}
function openIndustry(industry){
 const names=groupsByIndustry[industry]||[],items=datasets.themes.sectors.filter(x=>names.includes(x.sector));
 draw({...datasets.themes,sectors:items,count:items.length},{industry});
}
$('#backToSectors').addEventListener('click',()=>draw(datasets.sectors));
async function load(attempt=1){try{const [tr,sr]=await Promise.all(['/api/themes','/api/sectors'].map(url=>fetch(url,{headers:{Accept:'application/json'},cache:'no-store'})));datasets={themes:await tr.json(),sectors:await sr.json()};if(!tr.ok||!sr.ok)throw Error('資料讀取失敗');draw(datasets.sectors)}catch(e){if(attempt<4){setTimeout(()=>load(attempt+1),3000);return}$('#error').hidden=false;$('#error').textContent=`產業資料暫時無法讀取：${e.message}`}}load();
