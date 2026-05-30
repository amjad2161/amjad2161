"""A self-contained live dashboard for the SINGULARITY gateway.

Zero build step, zero dependencies: one HTML document that polls ``/status`` and
subscribes to the ``/stream`` SSE feed to render organ health, circuit state,
metrics and a live event log — echoing the BRAINIAC / agency dashboards.
"""

from __future__ import annotations

DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>SINGULARITY</title>
<style>
  :root { --bg:#0a0c10; --panel:#12161d; --line:#222a35; --fg:#e6edf3; --dim:#8b98a9;
          --ok:#3fb950; --warn:#d29922; --bad:#f85149; --accent:#58a6ff; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font:14px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; }
  header { padding:18px 24px; border-bottom:1px solid var(--line); display:flex;
           align-items:baseline; gap:16px; }
  header h1 { margin:0; font-size:20px; letter-spacing:3px; }
  header .v { color:var(--dim); }
  header .stat { margin-left:auto; color:var(--dim); }
  .wrap { display:grid; grid-template-columns:2fr 1fr; gap:16px; padding:16px 24px; }
  .panel { background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px; }
  .panel h2 { margin:0 0 10px; font-size:12px; text-transform:uppercase; letter-spacing:2px; color:var(--dim); }
  .organs { display:grid; grid-template-columns:repeat(auto-fill,minmax(150px,1fr)); gap:10px; }
  .organ { border:1px solid var(--line); border-radius:8px; padding:10px; }
  .organ .id { font-weight:700; }
  .organ .meta { color:var(--dim); font-size:12px; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
  .alive{background:var(--ok);} .degraded{background:var(--warn);} .down,.dormant{background:var(--bad);}
  .badge { font-size:11px; padding:1px 6px; border-radius:6px; border:1px solid var(--line); color:var(--dim); }
  #log { height:60vh; overflow:auto; font-size:12px; }
  #log div { padding:2px 0; border-bottom:1px solid #1b2129; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  #log .t { color:var(--accent); }
  .kv { display:flex; justify-content:space-between; color:var(--dim); }
  .kv b { color:var(--fg); }
</style>
</head>
<body>
<header>
  <h1>SINGULARITY</h1><span class="v" id="ver"></span>
  <span class="stat" id="stat">connecting…</span>
</header>
<div class="wrap">
  <div>
    <div class="panel"><h2>Organs</h2><div class="organs" id="organs"></div></div>
    <div class="panel" style="margin-top:16px"><h2>Counters</h2><div id="counters"></div></div>
  </div>
  <div class="panel"><h2>Live nervous system</h2><div id="log"></div></div>
</div>
<script>
// XSS-safe: every value from /status and the /stream SSE feed is written via
// textContent / DOM construction, never innerHTML. Attacker-controlled payloads
// (e.g. a /pulse goal "<img src=x onerror=...>") therefore render as inert text
// instead of executing in the operator's browser.
function el(tag, cls, text){
  const e=document.createElement(tag);
  if(cls) e.className=cls;
  if(text!=null) e.textContent=text;
  return e;
}
async function poll(){
  try{
    const s = await (await fetch('./status')).json();
    document.getElementById('ver').textContent = 'v'+(s.version||'');
    document.getElementById('stat').textContent =
      `${s.alive}/${s.organs} alive · ${s.real_mode} real · ${s.intents} intents · `+
      `${s.events_published} events · ${s.memory_sessions||0} sessions`;
    const o = document.getElementById('organs'); o.textContent='';
    (s.health||[]).forEach(h=>{
      const circ = (s.circuits||{})[h.organ]||'-';
      const card = el('div','organ');
      const id = el('div','id');
      // liveness only ever drives a CSS class; sanitise to letters defensively.
      id.appendChild(el('span','dot '+String(h.liveness||'').replace(/[^a-z]/gi,'')));
      id.appendChild(document.createTextNode(String(h.organ)));
      card.appendChild(id);
      card.appendChild(el('div','meta', `${h.mode} · ${h.liveness}`));
      const meta2 = el('div','meta');
      meta2.appendChild(el('span','badge','circuit '+circ));
      card.appendChild(meta2);
      o.appendChild(card);
    });
    const c = document.getElementById('counters'); c.textContent='';
    const counters=(s.metrics&&s.metrics.counters)||{};
    Object.keys(counters).sort().slice(0,12).forEach(k=>{
      const row = el('div','kv');
      row.appendChild(el('span',null,k));
      const b=document.createElement('b'); b.textContent=counters[k];
      row.appendChild(b); c.appendChild(row);
    });
  }catch(e){ document.getElementById('stat').textContent='offline'; }
}
function logLine(topic,data){
  const log=document.getElementById('log');
  const d=document.createElement('div');
  d.appendChild(el('span','t', new Date().toLocaleTimeString()));
  d.appendChild(document.createTextNode(' '+topic+' '));
  const v=el('span',null,data); v.style.color='#8b98a9';
  d.appendChild(v);
  log.prepend(d);
  while(log.childNodes.length>200) log.removeChild(log.lastChild);
}
try{
  const es=new EventSource('./stream');
  es.onmessage=e=>{ try{ const s=JSON.parse(e.data);
    logLine(s.topic||'event', JSON.stringify(s.payload||{})); }catch(_){ logLine('event',e.data); } };
  es.onerror=()=>logLine('stream','reconnecting…');
}catch(e){}
poll(); setInterval(poll,2000);
</script>
</body>
</html>
"""
