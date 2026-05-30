"""The SINGULARITY command center — a self-contained live dashboard.

Zero build step, zero dependencies: one HTML document that polls ``/health`` for
the real kernel status and subscribes to the ``/stream`` SSE feed. It renders
the organ grid (with REAL/MOCK provenance), circuit + metric panels, a live
nervous-system feed, and an interactive console that routes goals through the
real kernel (sending the bearer token to the guarded ``/route`` and ``/pulse``).

All feed/status values are written via ``textContent`` / DOM construction, never
``innerHTML`` with data — so attacker-controlled payloads render as inert text.
"""

from __future__ import annotations

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SINGULARITY · Command Center</title>
<style>
  :root{ --bg:#05070d; --bg2:#0a0e17; --panel:rgba(18,24,36,.72); --line:#1d2738;
         --fg:#e6f0ff; --dim:#7d8ca8; --cy:#22d3ee; --cy2:#0891b2; --ok:#34d399;
         --warn:#fbbf24; --bad:#f87171; --real:#34d399; --mock:#64748b; }
  *{box-sizing:border-box}
  body{margin:0;background:
        radial-gradient(1200px 600px at 80% -10%,rgba(34,211,238,.10),transparent),
        radial-gradient(900px 500px at -10% 110%,rgba(34,211,238,.06),transparent),
        var(--bg);color:var(--fg);
        font:13px/1.5 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
  header{display:flex;align-items:center;gap:18px;padding:14px 22px;
         border-bottom:1px solid var(--line);background:linear-gradient(180deg,rgba(34,211,238,.05),transparent)}
  header h1{margin:0;font-size:19px;letter-spacing:5px;font-weight:700;
            background:linear-gradient(90deg,#fff,var(--cy));-webkit-background-clip:text;
            -webkit-text-fill-color:transparent}
  header .v{color:var(--dim);font-size:11px}
  header .stat{margin-left:auto;color:var(--dim);font-size:12px;text-align:right}
  header .stat b{color:var(--cy)}
  .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:6px;vertical-align:middle;
       box-shadow:0 0 8px currentColor}
  .alive{color:var(--ok);background:var(--ok)} .degraded{color:var(--warn);background:var(--warn)}
  .down,.dormant{color:var(--bad);background:var(--bad)}
  .wrap{display:grid;grid-template-columns:1.7fr 1fr;gap:16px;padding:16px 22px}
  .panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px;
         backdrop-filter:blur(6px)}
  .panel h2{margin:0 0 12px;font-size:11px;text-transform:uppercase;letter-spacing:3px;color:var(--dim)}
  .organs{display:grid;grid-template-columns:repeat(auto-fill,minmax(165px,1fr));gap:10px}
  .organ{border:1px solid var(--line);border-radius:11px;padding:11px 12px;
          background:linear-gradient(180deg,rgba(255,255,255,.02),transparent);transition:.2s}
  .organ:hover{border-color:var(--cy2);transform:translateY(-1px)}
  .organ .id{font-weight:700;font-size:14px;letter-spacing:.5px}
  .organ .dom{color:var(--dim);font-size:11px;margin-top:2px}
  .organ .row{display:flex;align-items:center;justify-content:space-between;margin-top:8px}
  .badge{font-size:10px;font-weight:700;letter-spacing:1px;padding:2px 8px;border-radius:20px;border:1px solid}
  .b-real{color:var(--real);border-color:var(--real);background:rgba(52,211,153,.08)}
  .b-mock{color:var(--mock);border-color:var(--mock)}
  .chip{font-size:10px;color:var(--dim);border:1px solid var(--line);border-radius:6px;padding:1px 6px}
  .kv{display:flex;justify-content:space-between;color:var(--dim);padding:2px 0}
  .kv b{color:var(--fg)}
  #log{height:38vh;overflow:auto;font-size:11.5px}
  #log div{padding:3px 0;border-bottom:1px solid #131a26;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  #log .t{color:var(--cy)}
  .console{margin:0 22px 18px;background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
  .console h2{margin:0 0 10px;font-size:11px;text-transform:uppercase;letter-spacing:3px;color:var(--dim)}
  .crow{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
  input,button{font:inherit}
  input{background:#0a0f1a;border:1px solid var(--line);color:var(--fg);border-radius:8px;padding:8px 10px}
  input:focus{outline:none;border-color:var(--cy2)}
  #intent{width:170px} #payload{flex:1;min-width:220px} #goal{flex:1;min-width:220px} #token{width:150px}
  button{background:linear-gradient(180deg,var(--cy),var(--cy2));color:#04121a;border:none;font-weight:700;
         letter-spacing:.5px;border-radius:8px;padding:8px 16px;cursor:pointer}
  button:hover{filter:brightness(1.1)} button.ghost{background:transparent;border:1px solid var(--cy2);color:var(--cy)}
  #out{margin-top:10px;background:#070b13;border:1px solid var(--line);border-radius:8px;padding:10px;
       max-height:26vh;overflow:auto;white-space:pre-wrap;font-size:11.5px;color:#bfe9f5;min-height:20px}
  .muted{color:var(--dim)}
</style>
</head>
<body>
<header>
  <h1>SINGULARITY</h1><span class="v" id="ver"></span>
  <span class="stat" id="stat">connecting…</span>
</header>

<div class="wrap">
  <div>
    <div class="panel"><h2>Organs · live federation</h2><div class="organs" id="organs"></div></div>
    <div class="panel" style="margin-top:16px"><h2>Telemetry</h2><div id="counters"></div></div>
  </div>
  <div class="panel"><h2>Live nervous system</h2><div id="log"></div></div>
</div>

<div class="console">
  <h2>Command console · route a goal through the real kernel</h2>
  <div class="crow" style="margin-bottom:8px">
    <input id="token" placeholder="API token" title="SINGULARITY_API_TOKEN (guarded routes)"/>
    <input id="goal" placeholder="goal for /pulse  (e.g. survey a vineyard then hedge)"/>
    <button id="bpulse">Pulse</button>
  </div>
  <div class="crow">
    <input id="intent" placeholder="intent  (e.g. trade.signal)"/>
    <input id="payload" placeholder='payload JSON  {"symbol":"BTC/USDT"}'/>
    <button id="broute" class="ghost">Route</button>
  </div>
  <div id="out" class="muted">Results appear here. Public reads (status/feed) need no token; /route &amp; /pulse do.</div>
</div>

<script>
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!=null)e.textContent=text;return e;}
function set(id,t){document.getElementById(id).textContent=t;}

async function poll(){
  try{
    const h=await(await fetch('./health')).json();
    const s=h.status||{};
    set('ver','v'+(s_version(s)));
    set('stat','');
    const st=document.getElementById('stat');
    st.textContent='';
    const mk=(label,val)=>{const w=el('span');w.appendChild(el('b',null,String(val)));
                            w.appendChild(document.createTextNode(' '+label+'   '));return w;};
    st.appendChild(mk('organs',`${s.alive}/${s.organs} alive`));
    st.appendChild(mk('real',`${s.real_mode}/${s.organs}`));
    st.appendChild(mk('intents',s.intents));
    st.appendChild(mk('events',s.events_published));
    const o=document.getElementById('organs');o.textContent='';
    (s.health||[]).forEach(x=>{
      const circ=(s.circuits||{})[x.organ]||'-';
      const card=el('div','organ');
      const id=el('div','id'); id.appendChild(el('span','dot '+String(x.liveness||'').replace(/[^a-z]/gi,'')));
      id.appendChild(document.createTextNode(x.organ)); card.appendChild(id);
      card.appendChild(el('div','dom',(x.detail&&x.detail.domain)||domOf(x.organ)));
      const row=el('div','row');
      row.appendChild(el('span','badge '+(x.mode==='real'?'b-real':'b-mock'),x.mode==='real'?'REAL':'MOCK'));
      row.appendChild(el('span','chip','circuit '+circ));
      card.appendChild(row); o.appendChild(card);
    });
    const c=document.getElementById('counters');c.textContent='';
    const ctr=(s.metrics&&s.metrics.counters)||{};
    const keys=Object.keys(ctr).sort().slice(0,10);
    if(!keys.length) c.appendChild(el('div','muted','no traffic yet — issue a command below'));
    keys.forEach(k=>{const r=el('div','kv');r.appendChild(el('span',null,k));
                     r.appendChild(el('b',null,String(ctr[k])));c.appendChild(r);});
  }catch(e){ set('stat','offline'); }
}
function s_version(s){return s.version||'1.6.1';}
function domOf(id){return ({neuro:'reasoning',agents:'agency',knowledge:'knowledge',sky:'embodiment',
  trade:'economics',vision:'perception',nexus:'dataplane',net:'network',control:'actuation'})[id]||'';}

function logLine(topic,data){
  const log=document.getElementById('log');const d=el('div');
  d.appendChild(el('span','t',new Date().toLocaleTimeString()));
  d.appendChild(document.createTextNode(' '+topic+' '));
  const v=el('span',null,data); v.style.color='#7d8ca8'; d.appendChild(v);
  log.prepend(d); while(log.childNodes.length>250) log.removeChild(log.lastChild);
}
try{
  const es=new EventSource('./stream');
  es.onmessage=e=>{try{const s=JSON.parse(e.data);logLine(s.topic||'event',JSON.stringify(s.payload||{}));}catch(_){logLine('event',e.data);}};
  es.onerror=()=>logLine('stream','reconnecting…');
}catch(e){}

async function post(path,body){
  const token=document.getElementById('token').value.trim();
  const headers={'Content-Type':'application/json'};
  if(token) headers['Authorization']='Bearer '+token;
  const out=document.getElementById('out'); out.className=''; out.textContent='… routing through kernel …';
  try{
    const r=await fetch(path,{method:'POST',headers,body:JSON.stringify(body)});
    const txt=await r.text();
    let pretty=txt; try{pretty=JSON.stringify(JSON.parse(txt),null,2);}catch(_){}
    out.textContent='HTTP '+r.status+'\\n'+pretty;
  }catch(e){ out.textContent='request failed: '+e; }
}
document.getElementById('bpulse').onclick=()=>{
  const g=document.getElementById('goal').value.trim(); if(g) post('./pulse',{goal:g});
};
document.getElementById('broute').onclick=()=>{
  const intent=document.getElementById('intent').value.trim(); if(!intent)return;
  let payload={}; const raw=document.getElementById('payload').value.trim();
  if(raw){try{payload=JSON.parse(raw);}catch(e){document.getElementById('out').textContent='payload is not valid JSON';return;}}
  post('./route',{intent,payload});
};
poll(); setInterval(poll,2000);
</script>
</body>
</html>
"""
