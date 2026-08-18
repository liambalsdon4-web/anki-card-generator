"""Render a standalone landing page (single HTML file) from AI-generated copy.

The waitlist form POSTs to the app's own /api/saas/ideas/{id}/signup, so when the
page is served by Income Hub (or hosted alongside it) signups are captured live.
Matches the app's aesthetic: Bricolage Grotesque + Manrope, acid-green accent.
"""
from __future__ import annotations

import html
import json


def _esc(s) -> str:
    return html.escape(str(s or ""))


def render_landing(idea: dict, copy: dict, signup_path: str) -> str:
    name = _esc(idea.get("name", "Product"))
    features = "".join(
        f"""<div class="feat"><h3>{_esc(f.get('title'))}</h3><p>{_esc(f.get('body'))}</p></div>"""
        for f in copy.get("features", [])
    )
    pricing = "".join(
        f"""<div class="tier{' hot' if p.get('highlight') else ''}">
              <div class="tname">{_esc(p.get('tier'))}</div>
              <div class="tprice">{_esc(p.get('price'))}</div>
              <ul>{''.join(f'<li>{_esc(x)}</li>' for x in p.get('features', []))}</ul>
            </div>"""
        for p in copy.get("pricing", [])
    )
    faq = "".join(
        f"""<div class="qa"><h4>{_esc(q.get('q'))}</h4><p>{_esc(q.get('a'))}</p></div>"""
        for q in copy.get("faq", [])
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,700;12..96,800&family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
:root{{--ink:#0f1211;--muted:#5b615e;--line:rgba(0,0,0,.09);--green:#00a862;--green2:#0bc57c;--bg:#f7f8f7}}
body{{font-family:'Manrope',system-ui,sans-serif;color:var(--ink);background:var(--bg);line-height:1.55;-webkit-font-smoothing:antialiased}}
.disp{{font-family:'Bricolage Grotesque',sans-serif}}
.wrap{{max-width:1040px;margin:0 auto;padding:0 24px}}
header{{padding:26px 0;display:flex;align-items:center;gap:10px}}
.logo{{width:34px;height:34px;border-radius:10px;background:linear-gradient(145deg,var(--green2),var(--green));display:flex;align-items:center;justify-content:center;color:#fff;font-family:'Bricolage Grotesque';font-weight:700;font-size:19px}}
.brand{{font-family:'Bricolage Grotesque';font-weight:700;font-size:20px}}
.hero{{text-align:center;padding:70px 0 40px;position:relative}}
.hero::before{{content:'';position:absolute;left:50%;top:0;transform:translateX(-50%);width:min(720px,90vw);height:360px;background:radial-gradient(closest-side,rgba(11,197,124,.18),transparent 70%);z-index:0}}
.hero>*{{position:relative;z-index:1}}
.hero h1{{font-family:'Bricolage Grotesque';font-weight:800;font-size:clamp(38px,6vw,68px);letter-spacing:-.03em;line-height:1.02;max-width:16ch;margin:0 auto}}
.hero p.sub{{font-size:clamp(17px,2.2vw,21px);color:var(--muted);margin:22px auto 0;max-width:38ch}}
form{{display:flex;gap:10px;max-width:460px;margin:34px auto 0;flex-wrap:wrap;justify-content:center}}
input[type=email]{{flex:1;min-width:220px;padding:15px 18px;border:1px solid var(--line);border-radius:14px;font-size:16px;font-family:inherit;background:#fff;outline:none}}
input[type=email]:focus{{border-color:var(--green);box-shadow:0 0 0 3px rgba(0,168,98,.15)}}
button{{padding:15px 26px;border:none;border-radius:14px;background:var(--green);color:#fff;font-weight:700;font-size:16px;font-family:inherit;cursor:pointer;transition:.16s}}
button:hover{{background:#0a7a48;transform:translateY(-1px)}}
.note{{font-size:13px;color:var(--muted);margin-top:14px}}
.msg{{margin-top:16px;font-weight:700;color:var(--green);min-height:22px}}
section{{padding:56px 0}}
.eyebrow{{font-family:'Bricolage Grotesque';text-align:center;font-weight:700;letter-spacing:.12em;text-transform:uppercase;font-size:12px;color:var(--green);margin-bottom:30px}}
.feats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px}}
.feat{{background:#fff;border:1px solid var(--line);border-radius:18px;padding:24px}}
.feat h3{{font-family:'Bricolage Grotesque';font-weight:700;font-size:19px;margin-bottom:8px}}
.feat p{{color:var(--muted);font-size:15px}}
.tiers{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px;max-width:820px;margin:0 auto}}
.tier{{background:#fff;border:1px solid var(--line);border-radius:20px;padding:28px;text-align:center}}
.tier.hot{{border-color:var(--green);box-shadow:0 20px 50px -22px rgba(0,168,98,.4)}}
.tname{{font-family:'Bricolage Grotesque';font-weight:700;font-size:18px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted)}}
.tprice{{font-family:'Bricolage Grotesque';font-weight:800;font-size:38px;margin:8px 0 16px}}
.tier ul{{list-style:none;text-align:left;display:inline-block}}
.tier li{{padding:6px 0 6px 24px;position:relative;color:var(--ink)}}
.tier li::before{{content:'✓';position:absolute;left:0;color:var(--green);font-weight:800}}
.band{{background:#fff;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}
.qa{{max-width:720px;margin:0 auto 18px;padding-bottom:18px;border-bottom:1px solid var(--line)}}
.qa h4{{font-family:'Bricolage Grotesque';font-weight:700;font-size:18px;margin-bottom:6px}}
.qa p{{color:var(--muted)}}
footer{{text-align:center;padding:50px 0;color:var(--muted);font-size:14px}}
</style></head>
<body>
<div class="wrap"><header><span class="logo">{name[:1].upper()}</span><span class="brand">{name}</span></header></div>

<div class="hero"><div class="wrap">
  <h1 class="disp">{_esc(copy.get('headline'))}</h1>
  <p class="sub">{_esc(copy.get('subhead'))}</p>
  <form onsubmit="return joinWaitlist(event)">
    <input type="email" id="wl-email" placeholder="you@work.com" required>
    <button type="submit">{_esc(copy.get('cta') or 'Join the waitlist')}</button>
  </form>
  <div class="note">{_esc(copy.get('footer_note'))}</div>
  <div class="msg" id="wl-msg"></div>
</div></div>

<section><div class="wrap"><div class="eyebrow">Why it matters</div><div class="feats">{features}</div></div></section>
<section class="band"><div class="wrap"><div class="eyebrow">Pricing</div><div class="tiers">{pricing}</div></div></section>
<section><div class="wrap"><div class="eyebrow">FAQ</div>{faq}</div></section>
<footer>© {name} · Built with Income Hub</footer>

<script>
async function joinWaitlist(e){{
  e.preventDefault();
  const email=document.getElementById('wl-email').value.trim();
  const msg=document.getElementById('wl-msg');
  if(!email)return false;
  try{{
    const r=await fetch({json.dumps(signup_path)},{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{email}})}});
    if(!r.ok)throw new Error();
    msg.textContent="You're on the list — we'll be in touch.";
    document.getElementById('wl-email').value='';
  }}catch(err){{msg.textContent='Something went wrong — try again.';}}
  return false;
}}
</script>
</body></html>"""
