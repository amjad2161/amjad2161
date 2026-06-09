"""OAuth callback HTML and social connect API helpers."""

from __future__ import annotations

from fastapi.responses import HTMLResponse


def oauth_success_page(
    *,
    provider: str,
    accounts: list[dict[str, object]],
    return_to: str,
) -> HTMLResponse:
    rows = "".join(
        f"<li><strong>{a.get('platform')}</strong> — {a.get('label')} "
        f"<code>{a.get('id')}</code></li>"
        for a in accounts
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Connected — BRAINIAC REEL-MAKER</title>
  <style>
    body {{
      font-family: ui-sans-serif, system-ui, sans-serif;
      background: #0b0f14;
      color: #e8eef7;
      display: grid;
      place-items: center;
      min-height: 100vh;
      margin: 0;
      padding: 1rem;
    }}
    .card {{
      background: #121820;
      border: 1px solid #243044;
      border-radius: 12px;
      padding: 1.5rem;
      max-width: 520px;
      width: 100%;
    }}
    a {{
      color: #5eead4;
    }}
    code {{
      font-size: 0.8rem;
      color: #8b9bb4;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Social accounts connected</h1>
    <p>Provider: <strong>{provider}</strong></p>
    <ul>{rows or "<li>No accounts saved</li>"}</ul>
    <p><a href="{return_to}">Back to REEL-MAKER dashboard</a></p>
  </div>
  <script>
    setTimeout(() => {{ window.location.href = {return_to!r}; }}, 2500);
  </script>
</body>
</html>"""
    return HTMLResponse(html)


def oauth_error_page(message: str, *, return_to: str = "/reel") -> HTMLResponse:
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Connection failed</title>
  <style>
    body {{ font-family: sans-serif; background:#111; color:#eee; padding:2rem; }}
    a {{ color:#5eead4; }}
  </style>
</head>
<body>
  <h1>Could not connect account</h1>
  <p>{message}</p>
  <p><a href="{return_to}">Return to dashboard</a></p>
</body>
</html>"""
    return HTMLResponse(html, status_code=400)
