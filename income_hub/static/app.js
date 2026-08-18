const S = { tab:'overview', data:null, ideas:[], channels:[], videos:[], activeChannel:null, busy:{},
  books:[], arbs:[], singleBets:[], betSummary:null, betHistory:null,
  calc:{event:'',total:100,legs:[{sel:'',odds:'',book:''},{sel:'',odds:'',book:''}]},
  scanSports:[], scanSelected:[], scanResults:[], scanQuota:null, scanMinProfit:0,
  fl:{clients:[], projects:[], invoices:[], summary:null},
  costs:[], goal:null };

const KIND = {
  micro_saas:{label:'Micro-SaaS',cls:'badge-cyan'}, youtube:{label:'YouTube',cls:'badge-red'},
  trading:{label:'Trading',cls:'badge-amber'}, betting:{label:'Betting',cls:'badge-purple'},
  affiliate:{label:'Affiliate',cls:'badge-blue'}, freelance:{label:'Freelance',cls:'badge-green'},
  other:{label:'Other',cls:'badge-muted'},
};
const STATUS = {idea:'badge-muted',building:'badge-amber',launched:'badge-blue',earning:'badge-green',paused:'badge-muted'};
const STAGES = ['idea','scripted','voiced','rendered','uploaded','published'];
const SAAS_STAGES = [['idea','Ideas'],['validating','Validating'],['building','Building'],['launched','Launched'],['earning','Earning']];

const api = {
  async req(m,p,b){const o={method:m,headers:{}};if(b!==undefined){o.body=JSON.stringify(b);o.headers['Content-Type']='application/json';}
    const r=await fetch(p,o);if(!r.ok){let t=await r.text();try{t=JSON.parse(t).detail||t}catch{}throw new Error(t);}return r.status===204?null:r.json();},
  get:(p)=>api.req('GET',p), post:(p,b)=>api.req('POST',p,b), put:(p,b)=>api.req('PUT',p,b), del:(p)=>api.req('DELETE',p),
};
function esc(s){return String(s??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}
function fmt(n){return Math.round(Number(n||0)).toLocaleString('en-US')}

/* ── nav / shell ── */
function nav(t){
  const dl=document.getElementById('detail-layer');
  if(dl){dl.classList.remove('show');dl.innerHTML='';S.detailId=null;document.getElementById('content').classList.remove('pushed');}
  S.tab=t;document.querySelectorAll('.seg-item').forEach(e=>e.classList.toggle('active',e.dataset.tab===t));
  window.scrollTo({top:0,behavior:'auto'});render();}

const navBar=document.getElementById('top-nav');
window.addEventListener('scroll',()=>navBar.classList.toggle('scrolled',window.scrollY>6),{passive:true});
document.addEventListener('keydown',e=>{if(e.key!=='Escape')return;
  if(document.getElementById('modal-root').innerHTML)closeModal();
  else if(document.getElementById('detail-layer').classList.contains('show'))closeStream();});

let _io;
function observeReveals(){
  _io?.disconnect();
  _io=new IntersectionObserver((es)=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('in');_io.unobserve(e.target);}}),
    {threshold:.12,rootMargin:'0px 0px -8% 0px'});
  document.querySelectorAll('.reveal:not(.in)').forEach(el=>_io.observe(el));
}

async function loadDash(){S.data=await api.get('/api/dashboard');
  const on=S.data.settings.api_key_set,p=document.getElementById('ai-pill');
  p.className='ai-pill '+(on?'on':'off');
  document.getElementById('ai-status').textContent=on?'Gemini ready':'No AI key';}

async function render(){
  stopQueuePoll();
  const el=document.getElementById('content'),ac=document.getElementById('actions');ac.innerHTML='';
  try{
    if(S.tab==='overview'){await loadDash();el.innerHTML=renderOverview();initOverview();
      ac.innerHTML=`<button class="btn btn-primary btn-sm" onclick="streamModal()">+ New stream</button>`;}
    else if(S.tab==='saas'){S.ideas=await api.get('/api/saas/ideas');el.innerHTML=renderSaas();}
    else if(S.tab==='youtube'){await loadDash();S.channels=await api.get('/api/yt/channels');S.videos=await api.get('/api/yt/videos');el.innerHTML=renderYouTube();
      if(S.channels.length){ac.innerHTML=`<button class="btn btn-primary btn-sm" onclick="channelModal()">+ Channel</button>`;startQueuePoll();}}
    else if(S.tab==='betting'){
      const [summary,books,arbs,singles,hist]=await Promise.all([
        api.get('/api/bet/summary'),api.get('/api/bet/books'),api.get('/api/bet/arbs'),
        api.get('/api/bet/bets'),api.get('/api/bet/history')]);
      S.betSummary=summary;S.books=books;S.arbs=arbs;S.singleBets=singles;S.betHistory=hist;
      el.innerHTML=renderBetting();calcRecalc();initBetChart();
      ac.innerHTML=`<button class="btn btn-primary btn-sm" onclick="syncBetting()">Sync to Overview</button>`;
      if(summary.odds_ready&&!S.scanSports.length)loadSports();}
    else if(S.tab==='freelance'){
      const [sum,clients,projects,invoices]=await Promise.all([
        api.get('/api/fl/summary'),api.get('/api/fl/clients'),
        api.get('/api/fl/projects'),api.get('/api/fl/invoices')]);
      S.fl={summary:sum,clients,projects,invoices};
      el.innerHTML=renderFreelance();
      ac.innerHTML=`<button class="btn btn-primary btn-sm" onclick="syncFreelance()">Sync to Overview</button>`;}
    else if(S.tab==='settings'){await loadDash();el.innerHTML=renderSettings();}
    observeReveals();
  }catch(e){el.innerHTML=`<div class="empty"><div class="ico">⚠️</div><div class="big">Something went wrong</div>${esc(e.message)}</div>`;}
}

/* ── Overview (interactive mind map) ── */
function kindColor(k){return {micro_saas:'#0aa2c0',youtube:'#ff3b30',trading:'#ff9500',betting:'#8e5cff',affiliate:'#0071e3',freelance:'#00a862',other:'#86868b'}[k]||'#86868b';}
function polar(cx,cy,r,deg){const a=deg*Math.PI/180;return [cx+r*Math.cos(a),cy+r*Math.sin(a)];}
/* deterministic 0..1 pseudo-random so the scatter is organic but stable per id */
function rnd(n){const x=Math.sin(n*127.1+31.7)*43758.5453;return x-Math.floor(x);}
function clampX(v){return Math.max(84,Math.min(1036,v));}
function clampY(v){return Math.max(74,Math.min(706,v));}
/* curved (quadratic) connector with a seeded perpendicular bow */
function curvePath(x1,y1,x2,y2,s){
  const mx=(x1+x2)/2,my=(y1+y2)/2,dx=x2-x1,dy=y2-y1,len=Math.hypot(dx,dy)||1;
  const k=(s*2-1)*Math.min(74,len*.28);
  const cxp=mx+(-dy/len)*k, cyp=my+(dx/len)*k;
  return `M${x1.toFixed(1)},${y1.toFixed(1)} Q${cxp.toFixed(1)},${cyp.toFixed(1)} ${x2.toFixed(1)},${y2.toFixed(1)}`;
}

function leafNode(s,lx,ly,delay){
  const rev=s.monthly_revenue||0;
  return `<div class="mnode leaf" data-id="${s.id}" data-kind="${s.kind}" style="left:${lx}%;top:${ly}%;--d:${delay}ms" onclick="openStream(${s.id},event)">
    <div class="mnode-in">
      <span class="mn-dot" style="background:${kindColor(s.kind)}"></span>
      <div class="mn-txt"><div class="mn-name">${esc(s.name)}</div><div class="mn-mrr ${rev>0?'':'zero'}">$${fmt(rev)}<span>/mo</span></div></div>
    </div></div>`;
}

function renderMindMap(){
  const d=S.data,t=d.totals;
  const W=1120,H=780,cx=560,cy=372;
  const groups={};d.streams.forEach(s=>{(groups[s.kind]=groups[s.kind]||[]).push(s);});
  const types=Object.keys(groups).map(k=>({kind:k,info:KIND[k]||KIND.other,streams:groups[k]}));
  const n=types.length;
  const R1=n<=1?170:n<=3?200:n<=5?215:225;
  let conns='',nodes='';
  types.forEach((ty,i)=>{
    const sk=i*3+1;
    const baseAng=-90+i*360/n;
    const ang=baseAng+(rnd(sk)*2-1)*24;           // jittered branch angle
    const R=R1+(rnd(sk+5)*2-1)*42;                 // jittered branch distance
    let [tx,ty_]=polar(cx,cy,R,ang);tx=clampX(tx);ty_=clampY(ty_);
    const dT=180+i*70;
    conns+=`<path class="conn conn-type" data-kind="${ty.kind}" pathLength="1" style="--d:${90+i*55}ms" d="${curvePath(cx,cy,tx,ty_,rnd(sk+2))}"/>`;
    nodes+=`<div class="mnode tnode" data-kind="${ty.kind}" style="left:${tx/W*100}%;top:${ty_/H*100}%;--d:${dT}ms" onclick="toggleType('${ty.kind}',event)">
      <div class="mnode-in"><span class="t-name">${esc(ty.info.label)}</span><span class="t-cnt">${ty.streams.length}</span></div></div>`;
    const m=ty.streams.length;
    const spread=Math.min((m-1)*28,160);
    ty.streams.forEach((s,j)=>{
      const off=(m===1?0:(-spread/2+j*(spread/(m-1)))) + (rnd(s.id)*2-1)*16;   // scattered fan
      const L=(m>4?170:150)+(rnd(s.id+9)*2-1)*40;                               // scattered distance
      let [lx,ly]=polar(tx,ty_,L,ang+off);lx=clampX(lx);ly=clampY(ly);
      conns+=`<path class="conn conn-leaf" data-kind="${ty.kind}" data-leaf="${s.id}" pathLength="1" style="--d:${dT+80}ms" d="${curvePath(tx,ty_,lx,ly,rnd(s.id+3))}"/>`;
      nodes+=leafNode(s,lx/W*100,ly/H*100,dT+150+j*70);
    });
  });
  const hub=`<div class="mnode hub" style="left:50%;top:${cy/H*100}%;--d:0ms">
    <div class="mnode-in"><div class="h-lbl">Net / month</div>
    <div class="h-fig tnum"><span class="cur">$</span><span id="hn" data-to="${t.net}">0</span></div>
    <div class="h-sub">${t.count} ${t.count===1?'stream':'streams'} · $${fmt(t.mrr)} MRR</div></div></div>`;
  if(!d.streams.length){
    nodes=`<div class="mnode addnode" style="left:50%;top:${(cy-170)/H*100}%;--d:220ms" onclick="streamModal()"><div class="mnode-in">＋ Add your first stream</div></div>`;
  }
  return `<svg class="map-svg" viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet">${conns}</svg>${hub}${nodes}`;
}

function toggleType(kind,ev){ev&&ev.stopPropagation();const stage=document.querySelector('.map-stage');if(!stage)return;
  const tnode=stage.querySelector(`.tnode[data-kind="${kind}"]`);
  const collapse=!tnode.classList.contains('collapsed');
  tnode.classList.toggle('collapsed',collapse);
  stage.querySelectorAll(`.mnode.leaf[data-kind="${kind}"]`).forEach(n=>n.classList.toggle('hidden-branch',collapse));
  stage.querySelectorAll(`.conn.conn-leaf[data-kind="${kind}"]`).forEach(c=>c.classList.toggle('hidden-branch',collapse));}

/* ── Stream detail page (pushed view) ── */
function openStream(id,ev){ev&&ev.stopPropagation();if(!S.data)return;
  const s=S.data.streams.find(x=>x.id===id);if(!s)return;
  S.detailId=id;const layer=document.getElementById('detail-layer');
  layer.innerHTML=renderStreamDetail(s);
  layer.scrollTop=0;
  requestAnimationFrame(()=>{layer.classList.add('show');document.getElementById('content').classList.add('pushed');});
  initDetail(s);}
function closeStream(){const layer=document.getElementById('detail-layer');
  layer.classList.remove('show');document.getElementById('content').classList.remove('pushed');S.detailId=null;
  setTimeout(()=>{if(!layer.classList.contains('show'))layer.innerHTML='';},460);}
function renderStreamDetail(s){
  const k=KIND[s.kind]||KIND.other;const rev=s.monthly_revenue||0,cost=s.monthly_cost||0,net=rev-cost;
  const margin=rev>0?Math.round(net/rev*100):0;
  return `
  <div class="detail-top"><div class="inner">
    <button class="btn btn-secondary btn-sm" onclick="closeStream()">← Map</button>
    <span class="badge ${k.cls}">${k.label}</span>
  </div></div>
  <div class="detail-body">
    <div class="detail-hero">
      <span class="d-dot" style="background:${kindColor(s.kind)}"></span>
      <h1 class="d-name">${esc(s.name)}</h1>
      <div class="d-badges"><span class="badge ${STATUS[s.status]||'badge-muted'}">${s.status}</span>
        ${s.url?`<a class="badge badge-blue" href="${esc(s.url)}" target="_blank">Open site ↗</a>`:''}</div>
    </div>
    <div class="d-figs">
      <div class="statc green"><div class="top"><div class="lbl">Revenue</div><div class="ico">↗</div></div><div class="val tnum"><span class="cur">$</span><span id="d-rev" data-to="${rev}">0</span></div><div class="foot">per month</div></div>
      <div class="statc red"><div class="top"><div class="lbl">Cost</div><div class="ico">↘</div></div><div class="val tnum"><span class="cur">$</span><span id="d-cost" data-to="${cost}">0</span></div><div class="foot">per month</div></div>
      <div class="statc ink"><div class="top"><div class="lbl">Net / mo</div><div class="ico">◆</div></div><div class="val tnum"><span class="cur">$</span><span id="d-net" data-to="${net}">0</span></div><div class="foot">${margin}% margin</div></div>
    </div>
    <div class="card card-pad d-panel">
      <div class="card-title" style="margin-bottom:6px">Run-rate</div>
      <div class="d-bars">
        <div class="d-bar"><div class="d-bar-l">Annual revenue</div><div class="d-bar-v">$${fmt(rev*12)}</div></div>
        <div class="d-bar"><div class="d-bar-l">Annual cost</div><div class="d-bar-v" style="color:var(--red)">$${fmt(cost*12)}</div></div>
        <div class="d-bar"><div class="d-bar-l">Annual net</div><div class="d-bar-v" style="color:var(--green-ink)">$${fmt(net*12)}</div></div>
      </div>
    </div>
    ${s.notes?`<div class="card card-pad d-panel"><div class="card-title" style="margin-bottom:12px">Notes</div><div style="color:var(--ink-2);line-height:1.65;white-space:pre-wrap">${esc(s.notes)}</div></div>`:''}
    <div class="d-actions">
      <button class="btn btn-dark" onclick="streamModal(${s.id})">Edit stream</button>
      <button class="btn btn-danger" onclick="delStream(${s.id})">Delete</button>
    </div>
  </div>`;
}
function initDetail(s){['d-rev','d-cost','d-net'].forEach(countUp);}

function renderOverview(){
  const d=S.data,t=d.totals;
  return `
  <section class="section" style="padding-top:22px;padding-bottom:34px">
    <div class="wrap">
      <div style="text-align:center;margin-bottom:2px"><div class="eyebrow reveal in">Your income map</div></div>
      <div class="map-wrap"><div class="map-stage" id="mindmap">${renderMindMap()}</div></div>
      <div style="text-align:center;color:var(--faint);font-size:13px;font-weight:600;margin-top:2px">
        Tap a <b style="color:var(--ink-2)">branch</b> to collapse · tap a <b style="color:var(--ink-2)">source</b> to expand · tap the centre to reset</div>
    </div>
  </section>

  <section class="section band tight">
    <div class="wrap">
      <div class="trio">
        <div class="statc green reveal" style="--d:0ms">
          <div class="top"><div class="lbl">Gross MRR</div><div class="ico">↗</div></div>
          <div class="val tnum"><span class="cur">$</span><span id="tm" data-to="${t.mrr}">0</span></div>
          <div class="foot">${t.count} active ${t.count===1?'stream':'streams'} recurring</div>
        </div>
        <div class="statc red reveal" style="--d:90ms">
          <div class="top"><div class="lbl">Monthly burn</div><div class="ico">↘</div></div>
          <div class="val tnum"><span class="cur">$</span><span id="tc" data-to="${t.cost}">0</span></div>
          <div class="foot">${t.mrr>0?Math.round(t.cost/t.mrr*100):0}% of gross revenue</div>
        </div>
        <div class="statc ink reveal" style="--d:180ms">
          <div class="top"><div class="lbl">Net / month</div><div class="ico">◆</div></div>
          <div class="val tnum"><span class="cur">$</span><span id="tn" data-to="${t.net}">0</span></div>
          <div class="foot">${d.shared_costs_total>0?`after streams + $${fmt(d.shared_costs_total)} shared costs`:'after all monthly costs'}</div>
        </div>
      </div>
      ${renderGoalBar(d)}
    </div>
  </section>

  <section class="section">
    <div class="wrap">
      <div class="card card-pad reveal" style="--d:0ms">
        <div class="card-head"><div><div class="card-title">Revenue</div><div class="card-sub">Last 6 months</div></div>
          <div style="display:flex;gap:8px">
            <button class="btn btn-secondary btn-sm" onclick="costsModal()">Shared costs</button>
            <button class="btn btn-dark btn-sm" onclick="streamModal()">+ New stream</button>
          </div>
        </div>
        <canvas id="trend" style="max-height:250px"></canvas>
      </div>
    </div>
  </section>

  <footer><div class="wrap"><span>Income Hub</span><span>${d.streams.length} ${d.streams.length===1?'stream':'streams'} tracked</span></div></footer>`;
}

function countUp(id){const el=document.getElementById(id);if(!el)return;
  const to=parseFloat(el.dataset.to||el.textContent)||0;const dur=1000;const t0=performance.now();
  function step(t){const p=Math.min(1,(t-t0)/dur);const e=1-Math.pow(1-p,3);
    el.textContent=fmt(to*e);if(p<1)requestAnimationFrame(step);}
  requestAnimationFrame(step);}

function initOverview(){
  ['hn','tm','tc','tn'].forEach(countUp);
  const tr=S.data.trend;const c=document.getElementById('trend');if(!c)return;
  Chart.defaults.color='#86868b';Chart.defaults.font.family="'Manrope',sans-serif";Chart.defaults.font.size=11;
  const ctx=c.getContext('2d');
  const g=ctx.createLinearGradient(0,0,0,250);
  g.addColorStop(0,'rgba(11,197,124,.26)');g.addColorStop(1,'rgba(11,197,124,0)');
  const labels=tr.labels.length?tr.labels:['—'];
  new Chart(c,{type:'line',data:{labels,datasets:[
    {label:'Revenue',data:tr.revenue,borderColor:'#00a862',backgroundColor:g,fill:true,tension:.4,
      borderWidth:2.5,pointRadius:0,pointHoverRadius:5,pointBackgroundColor:'#00a862',pointBorderColor:'#fff',pointBorderWidth:2},
    {label:'Cost',data:tr.cost,borderColor:'#ff9500',backgroundColor:'transparent',fill:false,tension:.4,
      borderWidth:1.5,borderDash:[5,4],pointRadius:0,pointHoverRadius:4}]},
    options:{maintainAspectRatio:false,plugins:{legend:{display:true,position:'top',align:'end',
        labels:{boxWidth:8,boxHeight:8,usePointStyle:true,pointStyle:'circle',padding:16,color:'#6e6e73',font:{weight:600}}},
      tooltip:{backgroundColor:'#1d1d1f',padding:11,cornerRadius:10,titleColor:'#fff',bodyColor:'#0bc57c',displayColors:false,
        callbacks:{label:c=>' '+c.dataset.label+': $'+fmt(c.parsed.y)}}},
      scales:{x:{grid:{display:false},border:{display:false},ticks:{color:'#86868b'}},
        y:{grid:{color:'rgba(0,0,0,.06)'},border:{display:false},ticks:{color:'#86868b',callback:v=>'$'+fmt(v)}}}}});}

function renderGoalBar(d){
  const g=d.goal;const net=d.totals.net;
  if(!g||!g.target_net){
    return `<div class="goal-bar-wrap reveal" style="--d:270ms;margin-top:18px;display:flex;align-items:center;justify-content:space-between;gap:16px">
      <div><div style="font-size:13.5px;font-weight:700;color:var(--muted)">No monthly goal set</div>
        <div style="font-size:12px;color:var(--faint);margin-top:2px">Set a net income target to track your progress</div></div>
      <button class="btn btn-secondary btn-sm" onclick="goalModal()">Set goal</button>
    </div>`;
  }
  const pct=Math.min(100,Math.round(net/g.target_net*100));
  const col=pct>=100?'var(--green)':pct>=60?'var(--sky)':'var(--amber)';
  return `<div class="goal-bar-wrap reveal" style="--d:270ms;margin-top:18px">
    <div style="display:flex;justify-content:space-between;align-items:center;gap:12px">
      <div style="font-size:13.5px;font-weight:700">Monthly goal · ${g.period}</div>
      <div style="display:flex;align-items:center;gap:9px">
        <span style="font-family:var(--disp);font-weight:600;font-size:17px;color:${col}">${pct}%</span>
        <button class="btn btn-secondary btn-sm" onclick="goalModal()">Edit</button>
      </div>
    </div>
    <div class="goal-bar-track"><div class="goal-bar-fill" style="width:${pct}%;background:linear-gradient(90deg,${col},${col})"></div></div>
    <div class="goal-labels"><span>$0</span><span style="color:${col};font-weight:700">$${fmt(net)} net</span><span>$${fmt(g.target_net)} target</span></div>
  </div>`;
}

function goalModal(){
  const g=S.data?.goal;const period=new Date().toISOString().slice(0,7);
  modal('Monthly income goal',`
    <div class="row"><label>Month</label><input id="goal-period" value="${g?.period||period}"></div>
    <div class="row2">
      <div><label>Target gross revenue ($)</label><input id="goal-rev" type="number" value="${g?.target_revenue||0}"></div>
      <div><label>Target net income ($)</label><input id="goal-net" type="number" value="${g?.target_net||0}"></div>
    </div>`,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button>
     <button class="btn btn-primary" onclick="saveGoal()">Save goal</button>`);}
async function saveGoal(){
  const b={period:val('goal-period'),target_revenue:parseFloat(val('goal-rev'))||0,target_net:parseFloat(val('goal-net'))||0};
  await api.put('/api/goals/current',b);closeModal();render();}

async function costsModal(){
  S.costs=await api.get('/api/costs');
  const rows=S.costs.map(c=>`
    <div class="cost-row" id="cr-${c.id}">
      <div style="font-weight:600">${esc(c.name)}<span class="badge badge-muted" style="margin-left:7px">${esc(c.category)}</span></div>
      <div style="font-size:12.5px;color:var(--muted)">${esc(c.url||'')}</div>
      <div style="font-family:var(--disp);font-weight:600;text-align:right">$${fmt(c.amount)}<span style="font-size:10px;color:var(--faint);font-family:var(--sans)">/mo</span></div>
      <button class="icobtn d" onclick="deleteCost(${c.id})">✕</button>
    </div>`).join('');
  const total=S.costs.filter(c=>c.active).reduce((a,c)=>a+c.amount,0);
  modal('Shared recurring costs',`
    <p style="color:var(--muted);font-size:13.5px;margin-bottom:16px">Costs shared across all streams — hosting, domains, API keys, tools. Shown as a deduction from your true net on Overview.</p>
    <div style="margin-bottom:18px">${rows||'<div style="color:var(--faint);text-align:center;padding:20px 0">No shared costs yet</div>'}</div>
    <div style="border-top:1px solid var(--line);padding-top:14px;margin-bottom:4px;font-weight:700;text-align:right;font-size:14px">Total: <span style="color:var(--red)">$${fmt(total)}/mo</span></div>
    <div class="row2" style="margin-top:16px">
      <div><label>Name</label><input id="cost-name" placeholder="e.g. Netlify hosting"></div>
      <div><label>$/month</label><input id="cost-amt" type="number" placeholder="0"></div>
    </div>
    <div class="row2">
      <div><label>Category</label><select id="cost-cat"><option>hosting</option><option>domain</option><option>api</option><option>tools</option><option>other</option></select></div>
      <div><label>URL (optional)</label><input id="cost-url" placeholder="provider site"></div>
    </div>`,
    `<button class="btn btn-secondary" onclick="closeModal()">Done</button>
     <button class="btn btn-primary" onclick="addCost()">Add cost</button>`);}
async function addCost(){const b={name:val('cost-name'),amount:parseFloat(val('cost-amt'))||0,category:val('cost-cat'),url:val('cost-url')};
  if(!b.name)return alert('Name required');await api.post('/api/costs',b);await costsModal();}
async function deleteCost(id){await api.del('/api/costs/'+id);await costsModal();}

function streamModal(id){const s=id?S.data.streams.find(x=>x.id===id):null;const v=(f,d='')=>s?(s[f]??d):d;
  const kinds=Object.keys(KIND).map(k=>`<option value="${k}" ${v('kind','micro_saas')===k?'selected':''}>${KIND[k].label}</option>`).join('');
  const sts=Object.keys(STATUS).map(k=>`<option value="${k}" ${v('status','idea')===k?'selected':''}>${k}</option>`).join('');
  modal(`${s?'Edit':'New'} income stream`,`
    <div class="row"><label>Name</label><input id="st-name" value="${esc(v('name'))}"></div>
    <div class="row2"><div><label>Type</label><select id="st-kind">${kinds}</select></div><div><label>Status</label><select id="st-status">${sts}</select></div></div>
    <div class="row2"><div><label>Monthly revenue ($)</label><input id="st-rev" type="number" value="${v('monthly_revenue',0)}"></div><div><label>Monthly cost ($)</label><input id="st-cost" type="number" value="${v('monthly_cost',0)}"></div></div>
    <div class="row"><label>URL</label><input id="st-url" value="${esc(v('url'))}"></div>
    <div class="row"><label>Notes</label><textarea id="st-notes">${esc(v('notes'))}</textarea></div>`,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="saveStream(${id||'null'})">Save</button>`);}
async function saveStream(id){const b={name:val('st-name'),kind:val('st-kind'),status:val('st-status'),
  monthly_revenue:parseFloat(val('st-rev'))||0,monthly_cost:parseFloat(val('st-cost'))||0,url:val('st-url'),notes:val('st-notes')};
  if(!b.name)return alert('Name required');
  try{if(id)await api.put('/api/streams/'+id,b);else await api.post('/api/streams',b);closeModal();
    const detailOpen=document.getElementById('detail-layer').classList.contains('show');
    await render();
    if(detailOpen&&id)openStream(id);
  }catch(e){alert(e.message);}}
async function delStream(id){if(!confirm('Delete this stream?'))return;await api.del('/api/streams/'+id);
  if(document.getElementById('detail-layer').classList.contains('show'))closeStream();
  render();}

/* ── Micro-SaaS ── */
function ideaCard(i){
  const sc=i.score,col=sc>=70?'var(--green)':sc>=55?'var(--sky)':sc>=40?'var(--amber)':'var(--muted)';
  const chips=[];if(i.build_kit)chips.push('kit');if(i.research)chips.push('research');if(i.has_landing)chips.push('page');
  return `<div class="scard" onclick="ideaDetail(${i.id})">
    <div style="display:flex;justify-content:space-between;gap:8px"><div class="scard-t">${esc(i.name)}</div>
      <div style="color:${col};font-family:var(--disp);font-weight:600;font-size:17px">${sc}</div></div>
    <div class="scard-sub">${esc(i.problem)}</div>
    <div class="scard-foot">
      ${chips.map(c=>`<span class="dchip on">${c}</span>`).join('')}
      ${i.signups?`<span class="dchip on">✉ ${i.signups}</span>`:''}
      ${i.mrr>0?`<span class="dchip on">$${fmt(i.mrr)}/mo</span>`:''}
    </div></div>`;
}
function renderSaasBoard(){
  if(!S.ideas.length)return `<div class="empty"><div class="ico">🚀</div><div class="big">No ideas yet</div>Generate your first batch above.</div>`;
  return `<div class="saas-cols">`+SAAS_STAGES.map(([key,label])=>{
    const items=S.ideas.filter(i=>(i.stage||'idea')===key);
    return `<div class="col"><div class="col-head">${label}<span>${items.length}</span></div>${items.map(ideaCard).join('')}</div>`;
  }).join('')+`</div>`;
}
function renderSaas(){
  return `
  <section class="hero" style="padding:56px 0 16px">
    <div class="wrap">
      <div class="eyebrow reveal in">Micro-SaaS Launchpad</div>
      <h1 class="disp reveal in" style="font-size:clamp(36px,5.5vw,60px);letter-spacing:-.03em;line-height:1.02;margin:12px 0 0">Idea to income,<br>one product at a time.</h1>
      <p class="hero-sub reveal in" style="margin-top:18px;max-width:640px;margin-left:auto;margin-right:auto">Generate scored ideas, then work each one across the pipeline — build kit, market research, a real landing page, and a task list — until it earns.</p>
    </div>
  </section>
  <section class="section tight"><div class="wrap">
    <div class="toolbar reveal in">
      <input id="saas-focus" placeholder="Optional focus — e.g. tools for tradies, AI for accountants" style="max-width:420px">
      <select id="saas-n" style="width:auto"><option>6</option><option>8</option><option>10</option></select>
      <button class="btn btn-primary" id="gen-btn" onclick="genIdeas()">✨ Generate ideas</button>
    </div>
    <div id="saas-board" class="reveal in">${renderSaasBoard()}</div>
  </div></section>`;
}
function refreshSaasBoard(){const el=document.getElementById('saas-board');if(el)el.innerHTML=renderSaasBoard();}
function refreshIdea(u){if(!u)return;const k=S.ideas.findIndex(x=>x.id===u.id);if(k>=0)S.ideas[k]=u;}
async function genIdeas(){const btn=document.getElementById('gen-btn');btn.disabled=true;btn.innerHTML='<span class="spin"></span> Generating…';
  try{S.ideas=await api.post('/api/saas/generate',{n:parseInt(val('saas-n'))||6,focus:val('saas-focus')});render();}
  catch(e){alert('Error: '+e.message);btn.disabled=false;btn.innerHTML='✨ Generate ideas';}}

function kitView(k){return `
  <div class="kv"><b>MVP scope</b><p>${esc(k.mvp_scope)}</p></div>
  <div class="kv"><b>Stack</b><div class="chips2">${(k.stack||[]).map(s=>`<span class="sm">${esc(s)}</span>`).join('')}</div></div>
  <div class="kv"><b>Features</b>${(k.features||[]).map(f=>`<div class="li"><b>${esc(f.name)}</b> — ${esc(f.detail)}</div>`).join('')}</div>
  <div class="kv"><b>Data model</b>${(k.data_model||[]).map(d=>`<div class="li"><b>${esc(d.entity)}</b>: ${esc(d.fields)}</div>`).join('')}</div>
  <div class="kv"><b>Pricing</b>${(k.pricing||[]).map(p=>`<div class="li"><b>${esc(p.tier)}</b> ${esc(p.price)} — ${esc(p.features)}</div>`).join('')}</div>
  <div class="kv"><b>Roadmap</b>${(k.roadmap||[]).map(r=>`<div class="li"><b>${esc(r.week)}</b>: ${esc(r.goal)}<ul>${(r.tasks||[]).map(t=>`<li>${esc(t)}</li>`).join('')}</ul></div>`).join('')}</div>`;}
function researchView(r){return `
  <div class="kv"><b>Verdict</b><p>${esc(r.verdict)}</p></div>
  <div class="kv"><b>Competitors</b>${(r.competitors||[]).map(c=>`<div class="li"><b>${esc(c.name)}</b> — ${esc(c.angle)} <span style="color:var(--faint)">(${esc(c.pricing)})</span></div>`).join('')}</div>
  <div class="kv"><b>Demand signals</b><ul>${(r.demand_signals||[]).map(s=>`<li>${esc(s)}</li>`).join('')}</ul></div>
  <div class="kv"><b>Keywords</b><div class="chips2">${(r.keywords||[]).map(k=>`<span class="sm">${esc(k)}</span>`).join('')}</div></div>
  <div class="kv"><b>Pricing benchmark</b><p>${esc(r.pricing_benchmark)}</p></div>
  <div class="kv"><b>Risks</b><ul>${(r.risks||[]).map(s=>`<li>${esc(s)}</li>`).join('')}</ul></div>
  <div class="kv"><b>Differentiation</b><p>${esc(r.differentiation)}</p></div>`;}

function ideaDetail(id){const i=S.ideas.find(x=>x.id===id);if(!i)return;S.saasBusy=S.saasBusy||{};
  const busy=k=>S.saasBusy[id+'-'+k];
  const done=(i.validation||[]).filter(x=>x.done).length,tot=(i.validation||[]).length;
  const checks=(i.validation||[]).map((c,idx)=>`<label class="tasrow" style="cursor:pointer"><input type="checkbox" ${c.done?'checked':''} onchange="toggleCheck(${id},${idx},this.checked)"><span style="font-size:13.5px;color:var(--ink)">${esc(c.item)}</span></label>`).join('');
  const stageBar=SAAS_STAGES.map(([k,l])=>`<button class="stage-btn ${(i.stage||'idea')===k?'on':''}" onclick="moveStage(${id},'${k}')">${l}</button>`).join('');
  const kitBox=busy('kit')?`<div style="color:var(--muted)"><span class="spin"></span> Generating build kit…</div>`
    :i.build_kit?kitView(i.build_kit)+`<button class="btn btn-secondary btn-sm" style="margin-top:6px" onclick="saasGen(${id},'kit','build-kit')">Regenerate</button>`
    :`<button class="btn btn-primary btn-sm" onclick="saasGen(${id},'kit','build-kit')">✨ Generate build kit</button>`;
  const resBox=busy('research')?`<div style="color:var(--muted)"><span class="spin"></span> Researching the market…</div>`
    :i.research?researchView(i.research)+`<button class="btn btn-secondary btn-sm" style="margin-top:6px" onclick="saasGen(${id},'research','research')">Regenerate</button>`
    :`<button class="btn btn-primary btn-sm" onclick="saasGen(${id},'research','research')">✨ Run market research</button>`;
  const landBox=busy('landing')?`<div style="color:var(--muted)"><span class="spin"></span> Writing the landing page…</div>`
    :i.has_landing?`<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><button class="btn btn-dark btn-sm" onclick="previewLanding(${id})">Preview page ↗</button><button class="btn btn-secondary btn-sm" onclick="saasGen(${id},'landing','landing')">Regenerate</button>${i.signups?`<button class="btn btn-secondary btn-sm" onclick="viewSignups(${id},${i.signups})">✉ ${i.signups} signup${i.signups===1?'':'s'}</button>`:'<span class="badge badge-muted">0 signups</span>'}</div>`
    :`<button class="btn btn-primary btn-sm" onclick="saasGen(${id},'landing','landing')">✨ Generate landing page</button>`;
  const tasks=(i.tasks||[]).map((t,idx)=>`<div class="tasrow"><input type="checkbox" ${t.done?'checked':''} onchange="toggleTaskS(${id},${idx},this.checked)"><span style="flex:1;font-size:13.5px;${t.done?'text-decoration:line-through;color:var(--faint)':'color:var(--ink)'}">${esc(t.text)}</span><button class="icobtn d" style="width:26px;height:26px" onclick="delTaskS(${id},${idx})">✕</button></div>`).join('');
  modal(esc(i.name),`
    <p style="color:var(--muted);font-size:14.5px;margin-bottom:14px;line-height:1.55">${esc(i.solution)}</p>
    <div class="stage-bar">${stageBar}</div>
    <div class="submetrics" style="margin-bottom:10px"><span class="sm">demand <b>${i.demand}</b></span><span class="sm">WTP <b>${i.willingness_to_pay}</b></span><span class="sm">competition <b>${i.competition}</b></span><span class="sm">effort <b>${i.build_effort}</b></span><span class="sm">fit <b>${i.founder_fit}</b></span><span class="sm">score <b>${i.score}</b></span></div>
    <div class="row"><label>Target · Monetization</label><div style="font-size:13.5px">${esc(i.target_user)} · ${esc(i.monetization)} · est ${esc(i.est_mrr_range)}</div></div>
    <div class="dsec"><div class="dsec-head"><div class="t">🧰 Build kit</div></div>${kitBox}</div>
    <div class="dsec"><div class="dsec-head"><div class="t">🔍 Market research</div></div>${resBox}</div>
    <div class="dsec"><div class="dsec-head"><div class="t">🚀 Landing page</div></div>${landBox}</div>
    <div class="dsec"><div class="dsec-head"><div class="t">✅ Validation (${done}/${tot})</div></div>${checks}</div>
    <div class="dsec"><div class="dsec-head"><div class="t">📋 Build tasks</div>
      <div style="display:flex;align-items:center;gap:8px"><label style="margin:0">MRR $</label><input id="mrr-${id}" type="number" value="${i.mrr||0}" style="width:88px" onchange="saveMrr(${id})"></div></div>
      ${tasks}
      <div style="display:flex;gap:8px;margin-top:10px"><input id="newtask" placeholder="Add a build task…" onkeydown="if(event.key==='Enter')addTaskS(${id})"><button class="btn btn-secondary btn-sm" onclick="addTaskS(${id})">Add</button></div>
    </div>`,
    `<button class="btn btn-danger" onclick="delIdea(${id})" style="margin-right:auto">Delete</button>
     <button class="btn btn-secondary" onclick="closeModal()">Close</button>${i.status!=='building'?`<button class="btn btn-primary" onclick="promote(${id})">Promote to income stream</button>`:'<span class="badge badge-amber">promoted to stream</span>'}`);
}
async function delIdea(id){if(!confirm('Delete this idea permanently?'))return;
  await api.del('/api/saas/ideas/'+id);closeModal();S.ideas=S.ideas.filter(x=>x.id!==id);refreshSaasBoard();}
async function saasGen(id,kind,ep){S.saasBusy=S.saasBusy||{};S.saasBusy[id+'-'+kind]=true;ideaDetail(id);
  try{const idea=await api.post('/api/saas/ideas/'+id+'/'+ep);refreshIdea(idea);refreshSaasBoard();}
  catch(e){alert('Error: '+e.message);}
  finally{delete S.saasBusy[id+'-'+kind];ideaDetail(id);}}
function previewLanding(id){window.open('/api/saas/ideas/'+id+'/landing','_blank');}
async function viewSignups(id,count){
  const rows=await api.get('/api/saas/ideas/'+id+'/signups');
  const table=rows.length?`<table class="fl-table" style="margin-top:8px"><thead><tr><th>Email</th><th>Signed up</th></tr></thead><tbody>${
    rows.map(r=>`<tr><td>${esc(r.email)}</td><td style="color:var(--muted);font-size:13px">${r.created_at?.slice(0,16)||'—'}</td></tr>`).join('')
  }</tbody></table>`:'<div style="color:var(--faint);padding:12px 0">No signups yet</div>';
  modal(`Waitlist signups (${count})`,table,
    `<a class="btn btn-secondary" href="/api/saas/ideas/${id}/signups/csv" download>⬇ CSV</a>
     <button class="btn btn-primary" onclick="closeModal()">Close</button>`);}
async function toggleCheck(id,idx,done){const i=S.ideas.find(x=>x.id===id);i.validation[idx].done=done;
  const idea=await api.put('/api/saas/ideas/'+id,{validation:i.validation});refreshIdea(idea);}
async function moveStage(id,stage){const idea=await api.put('/api/saas/ideas/'+id,{stage});refreshIdea(idea);refreshSaasBoard();ideaDetail(id);}
async function saveMrr(id){const v=parseFloat(val('mrr-'+id))||0;const idea=await api.put('/api/saas/ideas/'+id,{mrr:v});refreshIdea(idea);refreshSaasBoard();}
async function addTaskS(id){const inp=document.getElementById('newtask');const t=inp?inp.value.trim():'';if(!t)return;
  const i=S.ideas.find(x=>x.id===id);const tasks=[...(i.tasks||[]),{text:t,done:false}];
  const idea=await api.put('/api/saas/ideas/'+id,{tasks});refreshIdea(idea);ideaDetail(id);}
async function toggleTaskS(id,idx,done){const i=S.ideas.find(x=>x.id===id);const tasks=i.tasks.map((t,k)=>k===idx?{...t,done}:t);
  const idea=await api.put('/api/saas/ideas/'+id,{tasks});refreshIdea(idea);}
async function delTaskS(id,idx){const i=S.ideas.find(x=>x.id===id);const tasks=i.tasks.filter((_,k)=>k!==idx);
  const idea=await api.put('/api/saas/ideas/'+id,{tasks});refreshIdea(idea);ideaDetail(id);}
async function promote(id){try{await api.post('/api/saas/ideas/'+id+'/promote');
  const idea=await api.put('/api/saas/ideas/'+id,{stage:'building'});refreshIdea(idea);refreshSaasBoard();ideaDetail(id);
  alert('Promoted to a tracked income stream — see the Overview map.');}catch(e){alert(e.message);}}

/* ── YouTube ── */
const QPCT={'waiting':6,'writing script':22,'recording voiceover':48,'rendering video':78,'uploading':92,'complete':100};
function qcard(v){
  const qs=v.queue_status;const tag=qs&&qs!=='done'?`<span class="qtag ${qs}">${qs==='running'?(v.queue_msg||'running'):qs}</span>`:'';
  const meta=v.error&&qs==='failed'?'':(v.script.length?v.script.length+' segments':'—');
  return `<div class="vcard" onclick="videoModal(${v.id})"><div class="t">${esc(v.title||v.topic)}</div>
    <div class="m">${tag}${meta?`<span>${meta}</span>`:''}</div></div>`;
}
function renderBoard(vids){
  return STAGES.map(stg=>{
    const items=vids.filter(v=>v.stage===stg);
    return `<div class="col"><div class="col-head">${stg}<span>${items.length}</span></div>${items.map(qcard).join('')}</div>`;
  }).join('');
}
function renderQueuePanel(snap){
  const items=snap.items||[];
  if(!items.length)return '';
  const running=items.filter(i=>i.queue_status==='running').length;
  const rows=items.map(v=>{
    const qs=v.queue_status;const pct=qs==='failed'?100:(QPCT[v.queue_msg]||(qs==='queued'?6:40));
    const barcls=qs==='running'?'run':qs==='failed'?'fail':'';
    const msg=qs==='failed'?esc(v.queue_msg||v.error||'failed'):esc(v.queue_msg||'waiting');
    return `<div class="qrow">
      <div class="qrow-top"><div class="qn">${esc(v.title||v.topic)}</div>
        <div class="qright"><span class="qs ${qs}">${qs==='running'?msg:qs}</span>
          ${qs==='failed'?`<button class="btn btn-secondary btn-sm" onclick="retryVideo(${v.id})">Retry</button>`:''}</div></div>
      <div class="qbar ${barcls}"><i style="width:${pct}%"></i></div></div>`;
  }).join('');
  return `<div class="qpanel">
    <div class="qhead"><div class="t">${running?'<span class="spin"></span>':'⏸'} Render queue <span class="qcount">${items.length} in queue</span></div>
      <button class="btn btn-secondary btn-sm" onclick="clearQueue()">Clear pending</button></div>
    ${rows}</div>`;
}
function renderYouTube(){
  if(!S.channels.length)return `
  <section class="hero" style="padding:64px 0 20px"><div class="wrap">
    <div class="eyebrow reveal in">Faceless YouTube</div>
    <h1 class="disp reveal in" style="font-size:clamp(38px,6vw,64px);letter-spacing:-.03em;line-height:1.02;margin:14px 0 0">Idea to MP4,<br>on autopilot.</h1>
    <p class="hero-sub reveal in" style="margin-top:20px;max-width:640px;margin-left:auto;margin-right:auto">Pick a niche → Gemini writes the script → edge-tts voices it → caption slides + ffmpeg render an MP4 → optional YouTube upload. No paid APIs for script→video.</p>
    <div class="reveal in" style="margin-top:28px"><button class="btn btn-primary" onclick="channelModal()">+ Create a channel</button></div>
  </div></section>`;
  const chOpts=S.channels.map(c=>`<option value="${c.id}" ${S.activeChannel===c.id?'selected':''}>${esc(c.name)}</option>`).join('');
  if(!S.activeChannel)S.activeChannel=S.channels[0].id;
  const ch=S.channels.find(c=>c.id===S.activeChannel);
  const vids=S.videos.filter(v=>v.channel_id===S.activeChannel);
  return `
  <section class="section" style="padding-top:44px"><div class="wrap">
    <div class="sec-head reveal in" style="margin-bottom:20px">
      <div><div class="eyebrow">Faceless YouTube</div><div class="sec-title disp" style="font-family:var(--disp);font-weight:600;font-size:30px;letter-spacing:-.025em;text-transform:none;color:var(--ink);margin-top:6px">${esc(ch.name)}</div></div>
      <button class="btn btn-danger btn-sm" onclick="delChannel(${ch.id})">Delete channel</button>
    </div>
    <div class="toolbar reveal in" style="margin-bottom:14px">
      <select style="width:auto" onchange="S.activeChannel=parseInt(this.value);render()">${chOpts}</select>
      <span class="badge badge-cyan">${esc(ch.niche||'no niche')}</span><span class="badge badge-muted">${esc(ch.style)}</span>
      <div style="flex:1"></div>
      <button class="btn btn-secondary btn-sm" onclick="suggestTopics(${ch.id})">💡 Suggest topics</button>
      <button class="btn btn-secondary btn-sm" onclick="videoModal(null)">+ Video</button>
    </div>
    <div class="toolbar reveal in" style="background:var(--bg-alt);border:1px solid var(--line);border-radius:16px;padding:13px 16px;margin-bottom:20px">
      <span style="font-weight:700;font-size:13.5px">⚡ Batch autopilot</span>
      <span style="color:var(--muted);font-size:13px">generate</span>
      <input id="batch-n" type="number" value="4" min="1" max="20" style="width:64px">
      <span style="color:var(--muted);font-size:13px">videos & auto-run the whole pipeline</span>
      <label style="display:flex;align-items:center;gap:7px;font-size:13px;font-weight:600;color:${S.data.youtube_upload_ready?'var(--ink-2)':'var(--faint)'};cursor:${S.data.youtube_upload_ready?'pointer':'not-allowed'}">
        <input type="checkbox" id="batch-upload" ${S.data.youtube_upload_ready?'':'disabled'} style="width:16px;height:16px;accent-color:var(--green)">
        Auto-upload ${S.data.youtube_upload_ready?`(${esc(S.data.settings.upload_privacy)})`:'· connect in Settings'}</label>
      <div style="flex:1"></div>
      <button class="btn btn-secondary btn-sm" onclick="queueAll()">Queue all pending</button>
      <button class="btn btn-primary btn-sm" id="batch-btn" onclick="batchGenerate()">✨ Generate &amp; queue</button>
    </div>
    <div id="queue-wrap"></div>
    <div id="yt-board" class="board reveal in">${renderBoard(vids)}</div>
  </div></section>`;
}

/* live queue polling */
let _qpoll=null,_qpolling=false;
function stopQueuePoll(){if(_qpoll){clearInterval(_qpoll);_qpoll=null;}}
function startQueuePoll(){stopQueuePoll();pollQueue();_qpoll=setInterval(pollQueue,2500);}
async function pollQueue(){
  if(S.tab!=='youtube'||!S.activeChannel){stopQueuePoll();return;}
  if(_qpolling)return;_qpolling=true;
  try{
    const snap=await api.get('/api/yt/queue?channel_id='+S.activeChannel);
    S.videos=await api.get('/api/yt/videos');
    const qp=document.getElementById('queue-wrap');if(qp)qp.innerHTML=renderQueuePanel(snap);
    const bd=document.getElementById('yt-board');if(bd)bd.innerHTML=renderBoard(S.videos.filter(v=>v.channel_id===S.activeChannel));
    const active=snap.items.some(i=>i.queue_status==='running'||i.queue_status==='queued');
    if(!active)stopQueuePoll();
  }catch(e){}finally{_qpolling=false;}
}
function batchUpload(){const c=document.getElementById('batch-upload');return !!(c&&c.checked);}
async function batchGenerate(){const n=parseInt(val('batch-n'))||4;const up=batchUpload();const btn=document.getElementById('batch-btn');
  btn.disabled=true;btn.innerHTML='<span class="spin"></span> Generating…';
  try{await api.post('/api/yt/batch',{channel_id:S.activeChannel,count:n,auto_run:true,do_upload:up});await render();}
  catch(e){alert('Error: '+e.message);btn.disabled=false;btn.innerHTML='✨ Generate & queue';}}
async function queueAll(){const up=batchUpload();try{const r=await api.post('/api/yt/queue/enqueue_channel/'+S.activeChannel,{do_upload:up});
    if(!r.queued)return alert('Nothing pending to queue.');await render();}catch(e){alert(e.message);}}
async function clearQueue(){try{await api.post('/api/yt/queue/clear');await render();}catch(e){alert(e.message);}}
async function retryVideo(id){try{await api.post('/api/yt/videos/'+id+'/enqueue',{do_upload:false});startQueuePoll();}catch(e){alert(e.message);}}
function channelModal(){modal('New faceless channel',`
  <div class="row"><label>Channel name</label><input id="ch-name" placeholder="e.g. Midnight Facts"></div>
  <div class="row2"><div><label>Niche</label><input id="ch-niche" placeholder="space facts, stoic wisdom…"></div><div><label>Style</label><input id="ch-style" value="top-10 list"></div></div>
  <div class="row2"><div><label>Voice (edge-tts)</label><input id="ch-voice" value="en-US-AndrewNeural"></div><div><label>Target words</label><input id="ch-words" type="number" value="220"></div></div>`,
  `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="saveChannel()">Create</button>`);}
async function saveChannel(){const b={name:val('ch-name'),niche:val('ch-niche'),style:val('ch-style')||'top-10 list',
  voice:val('ch-voice')||'en-US-AndrewNeural',target_length_words:parseInt(val('ch-words'))||220};
  if(!b.name)return alert('Name required');const c=await api.post('/api/yt/channels',b);S.activeChannel=c.id;closeModal();render();}
async function delChannel(id){if(!confirm('Delete channel and its videos?'))return;await api.del('/api/yt/channels/'+id);S.activeChannel=null;render();}
async function suggestTopics(cid){try{const r=await api.post('/api/yt/topics/'+cid);
  modal('Suggested topics',r.topics.map(t=>`<div class="vcard" onclick="createVideo(${cid},'${esc(t).replace(/'/g,"\\'")}')"><div class="t">${esc(t)}</div><div class="m">click to add to pipeline</div></div>`).join(''),
    `<button class="btn btn-secondary" onclick="closeModal()">Close</button>`);}catch(e){alert(e.message);}}
async function createVideo(cid,topic){await api.post('/api/yt/videos',{channel_id:cid,topic});closeModal();render();}
function videoModal(id){
  if(!id){modal('New video',`<div class="row"><label>Topic / working title</label><input id="v-topic" placeholder="e.g. 10 space facts that sound fake"></div>`,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="addVideo()">Add</button>`);return;}
  const v=S.videos.find(x=>x.id===id);const si=STAGES.indexOf(v.stage);
  const steps=STAGES.map((s,idx)=>`<div class="step ${idx<si?'done':idx===si?'active':''}">${s}</div>`).join('');
  const script=v.script.length?`<div class="section-title" style="margin:16px 0 10px">Script</div>`+
    v.script.map(s=>`<div style="margin-bottom:11px"><b style="font-size:13px;color:var(--sky)">${esc(s.heading)}</b><div style="font-size:13.5px;color:var(--muted);line-height:1.5">${esc(s.narration)}</div></div>`).join(''):'';
  const b=S.busy[id];
  modal(esc(v.title||v.topic),`
    <div class="pipeline-steps">${steps}</div>
    ${v.error?`<div class="hint" style="color:var(--red)">⚠ ${esc(v.error)}</div>`:''}
    ${v.youtube_id?`<div class="row"><label>Published on YouTube</label><a class="badge badge-blue" href="https://youtu.be/${esc(v.youtube_id)}" target="_blank">youtu.be/${esc(v.youtube_id)} ↗</a></div>`:''}
    ${v.title&&v.title!==v.topic?`<div class="row"><label>Title</label><div>${esc(v.title)}</div></div>`:''}
    ${v.description?`<div class="row"><label>Description</label><div style="font-size:13.5px;color:var(--muted);line-height:1.5">${esc(v.description)}</div></div>`:''}
    ${v.tags?`<div class="row"><label>Tags</label><span style="font-size:13.5px">${esc(v.tags)}</span></div>`:''}
    ${v.thumbnail_prompt?`<div class="row"><label>Thumbnail prompt</label><div style="font-size:13.5px;color:var(--muted)">${esc(v.thumbnail_prompt)}</div></div>`:''}
    ${script}
    ${v.video_path?`<div style="margin-top:16px"><video src="/api/yt/videos/${id}/file" controls style="width:100%;border-radius:12px"></video></div>`:''}`,
    `<div style="display:flex;gap:8px;flex-wrap:wrap;width:100%;justify-content:flex-end">
      ${b?`<span style="color:var(--muted);align-self:center;font-weight:600"><span class="spin"></span> ${esc(b)}…</span>`:`
      <button class="btn btn-secondary btn-sm" onclick="ytStep(${id},'script')">1 · Script</button>
      <button class="btn btn-secondary btn-sm" onclick="ytStep(${id},'voice')" ${!v.script.length?'disabled':''}>2 · Voice</button>
      <button class="btn btn-secondary btn-sm" onclick="ytStep(${id},'render')" ${!v.audio_path?'disabled':''}>3 · Render</button>
      <button class="btn btn-primary btn-sm" onclick="ytStep(${id},'pipeline')">⚡ Auto (1→3)</button>
      ${v.video_path&&!v.youtube_id?`<button class="btn btn-dark btn-sm" onclick="ytStep(${id},'upload')">⬆ Upload</button>`:''}
      ${v.video_path?`<a class="btn btn-secondary btn-sm" href="/api/yt/videos/${id}/file" download>⬇ MP4</a>`:''}`}
    </div>`);}
async function addVideo(){const topic=val('v-topic');if(!topic)return;await api.post('/api/yt/videos',{channel_id:S.activeChannel,topic});closeModal();render();}
async function ytStep(id,step){S.busy[id]={script:'Writing script',voice:'Generating voiceover',render:'Rendering video',upload:'Uploading to YouTube',pipeline:'Running full pipeline'}[step];
  videoModal(id);
  try{const ep=step==='pipeline'?'pipeline':step;const v=await api.post(`/api/yt/videos/${id}/${ep}`);
    const idx=S.videos.findIndex(x=>x.id===id);if(idx>=0)S.videos[idx]=v;delete S.busy[id];videoModal(id);
    S.videos=await api.get('/api/yt/videos');}
  catch(e){delete S.busy[id];alert('Error: '+e.message);S.videos=await api.get('/api/yt/videos');videoModal(id);}}

/* ── Settings ── */
function renderSettings(){const s=S.data.settings;
  return `
  <section class="hero" style="padding:60px 0 16px"><div class="wrap">
    <div class="eyebrow reveal in">System</div>
    <h1 class="disp reveal in" style="font-size:clamp(36px,5.5vw,58px);letter-spacing:-.03em;margin:14px 0 0">Settings</h1>
  </div></section>
  <section class="section tight"><div class="wrap" style="max-width:680px">
    <div class="card card-pad reveal in" style="margin-bottom:18px">
      <div class="section-title" style="margin-bottom:16px">AI · Gemini</div>
      <div class="hint">Reuses your <code>GEMINI_API_KEY</code> env var or a key saved here. Model: <code>${esc(s.model)}</code>. Source: <b>${esc(s.api_key_source)}</b>.</div>
      <div class="row"><label>Override API key (optional)</label><input id="set-key" type="password" placeholder="${s.api_key_set?'key is set — leave blank to keep':'paste Gemini key'}"></div>
      <div class="row2"><div><label>Model</label><input id="set-model" value="${esc(s.model)}"></div><div><label>Default TTS voice</label><input id="set-voice" value="${esc(s.tts_voice)}"></div></div>
      <div class="row"><label>Video resolution</label><input id="set-res" value="${esc(s.video_resolution)}"></div>
      <button class="btn btn-primary" onclick="saveSettings()">Save settings</button>
    </div>
    <div class="card card-pad reveal in" style="margin-bottom:18px">
      <div class="section-title" style="margin-bottom:14px">Betting · Odds API</div>
      <div class="hint">Powers the live arb scanner. Status: <b style="color:${s.odds_api_key_set?'var(--green-ink)':'var(--amber)'}">${s.odds_api_key_set?'connected':'not set'}</b>. Free key at <code>the-odds-api.com</code> (500 req/mo).</div>
      <div class="row"><label>Odds API key</label><input id="set-odds" type="password" placeholder="${s.odds_api_key_set?'key is set — leave blank to keep':'paste Odds API key'}"></div>
      <button class="btn btn-primary" onclick="saveSettings()">Save settings</button>
    </div>
    <div class="card card-pad reveal in" style="--d:80ms">
      <div class="section-title" style="margin-bottom:14px">YouTube upload</div>
      <div class="hint">Status: <b style="color:${S.data.youtube_upload_ready?'var(--green-ink)':'var(--amber)'}">${S.data.youtube_upload_ready?'connected':'not configured'}</b>.
      ${S.data.youtube_upload_ready?'Auto-upload is available in the Faceless YT batch bar. The first upload opens a one-time browser consent.':'To enable auto-upload: enable the YouTube Data API v3, create an OAuth <b>desktop</b> client, and drop the JSON at <code>data/client_secret.json</code>.'}</div>
      <div class="row2" style="margin-bottom:0"><div><label>Auto-upload privacy</label><select id="set-privacy">
        <option value="unlisted" ${s.upload_privacy==='unlisted'?'selected':''}>Unlisted</option>
        <option value="private" ${s.upload_privacy==='private'?'selected':''}>Private</option>
        <option value="public" ${s.upload_privacy==='public'?'selected':''}>Public</option>
      </select></div><div style="display:flex;align-items:flex-end"><button class="btn btn-primary" style="width:100%" onclick="saveSettings()">Save privacy</button></div></div>
    </div>
  </div></section>`;}
async function saveSettings(){const b={model:val('set-model'),tts_voice:val('set-voice'),video_resolution:val('set-res')};
  const k=val('set-key');if(k)b.api_key=k;
  const p=val('set-privacy');if(p)b.upload_privacy=p;
  const ok=val('set-odds');if(ok)b.odds_api_key=ok;
  await api.post('/api/settings',b);await loadDash();render();alert('Saved.');}

/* ── Betting ── */
const BOOK_STATUS={active:'badge-green',limited:'badge-amber',gubbed:'badge-purple',banned:'badge-red',closed:'badge-muted'};
function bookName(id){const b=S.books.find(x=>x.id===id);return b?b.name:'—';}

function renderCalc(){
  const legs=S.calc.legs.map((lg,i)=>{
    const bookOpts=`<option value="">book…</option>`+S.books.map(b=>`<option value="${b.id}" ${lg.book==b.id?'selected':''}>${esc(b.name)}</option>`).join('');
    return `<div class="calc-leg">
      <span class="calc-i">${i+1}</span>
      <input placeholder="Outcome (e.g. Home)" value="${esc(lg.sel)}" oninput="S.calc.legs[${i}].sel=this.value">
      <select onchange="S.calc.legs[${i}].book=this.value">${bookOpts}</select>
      <input type="number" step="0.01" placeholder="odds" value="${lg.odds}" oninput="S.calc.legs[${i}].odds=this.value;calcRecalc()">
      <span class="calc-stake" id="cstake-${i}">—</span>
      ${S.calc.legs.length>2?`<button class="icobtn d" title="Remove" onclick="calcDelLeg(${i})">✕</button>`:'<span></span>'}
    </div>`;}).join('');
  return `
    <div class="calc-head-row"><label style="margin:0">Total stake</label>
      <input type="number" step="1" value="${S.calc.total}" oninput="S.calc.total=this.value;calcRecalc()" style="width:120px">
      <button class="btn btn-secondary btn-sm" onclick="calcAddLeg()">+ Add outcome</button></div>
    <div class="calc-legs">${legs}</div>
    <div class="calc-out" id="calc-out"></div>`;
}
function calcAddLeg(){S.calc.legs.push({sel:'',odds:'',book:''});document.getElementById('calc-body').innerHTML=renderCalc();calcRecalc();}
function calcDelLeg(i){S.calc.legs.splice(i,1);document.getElementById('calc-body').innerHTML=renderCalc();calcRecalc();}
function calcRecalc(){
  const legs=S.calc.legs,T=parseFloat(S.calc.total)||0;
  const inv=legs.map(l=>{const o=parseFloat(l.odds);return o>1?1/o:0;});
  const sum=inv.reduce((a,b)=>a+b,0);
  legs.forEach((l,i)=>{const el=document.getElementById('cstake-'+i);if(!el)return;
    const st=sum>0&&inv[i]>0?T*inv[i]/sum:0;el.textContent=st?('$'+st.toFixed(2)):'—';});
  const out=document.getElementById('calc-out');if(!out)return;
  if(sum<=0||legs.some(l=>!(parseFloat(l.odds)>1))){out.innerHTML=`<span class="calc-hint">Enter decimal odds for every outcome to see the split.</span>`;return;}
  const ret=T/sum,profit=ret-T,roi=(1/sum-1)*100,arb=sum<1;
  out.innerHTML=`
    <div class="calc-metrics">
      <div><div class="cm-n" style="color:${arb?'var(--green)':'var(--red)'}">${(sum*100).toFixed(2)}%</div><div class="cm-l">Book margin</div></div>
      <div><div class="cm-n">$${ret.toFixed(2)}</div><div class="cm-l">Return each way</div></div>
      <div><div class="cm-n" style="color:${profit>=0?'var(--green)':'var(--red)'}">${profit>=0?'+':''}$${profit.toFixed(2)}</div><div class="cm-l">Profit</div></div>
      <div><div class="cm-n" style="color:${roi>=0?'var(--green)':'var(--red)'}">${roi>=0?'+':''}${roi.toFixed(2)}%</div><div class="cm-l">ROI</div></div>
    </div>
    <div class="calc-flag ${arb?'ok':'bad'}">${arb?'✓ Arbitrage — profit on every outcome':'✗ No arb — under 100% book margin needed'}</div>
    <div style="margin-top:12px"><button class="btn btn-primary btn-sm" onclick="saveArb()" ${arb?'':'disabled'}>Save as tracked arb →</button></div>`;
}
async function saveArb(){
  const T=parseFloat(S.calc.total)||0,legs=S.calc.legs;
  const inv=legs.map(l=>{const o=parseFloat(l.odds);return o>1?1/o:0;});
  const sum=inv.reduce((a,b)=>a+b,0);
  if(!(sum>0&&sum<1))return alert('Not an arbitrage — check the odds.');
  const ev=(S.calc.event||'').trim()||'Untitled arb';
  const outLegs=legs.map((l,i)=>({bookmaker_id:l.book?parseInt(l.book):null,selection:l.sel||('Outcome '+(i+1)),
    odds:parseFloat(l.odds),stake:Math.round(T*inv[i]/sum*100)/100}));
  await api.post('/api/bet/arbs',{event:ev,stake_total:T,profit_pct:(1/sum-1)*100,guaranteed_profit:T/sum-T,legs:outLegs});
  render();
}

function renderScanner(){
  const s=S.betSummary||{};
  if(!s.odds_ready){
    return `<section class="section tight"><div class="wrap">
      <div class="sec-head reveal in"><div><div class="eyebrow">Live</div><div class="sec-title">Arb scanner</div>
        <div class="sec-sub">Auto-find guaranteed-profit markets from live bookmaker odds.</div></div></div>
      <div class="card card-pad reveal in">
        <div class="hint">Add a free <b>Odds API</b> key to enable scanning. Grab one at <code>the-odds-api.com</code> (500 free requests/month), then paste it below.</div>
        <div style="display:flex;gap:10px;flex-wrap:wrap"><input id="odds-key" type="password" placeholder="paste Odds API key" style="max-width:340px"><button class="btn btn-primary" onclick="saveOddsKey()">Save key</button></div>
      </div></div></section>`;
  }
  const chips=S.scanSports.length
    ? `<div class="chips">${S.scanSports.map(sp=>`<button class="chip-toggle ${S.scanSelected.includes(sp.key)?'on':''}" data-key="${sp.key}" onclick="toggleSport('${sp.key}')">${esc(sp.title)}</button>`).join('')}</div>`
    : `<div style="color:var(--muted);font-size:13.5px;margin-bottom:14px">Click “Load sports” to choose what to scan.</div>`;
  const results=S.scanResults.length
    ? S.scanResults.map((r,idx)=>`
      <div class="scan-card">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
          <div><div style="font-weight:700;font-size:15px">${esc(r.event)}</div>
            <div style="font-size:12px;color:var(--muted)">${esc(r.sport)}${r.commence_time?' · '+new Date(r.commence_time).toLocaleString('en-AU',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'}):''}</div></div>
          <span class="badge badge-green" style="font-size:13px">+${Number(r.profit_pct).toFixed(2)}%</span></div>
        <div style="margin:10px 0">${r.legs.map(l=>`<div class="scan-leg"><span><b>${esc(l.selection)}</b> <span style="color:var(--faint)">${esc(l.bookmaker)}</span></span><span class="mono" style="font-weight:700">@ ${Number(l.odds).toFixed(2)}</span></div>`).join('')}</div>
        <div style="display:flex;gap:8px"><button class="btn btn-secondary btn-sm" onclick="loadArbToCalc(${idx})">Load into calculator</button>
          <button class="btn btn-primary btn-sm" onclick="saveScanArb(${idx})">Save as tracked arb</button></div>
      </div>`).join('')
    : `<div style="color:var(--muted);font-size:14px;padding:6px 0">No arbs found yet — pick sports and hit “Scan for arbs”. True arbs are rare; near-misses won't show.</div>`;
  return `<section class="section tight"><div class="wrap">
    <div class="sec-head reveal in"><div><div class="eyebrow">Live</div><div class="sec-title">Arb scanner</div>
      <div class="sec-sub">Pulls live AU bookmaker odds and finds guaranteed-profit markets.</div></div>
      ${S.scanQuota&&S.scanQuota.remaining?`<span class="badge badge-muted">${S.scanQuota.remaining} API credits left</span>`:''}</div>
    <div class="card card-pad reveal in">
      <div style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:8px">
        <button class="btn btn-secondary btn-sm" onclick="loadSports()">${S.scanSports.length?'Reload sports':'Load sports'}</button>
        <label style="margin:0">Min profit %</label><input type="number" step="0.1" value="${S.scanMinProfit}" oninput="S.scanMinProfit=this.value" style="width:88px">
        <div style="flex:1"></div>
        <button class="btn btn-primary btn-sm" id="scan-btn" onclick="runScan()" ${S.scanSelected.length?'':'disabled'}>⚡ Scan for arbs</button></div>
      ${chips}${results}
    </div></div></section>`;
}
async function saveOddsKey(){const k=val('odds-key');if(!k)return alert('Paste a key first.');await api.post('/api/settings',{odds_api_key:k});render();}
async function loadSports(){try{const sp=await api.get('/api/bet/scan/sports');S.scanSports=sp;
  if(!S.scanSelected.length){const pref=['aussierules_afl','rugbyleague_nrl','soccer_epl','basketball_nba'];
    S.scanSelected=sp.filter(x=>pref.includes(x.key)).map(x=>x.key);
    if(!S.scanSelected.length)S.scanSelected=sp.slice(0,3).map(x=>x.key);}
  render();}catch(e){alert(e.message);}}
function toggleSport(key){const i=S.scanSelected.indexOf(key);if(i>=0)S.scanSelected.splice(i,1);else S.scanSelected.push(key);
  document.querySelectorAll('.chip-toggle').forEach(el=>el.classList.toggle('on',S.scanSelected.includes(el.dataset.key)));
  const sb=document.getElementById('scan-btn');if(sb)sb.disabled=!S.scanSelected.length;}
async function runScan(){const btn=document.getElementById('scan-btn');if(!S.scanSelected.length)return;
  btn.disabled=true;btn.innerHTML='<span class="spin"></span> Scanning…';
  try{const r=await api.post('/api/bet/scan',{sports:S.scanSelected,regions:'au',min_profit:parseFloat(S.scanMinProfit)||0});
    S.scanResults=r.arbs;S.scanQuota=r.quota;render();
    document.querySelector('#content .sec-title')&&document.querySelectorAll('.sec-title').forEach(t=>{if(t.textContent==='Arb scanner')t.scrollIntoView({behavior:'smooth',block:'start'});});}
  catch(e){alert('Scan error: '+e.message);btn.disabled=false;btn.innerHTML='⚡ Scan for arbs';}}
function loadArbToCalc(idx){const r=S.scanResults[idx];S.calc.event=r.event;
  S.calc.legs=r.legs.map(l=>({sel:l.selection,odds:String(l.odds),book:''}));
  render().then(()=>document.getElementById('calc-body')?.scrollIntoView({behavior:'smooth',block:'center'}));}
async function saveScanArb(idx){const r=S.scanResults[idx];const T=100;
  const inv=r.legs.map(l=>1/l.odds);const sum=inv.reduce((a,b)=>a+b,0);
  const legs=r.legs.map((l,i)=>{const bk=S.books.find(b=>b.name.toLowerCase()===String(l.bookmaker).toLowerCase());
    return {bookmaker_id:bk?bk.id:null,selection:l.selection+' — '+l.bookmaker,odds:l.odds,stake:Math.round(T*inv[i]/sum*100)/100};});
  await api.post('/api/bet/arbs',{event:r.event,sport:r.sport,stake_total:T,profit_pct:r.profit_pct,guaranteed_profit:T/sum-T,legs});
  alert('Saved as a tracked arb (staked to $'+T+' — edit stakes to taste).');render();}

function renderBetting(){
  const s=S.betSummary||{};
  const books=S.books.map(b=>`
    <div class="card card-pad" style="padding:18px 20px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px">
        <div><div class="card-title" style="font-size:17px">${esc(b.name)}</div>
          <div style="margin-top:6px"><span class="badge ${BOOK_STATUS[b.status]||'badge-muted'}">${b.status}</span></div></div>
        <div style="text-align:right"><div style="font-family:var(--disp);font-weight:600;font-size:22px">$${fmt(b.balance)}</div>
          <div style="font-size:11px;color:var(--faint);font-weight:700;text-transform:uppercase;letter-spacing:.08em">balance</div></div>
      </div>
      ${b.notes?`<div style="font-size:12.5px;color:var(--muted);margin-top:10px">${esc(b.notes)}</div>`:''}
      <div style="display:flex;gap:7px;margin-top:14px">
        <button class="btn btn-secondary btn-sm" onclick="bookModal(${b.id})">Edit</button>
        <button class="btn btn-danger btn-sm" onclick="delBook(${b.id})">Delete</button></div>
    </div>`).join('');

  const arbs=S.arbs.map(a=>{
    const realized=a.legs.reduce((t,l)=>t+(['won','lost','void'].includes(l.status)?l.profit:0),0);
    const settled=a.legs.length>0&&a.legs.every(l=>l.status!=='pending');
    const legs=a.legs.map(l=>`
      <div class="leg-row">
        <div><b>${esc(l.selection||'—')}</b><div style="font-size:11.5px;color:var(--faint)">${esc(bookName(l.bookmaker_id))}</div></div>
        <div class="mono" style="color:var(--muted)">@ ${Number(l.odds).toFixed(2)}</div>
        <div style="font-weight:700">$${fmt(l.stake)}</div>
        <div style="font-weight:700;color:${l.status==='won'?'var(--green)':l.status==='lost'?'var(--red)':'var(--muted)'}">${l.status==='pending'?'—':(l.profit>=0?'+':'')+'$'+fmt(l.profit)}</div>
        <div class="leg-set">
          <button class="mini ${l.status==='won'?'on-won':''}" onclick="settleLeg(${l.id},'won')">W</button>
          <button class="mini ${l.status==='lost'?'on-lost':''}" onclick="settleLeg(${l.id},'lost')">L</button>
          <button class="mini ${l.status==='void'?'on-void':''}" onclick="settleLeg(${l.id},'void')">V</button></div>
      </div>`).join('');
    return `<div class="arbcard">
      <div class="arb-head">
        <div><div class="card-title">${esc(a.event)}</div>
          <div style="font-size:12.5px;color:var(--muted);margin-top:4px">$${fmt(a.stake_total)} staked · expected ${a.profit_pct>=0?'+':''}${Number(a.profit_pct).toFixed(2)}% · guaranteed $${fmt(a.guaranteed_profit)}</div></div>
        <div style="text-align:right">
          <div style="font-family:var(--disp);font-weight:600;font-size:20px;color:${realized>=0?'var(--green)':'var(--red)'}">${settled?((realized>=0?'+':'')+'$'+fmt(realized)):'in play'}</div>
          <div style="font-size:11px;color:var(--faint);font-weight:700;text-transform:uppercase">${settled?'realised':'open'}</div></div>
      </div>${legs}
      <div style="text-align:right;margin-top:10px"><button class="btn btn-danger btn-sm" onclick="delArb(${a.id})">Delete</button></div>
    </div>`;}).join('');

  const singles=S.singleBets.map(b=>`
    <div class="leg-row" style="grid-template-columns:1.4fr .7fr 74px 88px auto 32px">
      <div><b>${esc(b.selection||b.event||'Bet')}</b><div style="font-size:11.5px;color:var(--faint)">${esc(bookName(b.bookmaker_id))}</div></div>
      <div class="mono" style="color:var(--muted)">@ ${Number(b.odds).toFixed(2)}</div>
      <div style="font-weight:700">$${fmt(b.stake)}</div>
      <div style="font-weight:700;color:${b.status==='won'?'var(--green)':b.status==='lost'?'var(--red)':'var(--muted)'}">${b.status==='pending'?'—':(b.profit>=0?'+':'')+'$'+fmt(b.profit)}</div>
      <div class="leg-set">
        <button class="mini ${b.status==='won'?'on-won':''}" onclick="settleLeg(${b.id},'won')">W</button>
        <button class="mini ${b.status==='lost'?'on-lost':''}" onclick="settleLeg(${b.id},'lost')">L</button>
        <button class="mini ${b.status==='void'?'on-void':''}" onclick="settleLeg(${b.id},'void')">V</button></div>
      <button class="icobtn d" onclick="delBet(${b.id})">✕</button>
    </div>`).join('');

  return `
  <section class="hero" style="padding:56px 0 8px"><div class="wrap">
    <div class="eyebrow reveal in">Sports betting · arbitrage</div>
    <h1 class="disp reveal in" style="font-size:clamp(34px,5.5vw,58px);letter-spacing:-.03em;margin:12px 0 0">Bet both sides.<br>Bank the spread.</h1>
  </div></section>

  <section class="section tight"><div class="wrap">
    <div class="trio reveal in" style="grid-template-columns:repeat(4,1fr)">
      <div class="statc ink"><div class="top"><div class="lbl">Bankroll</div><div class="ico">🏦</div></div><div class="val tnum"><span class="cur">$</span>${fmt(s.bankroll)}</div><div class="foot">${s.book_count||0} book${s.book_count===1?'':'s'}</div></div>
      <div class="statc green"><div class="top"><div class="lbl">Realised profit</div><div class="ico">↗</div></div><div class="val tnum"><span class="cur">$</span>${fmt(s.realized_profit)}</div><div class="foot">${(s.roi||0)>=0?'+':''}${Number(s.roi||0).toFixed(2)}% ROI on $${fmt(s.turnover)}</div></div>
      <div class="statc ink"><div class="top"><div class="lbl">In play</div><div class="ico">◷</div></div><div class="val tnum"><span class="cur">$</span>${fmt(s.pending_stake)}</div><div class="foot">${s.open_bets||0} open bet${s.open_bets===1?'':'s'}</div></div>
      <div class="statc green"><div class="top"><div class="lbl">This month</div><div class="ico">◆</div></div><div class="val tnum"><span class="cur">$</span>${fmt(s.month_profit)}</div><div class="foot">realised P&amp;L</div></div>
    </div>
  </div></section>

  ${S.betHistory&&S.betHistory.labels.length?`
  <section class="section tight band"><div class="wrap">
    <div class="sec-head reveal in"><div><div class="eyebrow">Performance</div><div class="sec-title">Cumulative P&L</div></div></div>
    <div class="card card-pad reveal in"><canvas id="bet-chart" style="max-height:220px"></canvas></div>
  </div></section>`:''}

  ${renderScanner()}

  <section class="section band tight"><div class="wrap">
    <div class="sec-head reveal in"><div><div class="eyebrow">Tool</div><div class="sec-title">Arbitrage calculator</div></div></div>
    <div class="grid reveal in" style="grid-template-columns:1.4fr 1fr;gap:18px">
      <div class="card card-pad">
        <div class="card-head" style="margin-bottom:12px"><div class="card-title">Arb calculator</div></div>
        <div class="row" style="max-width:440px"><label>Event / match</label><input placeholder="e.g. Sinner vs Alcaraz" value="${esc(S.calc.event)}" oninput="S.calc.event=this.value"></div>
        <div id="calc-body">${renderCalc()}</div>
      </div>
      <div class="card card-pad">
        <div class="card-head" style="margin-bottom:12px"><div class="card-title">Kelly criterion</div><div class="card-sub">Optimal stake sizing</div></div>
        <div class="row"><label>Bankroll ($)</label><input id="kelly-bank" type="number" value="${fmt(s.bankroll)||100}" oninput="kellyCalc()"></div>
        <div class="row2">
          <div><label>Decimal odds</label><input id="kelly-odds" type="number" step="0.01" placeholder="e.g. 2.10" oninput="kellyCalc()"></div>
          <div><label>Win probability (%)</label><input id="kelly-prob" type="number" step="1" min="1" max="99" placeholder="e.g. 55" oninput="kellyCalc()"></div>
        </div>
        <div id="kelly-out" class="kelly-out"><span style="color:var(--muted);font-size:13.5px">Enter odds + your estimated win % to see optimal stake.</span></div>
      </div>
    </div>
  </div></section>

  <section class="section tight"><div class="wrap">
    <div class="sec-head reveal in"><div><div class="eyebrow">Bankroll</div><div class="sec-title">Bookmaker accounts</div></div>
      <button class="btn btn-dark btn-sm" onclick="bookModal()">+ Add bookmaker</button></div>
    ${S.books.length?`<div class="grid reveal in">${books}</div>`:`<div class="empty"><div class="ico">🏦</div><div class="big">No bookmakers yet</div>Add the accounts you bet from to track balances and gubbings.</div>`}
  </div></section>

  <section class="section band"><div class="wrap">
    <div class="sec-head reveal in"><div><div class="eyebrow">Tracker</div><div class="sec-title">Tracked arbs</div></div></div>
    ${S.arbs.length?`<div class="reveal in">${arbs}</div>`:`<div class="empty"><div class="ico">📈</div><div class="big">No arbs tracked</div>Build one with the calculator above and hit “Save as tracked arb”.</div>`}
    <div class="sec-head reveal in" style="margin-top:32px"><div><div class="eyebrow">Tracker</div><div class="sec-title">Single bets</div></div>
      <button class="btn btn-dark btn-sm" onclick="betModal()">+ Log bet</button></div>
    ${S.singleBets.length?`<div class="card reveal in" style="padding:4px 18px">${singles}</div>`:`<div style="color:var(--muted);font-size:14px">No standalone bets logged.</div>`}
  </div></section>
  <footer><div class="wrap"><span>Income Hub · Betting</span><span>Arb responsibly — expect account limits</span></div></footer>`;
}

function bookModal(id){const b=id?S.books.find(x=>x.id===id):null;const v=(f,d='')=>b?(b[f]??d):d;
  const sts=['active','limited','gubbed','banned','closed'].map(x=>`<option ${v('status','active')===x?'selected':''}>${x}</option>`).join('');
  modal(`${b?'Edit':'Add'} bookmaker`,`
    <div class="row"><label>Name</label><input id="bk-name" value="${esc(v('name'))}" placeholder="e.g. Sportsbet"></div>
    <div class="row2"><div><label>Balance ($)</label><input id="bk-bal" type="number" value="${v('balance',0)}"></div>
      <div><label>Status</label><select id="bk-status">${sts}</select></div></div>
    <div class="row"><label>Notes</label><textarea id="bk-notes">${esc(v('notes'))}</textarea></div>`,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="saveBook(${id||'null'})">Save</button>`);}
async function saveBook(id){const b={name:val('bk-name'),balance:parseFloat(val('bk-bal'))||0,status:val('bk-status'),notes:val('bk-notes')};
  if(!b.name)return alert('Name required');if(id)await api.put('/api/bet/books/'+id,b);else await api.post('/api/bet/books',b);closeModal();render();}
async function delBook(id){if(!confirm('Delete this bookmaker?'))return;await api.del('/api/bet/books/'+id);render();}

function betModal(){const bookOpts=`<option value="">—</option>`+S.books.map(b=>`<option value="${b.id}">${esc(b.name)}</option>`).join('');
  modal('Log a bet',`
    <div class="row2"><div><label>Event</label><input id="bt-ev" placeholder="Match / event"></div><div><label>Selection</label><input id="bt-sel" placeholder="e.g. Over 2.5"></div></div>
    <div class="row2"><div><label>Bookmaker</label><select id="bt-book">${bookOpts}</select></div><div><label>Status</label><select id="bt-status"><option>pending</option><option>won</option><option>lost</option><option>void</option></select></div></div>
    <div class="row2"><div><label>Odds</label><input id="bt-odds" type="number" step="0.01"></div><div><label>Stake ($)</label><input id="bt-stake" type="number"></div></div>`,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="saveBet()">Save</button>`);}
async function saveBet(){const b={event:val('bt-ev'),selection:val('bt-sel'),bookmaker_id:val('bt-book')?parseInt(val('bt-book')):null,
  status:val('bt-status'),odds:parseFloat(val('bt-odds'))||0,stake:parseFloat(val('bt-stake'))||0};
  await api.post('/api/bet/bets',b);closeModal();render();}
async function settleLeg(id,status){await api.put('/api/bet/bets/'+id,{status});render();}
async function delArb(id){if(!confirm('Delete this arb and its legs?'))return;await api.del('/api/bet/arbs/'+id);render();}
async function delBet(id){if(!confirm('Delete this bet?'))return;await api.del('/api/bet/bets/'+id);render();}
async function syncBetting(){try{const st=await api.post('/api/bet/sync');alert(`Synced this month's betting P&L ($${fmt(st.monthly_revenue)}) to the Overview map.`);}catch(e){alert(e.message);}}

function initBetChart(){
  const c=document.getElementById('bet-chart');if(!c||!S.betHistory)return;
  const h=S.betHistory;
  const ctx=c.getContext('2d');
  const last=h.values[h.values.length-1]||0;
  const col=last>=0?'#00a862':'#ff3b30';
  const g=ctx.createLinearGradient(0,0,0,220);
  g.addColorStop(0,last>=0?'rgba(0,168,98,.22)':'rgba(255,59,48,.16)');g.addColorStop(1,'rgba(0,0,0,0)');
  Chart.defaults.color='#86868b';Chart.defaults.font.family="'Manrope',sans-serif";Chart.defaults.font.size=11;
  new Chart(c,{type:'line',data:{labels:h.labels,datasets:[{label:'Cumulative P&L',data:h.values,
    borderColor:col,backgroundColor:g,fill:true,tension:.35,borderWidth:2.5,
    pointRadius:0,pointHoverRadius:5,pointBackgroundColor:col,pointBorderColor:'#fff',pointBorderWidth:2}]},
    options:{maintainAspectRatio:false,plugins:{legend:{display:false},
      tooltip:{backgroundColor:'#1d1d1f',padding:10,cornerRadius:10,titleColor:'#fff',bodyColor:col,displayColors:false,
        callbacks:{label:c=>' P&L: $'+Number(c.parsed.y).toFixed(2)}}},
      scales:{x:{grid:{display:false},border:{display:false},ticks:{color:'#86868b',maxTicksLimit:8}},
        y:{grid:{color:'rgba(0,0,0,.06)'},border:{display:false},ticks:{color:'#86868b',callback:v=>'$'+v.toFixed(0)}}}}})}

function kellyCalc(){
  const bank=parseFloat(document.getElementById('kelly-bank')?.value)||0;
  const odds=parseFloat(document.getElementById('kelly-odds')?.value)||0;
  const probPct=parseFloat(document.getElementById('kelly-prob')?.value)||0;
  const out=document.getElementById('kelly-out');if(!out)return;
  if(!odds||odds<=1||!probPct){out.innerHTML='<span style="color:var(--muted);font-size:13.5px">Enter odds + your estimated win % to see optimal stake.</span>';return;}
  const p=probPct/100,q=1-p,b=odds-1;
  const f=(b*p-q)/b;
  const ev=(p*b-q)*100;
  const stake=bank*Math.max(0,f);
  const halfKelly=stake/2;
  const col=f>0?'var(--green)':'var(--red)';
  out.innerHTML=`
    <div class="calc-metrics" style="grid-template-columns:repeat(3,1fr)">
      <div><div class="cm-n" style="color:${col}">${(f*100).toFixed(1)}%</div><div class="cm-l">Kelly fraction</div></div>
      <div><div class="cm-n" style="color:${col}">$${stake.toFixed(2)}</div><div class="cm-l">Full Kelly stake</div></div>
      <div><div class="cm-n" style="color:${ev>=0?'var(--green)':'var(--red)'}">${ev>=0?'+':''}${ev.toFixed(1)}%</div><div class="cm-l">Edge per $100</div></div>
    </div>
    <div class="calc-flag ${f>0?'ok':'bad'}" style="margin-top:12px">${f>0?`✓ Positive edge — recommended stake: $${halfKelly.toFixed(2)} (half-Kelly, safer)`:'✗ Negative edge — do not bet at these odds/probability'}</div>
    ${f>0?`<div style="font-size:12.5px;color:var(--muted);margin-top:8px">Half-Kelly ($${halfKelly.toFixed(2)}) reduces variance while keeping ~75% of full EV. Only bet when you have genuine edge.</div>`:''}`}

/* ── Freelance tracker ── */
const FL_PROJ_STATUS={lead:'badge-muted',active:'badge-green',done:'badge-blue',cancelled:'badge-red'};
const FL_INV_STATUS={draft:'inv-draft',sent:'inv-sent',paid:'inv-paid',overdue:'inv-overdue'};

function clientName(id){const c=S.fl.clients.find(x=>x.id===id);return c?c.name:'—';}
function projectName(id){const p=S.fl.projects.find(x=>x.id===id);return p?p.name:'—';}

function projectValue(p){return p.rate_type==='hourly'?p.rate*(p.hours_logged||0):p.rate;}

function renderFreelance(){
  const s=S.fl.summary||{};
  const activeProjects=S.fl.projects.filter(p=>p.status==='active');
  const projRows=S.fl.projects.map(p=>{
    const v=projectValue(p);
    const client=clientName(p.client_id);
    return `<tr>
      <td><div style="font-weight:600">${esc(p.name)}</div><div style="font-size:12px;color:var(--faint)">${esc(client)}</div></td>
      <td><span class="badge ${FL_PROJ_STATUS[p.status]||'badge-muted'}">${p.status}</span></td>
      <td>${p.rate_type==='hourly'?`$${fmt(p.rate)}/hr · ${p.hours_logged||0}h`:`$${fmt(p.rate)} fixed`}</td>
      <td style="font-family:var(--disp);font-weight:600;color:${v>0?'var(--green-ink)':'var(--faint)'}">$${fmt(v)}</td>
      <td>${p.due_date?`<span style="font-size:12.5px;color:var(--muted)">${p.due_date}</span>`:''}</td>
      <td>
        <div style="display:flex;gap:5px">
          ${['lead','active','done','cancelled'].map(st=>`<button class="proj-status-btn ${p.status===st?'on':''}" onclick="setProjectStatus(${p.id},'${st}')">${st}</button>`).join('')}
          <button class="icobtn d" onclick="deleteProject(${p.id})">✕</button>
        </div>
      </td>
    </tr>`;}).join('');

  const invRows=S.fl.invoices.map(inv=>{
    const proj=projectName(inv.project_id);
    return `<tr>
      <td><div style="font-weight:600">$${fmt(inv.amount)}</div></td>
      <td><div style="font-size:13px">${esc(proj)}</div></td>
      <td><span class="inv-status ${FL_INV_STATUS[inv.status]||'inv-draft'}">${inv.status}</span></td>
      <td style="font-size:12.5px;color:var(--muted)">${inv.due_date||'—'}</td>
      <td style="font-size:12.5px;color:var(--muted)">${inv.paid_at?inv.paid_at.slice(0,10):'—'}</td>
      <td>
        <div style="display:flex;gap:5px;justify-content:flex-end">
          ${inv.status!=='paid'?`<button class="mini" onclick="markInvoicePaid(${inv.id})">Mark paid</button>`:''}
          <button class="icobtn d" onclick="deleteInvoice(${inv.id})">✕</button>
        </div>
      </td>
    </tr>`;}).join('');

  const clientCards=S.fl.clients.map(c=>`
    <div class="card card-pad" style="padding:18px 20px">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:10px">
        <div><div class="card-title" style="font-size:17px">${esc(c.name)}</div>
          ${c.contact?`<div style="font-size:12.5px;color:var(--muted);margin-top:3px">${esc(c.contact)}</div>`:''}
          ${c.email?`<div style="font-size:12px;color:var(--faint)">${esc(c.email)}</div>`:''}
        </div>
        <div style="display:flex;gap:6px">
          ${c.url?`<a class="badge badge-blue" href="${esc(c.url)}" target="_blank">Site ↗</a>`:''}
          <button class="btn btn-secondary btn-sm" onclick="clientModal(${c.id})">Edit</button>
          <button class="btn btn-danger btn-sm" onclick="deleteClient(${c.id})">✕</button>
        </div>
      </div>
    </div>`).join('');

  return `
  <section class="hero" style="padding:56px 0 16px"><div class="wrap">
    <div class="eyebrow reveal in">Freelance · Web Dev</div>
    <h1 class="disp reveal in" style="font-size:clamp(36px,5.5vw,60px);letter-spacing:-.03em;line-height:1.02;margin:12px 0 0">Pitch. Build. Invoice.<br>Get paid.</h1>
    <p class="hero-sub reveal in" style="margin-top:18px;max-width:600px;margin-left:auto;margin-right:auto">Track local business clients from first pitch to paid invoice. Log projects, set rates, and sync monthly earnings to your Overview.</p>
  </div></section>

  <section class="section band tight"><div class="wrap">
    <div class="trio reveal in" style="grid-template-columns:repeat(4,1fr)">
      <div class="statc green"><div class="top"><div class="lbl">This month</div><div class="ico">💰</div></div><div class="val tnum"><span class="cur">$</span>${fmt(s.month_earned)}</div><div class="foot">invoices paid</div></div>
      <div class="statc ink"><div class="top"><div class="lbl">Total earned</div><div class="ico">◆</div></div><div class="val tnum"><span class="cur">$</span>${fmt(s.total_earned)}</div><div class="foot">all time</div></div>
      <div class="statc red"><div class="top"><div class="lbl">Pending</div><div class="ico">◷</div></div><div class="val tnum"><span class="cur">$</span>${fmt(s.pending)}</div><div class="foot">outstanding invoices</div></div>
      <div class="statc ink"><div class="top"><div class="lbl">Active</div><div class="ico">⚡</div></div><div class="val tnum">${s.active_projects||0}</div><div class="foot">${s.client_count||0} client${s.client_count===1?'':'s'} total</div></div>
    </div>
  </div></section>

  <section class="section tight"><div class="wrap">
    <div class="sec-head reveal in">
      <div><div class="eyebrow">Pipeline</div><div class="sec-title">Projects</div></div>
      <button class="btn btn-dark btn-sm" onclick="projectModal()">+ New project</button>
    </div>
    ${S.fl.projects.length?`<div class="card reveal in" style="overflow:auto">
      <table class="fl-table">
        <thead><tr><th>Project</th><th>Status</th><th>Rate</th><th>Value</th><th>Due</th><th></th></tr></thead>
        <tbody>${projRows}</tbody>
      </table></div>`:`<div class="empty"><div class="ico">💼</div><div class="big">No projects yet</div>Add a client and create your first project.</div>`}
  </div></section>

  <section class="section band tight"><div class="wrap">
    <div class="sec-head reveal in">
      <div><div class="eyebrow">Money</div><div class="sec-title">Invoices</div></div>
      <button class="btn btn-dark btn-sm" onclick="invoiceModal()">+ New invoice</button>
    </div>
    ${S.fl.invoices.length?`<div class="card reveal in" style="overflow:auto">
      <table class="fl-table">
        <thead><tr><th>Amount</th><th>Project</th><th>Status</th><th>Due</th><th>Paid</th><th></th></tr></thead>
        <tbody>${invRows}</tbody>
      </table></div>`:`<div class="empty"><div class="ico">🧾</div><div class="big">No invoices yet</div>Create an invoice when a project is delivered.</div>`}
  </div></section>

  <section class="section tight"><div class="wrap">
    <div class="sec-head reveal in">
      <div><div class="eyebrow">Clients</div><div class="sec-title">Client accounts</div></div>
      <button class="btn btn-dark btn-sm" onclick="clientModal()">+ Add client</button>
    </div>
    ${S.fl.clients.length?`<div class="grid reveal in">${clientCards}</div>`:`<div class="empty"><div class="ico">🤝</div><div class="big">No clients yet</div>Add the local businesses you're pitching to.</div>`}
  </div></section>
  <footer><div class="wrap"><span>Income Hub · Freelance</span><span>Arb the gap between your rate and their value</span></div></footer>`;}

function clientModal(id){const c=id?S.fl.clients.find(x=>x.id===id):null;const v=(f,d='')=>c?(c[f]??d):d;
  modal(`${c?'Edit':'Add'} client`,`
    <div class="row"><label>Business name</label><input id="cl-name" value="${esc(v('name'))}"></div>
    <div class="row2"><div><label>Contact person</label><input id="cl-contact" value="${esc(v('contact'))}"></div><div><label>Email</label><input id="cl-email" type="email" value="${esc(v('email'))}"></div></div>
    <div class="row"><label>Website URL</label><input id="cl-url" value="${esc(v('url'))}" placeholder="https://"></div>
    <div class="row"><label>Notes</label><textarea id="cl-notes">${esc(v('notes'))}</textarea></div>`,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="saveClient(${id||'null'})">Save</button>`);}
async function saveClient(id){const b={name:val('cl-name'),contact:val('cl-contact'),email:val('cl-email'),url:val('cl-url'),notes:val('cl-notes')};
  if(!b.name)return alert('Name required');
  if(id)await api.put('/api/fl/clients/'+id,b);else await api.post('/api/fl/clients',b);
  closeModal();render();}
async function deleteClient(id){if(!confirm('Delete client and all their projects?'))return;await api.del('/api/fl/clients/'+id);render();}

function projectModal(id){const p=id?S.fl.projects.find(x=>x.id===id):null;const v=(f,d='')=>p?(p[f]??d):d;
  const clientOpts=`<option value="">— no client —</option>`+S.fl.clients.map(c=>`<option value="${c.id}" ${v('client_id')==c.id?'selected':''}>${esc(c.name)}</option>`).join('');
  const statOpts=['lead','active','done','cancelled'].map(s=>`<option ${v('status','lead')===s?'selected':''}>${s}</option>`).join('');
  modal(`${p?'Edit':'New'} project`,`
    <div class="row"><label>Project name</label><input id="pr-name" value="${esc(v('name'))}" placeholder="e.g. Website redesign — Joe's Cafe"></div>
    <div class="row2"><div><label>Client</label><select id="pr-client">${clientOpts}</select></div><div><label>Status</label><select id="pr-status">${statOpts}</select></div></div>
    <div class="row2">
      <div><label>Rate type</label><select id="pr-rtype"><option value="fixed" ${v('rate_type','fixed')==='fixed'?'selected':''}>Fixed price</option><option value="hourly" ${v('rate_type')==='hourly'?'selected':''}>Hourly</option></select></div>
      <div><label>Rate / price ($)</label><input id="pr-rate" type="number" value="${v('rate',0)}"></div>
    </div>
    <div class="row2"><div><label>Hours logged</label><input id="pr-hours" type="number" step="0.5" value="${v('hours_logged',0)}"></div><div><label>Due date</label><input id="pr-due" type="date" value="${v('due_date')}"></div></div>
    <div class="row"><label>Notes</label><textarea id="pr-notes">${esc(v('notes'))}</textarea></div>`,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="saveProject(${id||'null'})">Save</button>`);}
async function saveProject(id){const b={name:val('pr-name'),client_id:val('pr-client')?parseInt(val('pr-client')):null,
  status:val('pr-status'),rate_type:val('pr-rtype'),rate:parseFloat(val('pr-rate'))||0,
  hours_logged:parseFloat(val('pr-hours'))||0,due_date:val('pr-due'),notes:val('pr-notes')};
  if(!b.name)return alert('Name required');
  if(id)await api.put('/api/fl/projects/'+id,b);else await api.post('/api/fl/projects',b);
  closeModal();render();}
async function setProjectStatus(id,status){await api.put('/api/fl/projects/'+id,{status});render();}
async function deleteProject(id){if(!confirm('Delete this project?'))return;await api.del('/api/fl/projects/'+id);render();}

function invoiceModal(id){const inv=id?S.fl.invoices.find(x=>x.id===id):null;const v=(f,d='')=>inv?(inv[f]??d):d;
  const projOpts=`<option value="">— no project —</option>`+S.fl.projects.map(p=>`<option value="${p.id}" ${v('project_id')==p.id?'selected':''}>${esc(p.name)}</option>`).join('');
  const statOpts=['draft','sent','paid','overdue'].map(s=>`<option ${v('status','draft')===s?'selected':''}>${s}</option>`).join('');
  modal(`${inv?'Edit':'New'} invoice`,`
    <div class="row2"><div><label>Project</label><select id="inv-proj">${projOpts}</select></div><div><label>Amount ($)</label><input id="inv-amt" type="number" value="${v('amount',0)}"></div></div>
    <div class="row2"><div><label>Status</label><select id="inv-status">${statOpts}</select></div><div><label>Due date</label><input id="inv-due" type="date" value="${v('due_date')}"></div></div>
    <div class="row"><label>Notes</label><textarea id="inv-notes">${esc(v('notes'))}</textarea></div>`,
    `<button class="btn btn-secondary" onclick="closeModal()">Cancel</button><button class="btn btn-primary" onclick="saveInvoice(${id||'null'})">Save</button>`);}
async function saveInvoice(id){const b={project_id:val('inv-proj')?parseInt(val('inv-proj')):null,
  amount:parseFloat(val('inv-amt'))||0,status:val('inv-status'),due_date:val('inv-due'),notes:val('inv-notes')};
  if(id)await api.put('/api/fl/invoices/'+id,b);else await api.post('/api/fl/invoices',b);
  closeModal();render();}
async function markInvoicePaid(id){await api.put('/api/fl/invoices/'+id,{status:'paid'});render();}
async function deleteInvoice(id){if(!confirm('Delete this invoice?'))return;await api.del('/api/fl/invoices/'+id);render();}
async function syncFreelance(){try{const st=await api.post('/api/fl/sync');alert(`Synced this month's freelance earnings ($${fmt(st.monthly_revenue)}) to the Overview map.`);}catch(e){alert(e.message);}}

/* ── modal helpers ── */
function modal(title,body,foot){document.getElementById('modal-root').innerHTML=
  `<div class="modal-bg" onclick="if(event.target===this)closeModal()"><div class="modal">
    <div class="modal-head">${title}<button class="x" onclick="closeModal()">×</button></div>
    <div class="modal-body">${body}</div><div class="modal-foot">${foot}</div></div></div>`;}
function closeModal(){document.getElementById('modal-root').innerHTML='';}
function val(id){const e=document.getElementById(id);return e?e.value.trim():'';}

render();
