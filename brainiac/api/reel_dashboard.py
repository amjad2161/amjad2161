"""Self-contained HTML dashboard for REEL-MAKER."""

from __future__ import annotations

from fastapi.responses import HTMLResponse

REEL_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>BRAINIAC REEL-MAKER</title>
  <style>
    :root {
      --bg: #0b0f14;
      --panel: #121820;
      --border: #243044;
      --text: #e8eef7;
      --muted: #8b9bb4;
      --accent: #5eead4;
      --danger: #f87171;
      --ok: #4ade80;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: ui-sans-serif, system-ui, sans-serif;
      background: radial-gradient(circle at top, #152033, var(--bg));
      color: var(--text);
      min-height: 100vh;
    }
    header {
      padding: 1.25rem 1.5rem;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
    }
    h1 { margin: 0; font-size: 1.25rem; letter-spacing: 0.04em; }
    .badge { color: var(--accent); font-size: 0.85rem; }
    main {
      display: grid;
      grid-template-columns: minmax(280px, 360px) 1fr;
      gap: 1rem;
      padding: 1rem 1.5rem 2rem;
    }
    @media (max-width: 900px) {
      main { grid-template-columns: 1fr; }
    }
    .card {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 1rem;
    }
    label { display: block; font-size: 0.8rem; color: var(--muted); margin-bottom: 0.35rem; }
    input, select, textarea, button {
      width: 100%;
      border-radius: 8px;
      border: 1px solid var(--border);
      background: #0d1219;
      color: var(--text);
      padding: 0.6rem 0.75rem;
      font: inherit;
    }
    textarea { min-height: 72px; resize: vertical; }
    .row { margin-bottom: 0.75rem; }
    .platforms { display: grid; grid-template-columns: 1fr 1fr; gap: 0.35rem 0.75rem; }
    .platforms label { display: flex; align-items: center; gap: 0.4rem; color: var(--text); }
    button {
      cursor: pointer;
      background: linear-gradient(135deg, #14b8a6, #0ea5e9);
      border: none;
      font-weight: 600;
      margin-top: 0.5rem;
    }
    button.secondary {
      background: transparent;
      border: 1px solid var(--border);
      color: var(--text);
      margin-top: 0.35rem;
    }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    #status { font-size: 0.85rem; color: var(--muted); min-height: 1.2rem; margin-top: 0.5rem; }
    table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
    th, td { text-align: left; padding: 0.55rem 0.35rem; border-bottom: 1px solid var(--border); }
    th { color: var(--muted); font-weight: 500; }
    .pill {
      display: inline-block;
      padding: 0.15rem 0.45rem;
      border-radius: 999px;
      font-size: 0.75rem;
      border: 1px solid var(--border);
    }
    .pill.ready { color: var(--ok); }
    .pill.failed { color: var(--danger); }
    .social { font-size: 0.8rem; color: var(--muted); line-height: 1.45; }
    .connect-row { display: flex; gap: 0.35rem; flex-wrap: wrap; margin-top: 0.5rem; }
    .connect-row button { width: auto; flex: 1 1 auto; min-width: 7rem; margin: 0; font-size: 0.8rem; }
    .provider-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.25rem 0.5rem;
      border-radius: 8px;
      border: 1px solid var(--border);
      font-size: 0.75rem;
      margin: 0.2rem 0.25rem 0.2rem 0;
    }
    .provider-pill.off { opacity: 0.55; }
    .provider-pill .dot { width: 0.45rem; height: 0.45rem; border-radius: 50%; background: var(--danger); }
    .provider-pill .dot.on { background: var(--ok); }
    .account-list { margin-top: 0.75rem; font-size: 0.8rem; }
    .account-item {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 0.5rem;
      padding: 0.5rem 0;
      border-bottom: 1px solid var(--border);
    }
    .account-meta { color: var(--muted); font-size: 0.72rem; }
    .actions { display: flex; gap: 0.35rem; flex-wrap: wrap; }
    .actions button { width: auto; padding: 0.25rem 0.55rem; margin: 0; font-size: 0.75rem; }
    a { color: var(--accent); }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>BRAINIAC REEL-MAKER</h1>
      <div class="badge">Compose · Schedule · Publish</div>
    </div>
    <div id="social-summary" class="social">Loading social status…</div>
  </header>
  <main>
    <section class="card">
      <h2 style="margin-top:0;font-size:1rem;">New reel</h2>
      <form id="compose-form">
        <div class="row">
          <label for="topic">Topic</label>
          <textarea id="topic" required placeholder="3 AI hacks that save 2 hours a day"></textarea>
        </div>
        <div class="row">
          <label for="style">Style</label>
          <select id="style">
            <option value="viral_hook">viral_hook</option>
            <option value="storytelling">storytelling</option>
            <option value="tutorial">tutorial</option>
            <option value="motivational">motivational</option>
            <option value="product">product</option>
            <option value="trend_remix">trend_remix</option>
            <option value="news_buzz">news_buzz</option>
          </select>
        </div>
        <div class="row platforms">
          <label><input type="checkbox" name="platform" value="tiktok" checked /> TikTok</label>
          <label><input type="checkbox" name="platform" value="instagram" checked /> Instagram</label>
          <label><input type="checkbox" name="platform" value="youtube" /> YouTube</label>
          <label><input type="checkbox" name="platform" value="facebook" /> Facebook</label>
        </div>
        <div class="row">
          <label><input type="checkbox" id="voiceover" checked /> Voiceover (SonicMatrix)</label>
        </div>
        <div class="row">
          <label><input type="checkbox" id="use_ai_script" /> AI script (NeuroCore)</label>
        </div>
        <button type="submit" id="compose-btn">Compose reel</button>
        <div id="status"></div>
      </form>
      <hr style="border:none;border-top:1px solid var(--border);margin:1rem 0;" />
      <h2 style="margin:0 0 0.5rem;font-size:1rem;">Social accounts</h2>
      <p class="social" style="margin:0 0 0.5rem;">
        Connect Instagram, Facebook, TikTok, and YouTube in one bundle — automation uses the same linked accounts.
      </p>
      <div class="row">
        <label for="connect-label">Bundle label</label>
        <input id="connect-label" type="text" value="default" placeholder="default" />
      </div>
      <div class="connect-row">
        <button type="button" id="connect-all-btn">Connect all</button>
        <button type="button" class="secondary" id="refresh-social-btn">Refresh</button>
      </div>
      <div id="oauth-providers" class="connect-row"></div>
      <div id="account-list" class="account-list">Loading accounts…</div>
    </section>
    <section class="card">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:0.5rem;">
        <h2 style="margin:0;font-size:1rem;">Jobs</h2>
        <button type="button" class="secondary" id="refresh-btn" style="width:auto;">Refresh</button>
      </div>
      <div style="overflow-x:auto;margin-top:0.75rem;">
        <table>
          <thead>
            <tr>
              <th>Topic</th>
              <th>Status</th>
              <th>Score</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody id="jobs-body">
            <tr><td colspan="4">Loading…</td></tr>
          </tbody>
        </table>
      </div>
    </section>
  </main>
  <script>
    const api = (path, opts = {}) => fetch(path, {
      headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
      ...opts,
    });

    function setStatus(msg, isError = false) {
      const el = document.getElementById('status');
      el.textContent = msg;
      el.style.color = isError ? '#f87171' : '#8b9bb4';
    }

    function selectedPlatforms() {
      return [...document.querySelectorAll('input[name="platform"]:checked')].map((el) => el.value);
    }

    function connectLabel() {
      return document.getElementById('connect-label').value.trim() || 'default';
    }

    function oauthStartUrl(path, groupId) {
      const q = new URLSearchParams({
        label: connectLabel(),
        return_to: '/reel',
      });
      if (groupId) q.set('group_id', groupId);
      return `${path}?${q.toString()}`;
    }

    async function loadSocial() {
      const r = await api('/api/v1/reel/social/status');
      const data = await r.json();
      const ready = Object.entries(data.platforms || {})
        .filter(([, v]) => v.configured)
        .map(([k]) => k);
      const connected = (data.accounts || []).length;
      const summary = document.getElementById('social-summary');
      summary.innerHTML = [
        connected ? `${connected} account(s) connected` : 'No OAuth accounts',
        data.webhook_configured ? 'Webhook: on' : 'Webhook: off',
        data.public_base_url_configured ? 'Public URL: set' : 'Public URL: missing (Instagram)',
        ready.length ? `Live: ${ready.join(', ')}` : 'Live publish: dry-run only',
      ].join(' · ');

      const providersEl = document.getElementById('oauth-providers');
      const providers = data.oauth_providers || {};
      providersEl.innerHTML = Object.entries(providers).map(([key, p]) => {
        const cls = p.configured ? 'on' : '';
        const title = p.configured ? p.label : `${p.label} (set app credentials in .env)`;
        return `<button type="button" class="secondary provider-connect" data-provider="${key}" data-ready="${p.configured}" title="${title}">${p.label}</button>`;
      }).join('');
      providersEl.querySelectorAll('.provider-connect').forEach((btn) => {
        btn.addEventListener('click', () => connectProvider(btn.dataset.provider, btn.dataset.ready === 'true'));
      });

      window.__connectAllBundle = data.connect_all || null;
      renderAccounts(data.accounts || []);
    }

    function renderAccounts(accounts) {
      const el = document.getElementById('account-list');
      if (!accounts.length) {
        el.innerHTML = '<div class="social">No connected accounts yet. Use Connect all or pick a provider above.</div>';
        return;
      }
      el.innerHTML = accounts.map((acc) => {
        const def = acc.is_default ? '<span class="pill ready">default</span> ' : '';
        const expired = acc.token_expired ? '<span class="pill failed">expired</span> ' : '';
        const extra = acc.extra?.page_name || acc.extra?.channel_title || acc.extra?.username || '';
        return `<div class="account-item" data-id="${acc.id}">
          <div>
            <div><strong>${acc.platform}</strong> ${def}${expired}</div>
            <div>${acc.label}</div>
            <div class="account-meta">${extra ? extra + ' · ' : ''}${acc.id.slice(0, 8)}…</div>
          </div>
          <div class="actions">
            ${acc.is_default ? '' : `<button type="button" class="secondary" data-default="${acc.id}">Default</button>`}
            <button type="button" class="secondary" data-disconnect="${acc.id}">Remove</button>
          </div>
        </div>`;
      }).join('');
      el.querySelectorAll('[data-disconnect]').forEach((btn) => {
        btn.addEventListener('click', () => disconnectAccount(btn.dataset.disconnect));
      });
      el.querySelectorAll('[data-default]').forEach((btn) => {
        btn.addEventListener('click', () => setDefaultAccount(btn.dataset.default));
      });
    }

    async function connectProvider(provider, ready) {
      if (!ready) {
        setStatus(`OAuth app not configured for ${provider}. Set credentials in .env`, true);
        return;
      }
      const bundle = window.__connectAllBundle;
      const groupId = bundle?.group_id || null;
      window.location.href = oauthStartUrl(`/api/v1/reel/social/oauth/start/${provider}`, groupId);
    }

    async function connectAll() {
      const r = await api(`/api/v1/reel/social/oauth/start-all?label=${encodeURIComponent(connectLabel())}`);
      const bundle = await r.json();
      window.__connectAllBundle = bundle;
      const pending = (bundle.connections || []).filter((c) => c.configured);
      if (!pending.length) {
        setStatus('No OAuth apps configured. Add META/GOOGLE/TIKTOK credentials to .env', true);
        return;
      }
      const first = pending[0];
      window.location.href = oauthStartUrl(first.start_url.split('?')[0], bundle.group_id);
    }

    async function disconnectAccount(accountId) {
      if (!confirm('Disconnect this account?')) return;
      const r = await api(`/api/v1/reel/social/accounts/${accountId}`, { method: 'DELETE' });
      if (!r.ok) {
        setStatus('Could not remove account', true);
        return;
      }
      await loadSocial();
    }

    async function setDefaultAccount(accountId) {
      const r = await api(`/api/v1/reel/social/accounts/${accountId}/default`, { method: 'POST' });
      if (!r.ok) {
        setStatus('Could not set default account', true);
        return;
      }
      await loadSocial();
    }

    function pill(status) {
      const cls = status === 'ready' || status === 'published' ? 'ready' : (status === 'failed' ? 'failed' : '');
      return `<span class="pill ${cls}">${status}</span>`;
    }

    async function loadJobs() {
      const r = await api('/api/v1/reel/jobs?limit=25');
      const jobs = await r.json();
      const body = document.getElementById('jobs-body');
      if (!jobs.length) {
        body.innerHTML = '<tr><td colspan="4">No jobs yet — compose your first reel.</td></tr>';
        return;
      }
      body.innerHTML = jobs.map((job) => {
        const canPublish = job.status === 'ready' || job.status === 'published';
        const video = job.status === 'ready' || job.status === 'published'
          ? `<a href="/api/v1/reel/jobs/${job.job_id}/video" target="_blank">video</a>`
          : '';
        return `<tr>
          <td title="${job.job_id}">${job.topic.slice(0, 42)}</td>
          <td>${pill(job.status)}</td>
          <td>${(job.algorithm_score || 0).toFixed(1)}</td>
          <td class="actions">
            ${video}
            ${canPublish ? `<button type="button" data-publish="${job.job_id}">Publish</button>` : ''}
            <button type="button" class="secondary" data-delete="${job.job_id}">Delete</button>
          </td>
        </tr>`;
      }).join('');
      body.querySelectorAll('[data-publish]').forEach((btn) => {
        btn.addEventListener('click', () => publishJob(btn.dataset.publish));
      });
      body.querySelectorAll('[data-delete]').forEach((btn) => {
        btn.addEventListener('click', () => deleteJob(btn.dataset.delete));
      });
    }

    async function publishJob(jobId) {
      setStatus(`Publishing ${jobId}…`);
      const r = await api(`/api/v1/reel/jobs/${jobId}/publish`, {
        method: 'POST',
        body: JSON.stringify({ dry_run: true }),
      });
      const data = await r.json();
      if (!r.ok) {
        setStatus(data.detail || 'Publish failed', true);
        return;
      }
      setStatus(`Published (dry_run=${data.dry_run})`);
      await loadJobs();
    }

    async function deleteJob(jobId) {
      if (!confirm('Delete this job and its files?')) return;
      await api(`/api/v1/reel/jobs/${jobId}`, { method: 'DELETE' });
      await loadJobs();
    }

    document.getElementById('compose-form').addEventListener('submit', async (e) => {
      e.preventDefault();
      const platforms = selectedPlatforms();
      if (!platforms.length) {
        setStatus('Select at least one platform', true);
        return;
      }
      const btn = document.getElementById('compose-btn');
      btn.disabled = true;
      setStatus('Composing… this may take a few seconds.');
      try {
        const body = {
          topic: document.getElementById('topic').value.trim(),
          style: document.getElementById('style').value,
          platforms,
          voiceover: document.getElementById('voiceover').checked,
        };
        if (document.getElementById('use_ai_script').checked) {
          body.use_ai_script = true;
        }
        const r = await api('/api/v1/reel/compose', { method: 'POST', body: JSON.stringify(body) });
        const job = await r.json();
        if (!r.ok) {
          setStatus(job.detail || 'Compose failed', true);
          return;
        }
        setStatus(`Ready: ${job.job_id} (score ${job.algorithm_score.toFixed(1)})`);
        await loadJobs();
      } finally {
        btn.disabled = false;
      }
    });

    document.getElementById('refresh-btn').addEventListener('click', loadJobs);
    document.getElementById('refresh-social-btn').addEventListener('click', loadSocial);
    document.getElementById('connect-all-btn').addEventListener('click', connectAll);
    loadSocial();
    loadJobs();
  </script>
</body>
</html>
"""


def reel_dashboard_page() -> HTMLResponse:
    return HTMLResponse(content=REEL_DASHBOARD_HTML)
