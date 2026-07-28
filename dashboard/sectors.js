const $=s=>document.querySelector(s),fmt=(n,d=2)=>Number(n).toLocaleString('zh-TW',{maximumFractionDigits:d}),signed=n=>`${n>0?'+':''}${fmt(n)}%`;
const color=s=>s>=60?'#3ee0c2':s<40?'#ff647c':'#ffc857';
function render(data){
 const sectors=data.sectors,top=sectors.slice(0,3),weak=sectors.slice(-3).reverse();
 $('#asof').textContent=`資料截至 ${data.date} · ${data.count} 個產業`;
 $('#headline').textContent=`領先族群：${top.map(x=>x.sector).join('、')}`;
 $('#summary').textContent=`近5日相對大盤最強為${top[0].sector} ${signed(top[0].relative_5d_pct)}；相對較弱為${weak[0].sector} ${signed(weak[0].relative_5d_pct)}。轉強代表5日相對強度翻正但20日仍落後，轉弱則相反。`;
 $('#leaders').innerHTML=top.map((x,i)=>`<article class="panel leader" style="--sector-color:${color(x.strength)}"><small>強勢排行 ${i+1}</small><strong>${x.sector}</strong><span>5日 ${signed(x.return_5d_pct)} · 相對大盤 ${signed(x.relative_5d_pct)}</span></article>`).join('');
 $('#sectorRows').innerHTML=sectors.map(x=>{const c=color(x.strength);return `<tr><td><strong>${x.sector}</strong></td><td><span class="tag" style="color:${c};background:${c}20">${x.state}</span></td><td style="color:${x.daily_return_pct>=0?'#3ee0c2':'#ff647c'}">${signed(x.daily_return_pct)}</td><td>${signed(x.return_5d_pct)}</td><td>${signed(x.return_20d_pct)}</td><td>${signed(x.relative_5d_pct)}</td><td>${signed(x.relative_20d_pct)}</td><td><span class="meter" style="--meter:${c};--width:${x.strength}%"><i></i></span> ${fmt(x.strength,1)}</td></tr>`}).join('');
}
async function load(attempt=1){try{const r=await fetch('/api/sectors',{headers:{Accept:'application/json'},cache:'no-store'}),d=await r.json();if(!r.ok)throw Error(d.error||'資料讀取失敗');render(d)}catch(e){if(attempt<4){setTimeout(()=>load(attempt+1),3000);return}$('#error').hidden=false;$('#error').textContent=`產業資料暫時無法讀取：${e.message}`}}load();
