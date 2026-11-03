#!/usr/bin/env python3
"""Black hole contribution-streak card for a GitHub profile README.

Every contribution day becomes matter spiralling into a black hole. The total,
current streak and longest streak are shown on a HUD panel next to it.

Output is a single self-contained animated SVG (CSS + SMIL, no scripts, no
external fonts), so it animates when GitHub shows it in a README.

Data source:
  * In GitHub Actions: GraphQL API with GITHUB_TOKEN (all years since signup).
  * Locally: --data data/contributions.json  ({"today": "...", "days": {"YYYY-MM-DD": n}})
"""
import argparse
import datetime as dt
import json
import math
import os
import random
import urllib.request

W, H = 900, 360
CX, CY = 225, 180          # black hole centre
TILT = -9                  # disk tilt in degrees
SQUASH = 0.27              # perspective squash of the disk
HORIZON = 54               # event horizon radius

CYAN, PURPLE, WHITE = "#00D9FF", "#A855F7", "#E8FDFF"
MONO = "'JetBrains Mono','Fira Code',Consolas,'Courier New',monospace"
SANS = "'Segoe UI',Inter,Roboto,'Helvetica Neue',Arial,sans-serif"


# ----------------------------------------------------------------- data
def fetch_github(login, token):
    def gql(query, variables):
        req = urllib.request.Request(
            "https://api.github.com/graphql",
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            out = json.load(r)
        if "errors" in out:
            raise RuntimeError(out["errors"])
        return out["data"]

    created = gql("query($l:String!){user(login:$l){createdAt}}", {"l": login})["user"]["createdAt"]
    start_year = int(created[:4])
    now = dt.datetime.now(dt.timezone.utc)
    q = """query($l:String!,$f:DateTime!,$t:DateTime!){user(login:$l){
      contributionsCollection(from:$f,to:$t){contributionCalendar{
        weeks{contributionDays{date contributionCount}}}}}}"""
    days = {}
    for year in range(start_year, now.year + 1):
        f = f"{year}-01-01T00:00:00Z"
        t = f"{year}-12-31T23:59:59Z" if year < now.year else now.strftime("%Y-%m-%dT%H:%M:%SZ")
        cal = gql(q, {"l": login, "f": f, "t": t})["user"]["contributionsCollection"]["contributionCalendar"]
        for w in cal["weeks"]:
            for d in w["contributionDays"]:
                if d["contributionCount"]:
                    days[d["date"]] = d["contributionCount"]
    today = max([now.date().isoformat()] + list(days))
    return {"login": login, "today": today, "days": days}


def stats(data):
    days = {dt.date.fromisoformat(k): v for k, v in data["days"].items() if v > 0}
    today = dt.date.fromisoformat(data["today"])
    total = sum(days.values())
    first = min(days) if days else today

    # longest streak
    best, best_s, best_e, run, run_s = 0, None, None, 0, None
    d = first
    while d <= today:
        if d in days:
            run, run_s = (run + 1, run_s or d)
            if run >= best:
                best, best_s, best_e = run, run_s, d
        else:
            run, run_s = 0, None
        d += dt.timedelta(days=1)

    # current streak: alive if today or yesterday has a contribution
    cur, cur_s, cur_e = 0, None, None
    d = today if today in days else today - dt.timedelta(days=1)
    if d in days:
        cur_e = d
        while d in days:
            cur, cur_s = cur + 1, d
            d -= dt.timedelta(days=1)

    # last 12 months
    months = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append((y, m))
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    months.reverse()
    monthly = [sum(v for k, v in days.items() if (k.year, k.month) == ym) for ym in months]

    recent = sorted((k, v) for k, v in days.items() if (today - k).days < 365)
    return dict(total=total, first=first, today=today, best=best, best_s=best_s, best_e=best_e,
                cur=cur, cur_s=cur_s, cur_e=cur_e, months=months, monthly=monthly, recent=recent,
                active=len(days))


# ----------------------------------------------------------------- helpers
def fmt_date(d, year=False):
    if d is None:
        return "—"
    s = f"{d.strftime('%b')} {d.day}"
    return s + f", {d.year}" if year else s


def rng_text(a, b):
    if a is None:
        return "No active streak"
    return fmt_date(a) if a == b else f"{fmt_date(a)} – {fmt_date(b)}"


def disk_point(r, ang):
    x, y = r * math.cos(ang), r * math.sin(ang) * SQUASH
    t = math.radians(TILT)
    return CX + x * math.cos(t) - y * math.sin(t), CY + x * math.sin(t) + y * math.cos(t)


def spiral_path(r0, a0, turns, n=56):
    pts = []
    for i in range(n + 1):
        t = i / n
        r = HORIZON - 4 + (r0 - HORIZON + 4) * (1 - t) ** 1.35
        x, y = disk_point(r, a0 - turns * 2 * math.pi * t)
        pts.append(f"{x:.1f} {y:.1f}")
    return "M" + " L".join(pts)


# ----------------------------------------------------------------- render
def hud(a, s, login, L):
    # ---------- HUD panel
    px = 452
    a(f'<rect class="in" x="{px}" y="22" width="{W-px-22}" height="{H-44}" rx="14" fill="url(#panel)" '
      f'stroke="#30363D" style="animation-delay:.1s"/>')
    a(f'<g class="in" style="animation-delay:.25s"><circle cx="{px+24}" cy="46" r="4" fill="#F43F5E" class="blink"/>'
      f'<text x="{px+36}" y="50" class="lbl">{L["title"]}</text>'
      f'<text x="{W-44}" y="50" class="lbl" text-anchor="end">@{login}</text></g>')
    a(f'<line x1="{px+18}" y1="62" x2="{W-40}" y2="62" stroke="#30363D"/>')

    # total with count-up + glitch
    total = s["total"]
    ty = 122
    a(f'<g class="shake"><g transform="translate({px+22} {ty})">')
    steps = 16
    for i in range(steps + 1):
        val = round(total * (1 - (1 - i / steps) ** 2.2)) if i < steps else total
        t0 = 0.4 + i * 0.07
        if i < steps:
            a(f'<text class="big" fill="{WHITE}" opacity="0"><set attributeName="opacity" to="1" begin="{t0:.2f}s"/>'
              f'<set attributeName="opacity" to="0" begin="{t0+0.07:.2f}s"/>{val}</text>')
        else:
            a(f'<text class="gA big" fill="{CYAN}">{val}</text><text class="gB big" fill="#F43F5E">{val}</text>'
              f'<text class="big" fill="{WHITE}" opacity="0"><set attributeName="opacity" to="1" begin="{t0:.2f}s"/>{val}</text>')
    a('</g></g>')
    a(f'<text class="in sub" x="{px+24}" y="{ty+24}" style="animation-delay:.6s">TOTAL CONTRIBUTIONS · '
      f'{fmt_date(s["first"], True)} – Present</text>')

    # streak blocks
    by = 186
    cols = [(px + 24, "CURRENT STREAK", s["cur"], rng_text(s["cur_s"], s["cur_e"]), CYAN),
            (px + 230, "LONGEST STREAK", s["best"], rng_text(s["best_s"], s["best_e"]), PURPLE)]
    for i, (x, lbl, val, rng, col) in enumerate(cols):
        a(f'<g class="in" style="animation-delay:{0.8+i*0.2:.1f}s"><text x="{x}" y="{by}" class="lbl">{lbl}</text>'
          f'<text x="{x}" y="{by+38}" class="mid" fill="{col}" filter="url(#glow)">{val}</text>'
          f'<text x="{x + 22 * len(str(val)) + 6}" y="{by+38}" class="unit">{"day" if val == 1 else "days"}</text>'
          f'<text x="{x}" y="{by+58}" class="sub">{rng}</text></g>')

    # gravity well progress (current vs longest)
    gy = 284
    gw = 186
    ratio = (s["cur"] / s["best"]) if s["best"] else 0
    record = s["cur"] > 0 and s["cur"] >= s["best"]
    a(f'<g class="in" style="animation-delay:1.2s"><text x="{px+24}" y="{gy}" class="lbl">{L["well"]}</text>'
      f'<rect x="{px+24}" y="{gy+8}" width="{gw}" height="6" rx="3" fill="#1F2937"/>'
      f'<rect x="{px+24}" y="{gy+8}" width="0" height="6" rx="3" fill="url(#prog)" filter="url(#glow)">'
      f'<animate attributeName="width" from="0" to="{gw*min(1,ratio):.1f}" begin="1.4s" dur="1.4s" fill="freeze" '
      f'calcMode="spline" keySplines=".2 .8 .2 1" keyTimes="0;1"/></rect>')
    label = "NEW RECORD" if record else f"{round(ratio*100)}% OF RECORD"
    col = CYAN if record else "#94A3B8"
    mark = "▲ " if record else ""
    cls = "sub blink" if record else "sub"
    a(f'<text x="{px+24}" y="{gy+34}" class="{cls}" style="fill:{col}">{mark}{label}</text></g>')

    # 12-month accretion chart
    cx0, cw, ch, base = px + 230, 13, 30, 336
    mxm = max(s["monthly"] + [1])
    a(f'<g class="in" style="animation-delay:1.3s"><text x="{cx0}" y="{gy}" class="lbl">{L["chart"]}</text>')
    for i, (v, (yy, mm)) in enumerate(zip(s["monthly"], s["months"])):
        h = max(2, ch * v / mxm)
        x = cx0 + i * (cw + 3)
        a(f'<rect x="{x}" y="{base-12}" width="{cw}" height="0" rx="2" fill="url(#bar)" opacity="{.35 if v == 0 else .95}">'
          f'<animate attributeName="height" from="0" to="{h:.1f}" begin="{1.5+i*0.06:.2f}s" dur=".7s" fill="freeze"/>'
          f'<animate attributeName="y" from="{base-12}" to="{base-12-h:.1f}" begin="{1.5+i*0.06:.2f}s" dur=".7s" fill="freeze"/></rect>')
        a(f'<text x="{x+cw/2}" y="{base}" text-anchor="middle" style="font:600 8px {MONO};fill:#64748B">'
          f'{dt.date(yy, mm, 1).strftime("%b")[0]}</text>')
    a('</g>')



LABELS = dict(title='EVENT HORIZON', well='GRAVITY WELL', chart='ACCRETION · 12 MO')


def blackhole_scene(a, s, rnd):
    # ---------- halo + back of disk
    a(f'<circle class="breath" cx="{CX}" cy="{CY}" r="210" fill="url(#halo)"/>')
    t = math.radians(TILT)

    def disk_layer(clip):
        g = [f'<g clip-path="url(#{clip})" transform="rotate({TILT} {CX} {CY})">']
        for i, rx in enumerate(range(70, 206, 9)):
            ry = rx * SQUASH
            w = 1.2 + (1 - (rx - 70) / 136) * 4.5
            op = 0.95 - (rx - 70) / 136 * 0.7
            dash = f"{rnd.randint(10,60)} {rnd.randint(6,30)} {rnd.randint(2,14)} {rnd.randint(8,26)}"
            dur = 2.2 + (rx - 70) / 20
            g.append(f'<ellipse class="flow" cx="{CX}" cy="{CY}" rx="{rx}" ry="{ry:.1f}" stroke="url(#dop)" '
                     f'stroke-width="{w:.1f}" stroke-opacity="{op:.2f}" stroke-dasharray="{dash}" '
                     f'style="animation-duration:{dur:.1f}s"/>')
        g.append(f'<ellipse cx="{CX}" cy="{CY}" rx="150" ry="{150*SQUASH:.0f}" fill="none" stroke="url(#dop)" '
                 f'stroke-width="26" stroke-opacity=".22" filter="url(#blur6)"/>')
        g.append('</g>')
        return "".join(g)

    a(disk_layer("back"))

    # ---------- gravitational lensing: the far side of the disk bent over and under the hole
    a(f'<g class="pulse"><circle cx="{CX}" cy="{CY}" r="{HORIZON+16}" fill="none" stroke="url(#lens)" '
      f'stroke-width="26" filter="url(#blur6)" opacity=".75"/>'
      f'<circle cx="{CX}" cy="{CY}" r="{HORIZON+11}" fill="none" stroke="url(#lens)" stroke-width="9" opacity=".95" filter="url(#blur2)"/>'
      f'<circle class="flow" cx="{CX}" cy="{CY}" r="{HORIZON+9}" stroke="#fff" stroke-width="2" stroke-opacity=".7" '
      f'stroke-dasharray="30 12 6 14" style="animation-duration:3s"/></g>')
    a(f'<circle class="spin" cx="{CX}" cy="{CY}" r="{HORIZON+26}" fill="none" stroke="{CYAN}" stroke-width="1" '
      f'stroke-dasharray="2 9 14 9" opacity=".55"/>')
    a(f'<circle class="spinr" cx="{CX}" cy="{CY}" r="{HORIZON+34}" fill="none" stroke="{PURPLE}" stroke-width=".8" '
      f'stroke-dasharray="40 18 3 18" opacity=".45"/>')

    # ---------- contribution days falling in
    recent = s["recent"]
    mx = max([v for _, v in recent] + [1])
    parts = []
    for day, v in recent:
        n = 1 + min(4, round(4 * v / mx + 0.4))           # bigger days spawn more matter
        for _ in range(n):
            parts.append(v / mx)
    if not parts:
        parts = [0.2] * 12
    rnd.shuffle(parts)
    cycle = 9.0
    for i, k in enumerate(parts[:160]):
        r0 = rnd.uniform(140, 205)
        a0 = rnd.uniform(0, 2 * math.pi)
        turns = rnd.uniform(1.3, 2.3)
        dur = rnd.uniform(6.5, 10)
        begin = -(i / max(1, len(parts[:160]))) * cycle - rnd.uniform(0, 3)
        size = 2.2 + k * 4.8
        grad = 4 if k > .75 else 3 if k > .5 else 2 if k > .3 else rnd.choice([0, 1])
        path = spiral_path(r0, a0, turns)
        a(f'<circle r="{size:.1f}" fill="url(#p{grad})">'
          f'<animateMotion dur="{dur:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite" path="{path}"/>'
          f'<animate attributeName="opacity" values="0;1;1;.9;0" keyTimes="0;.08;.7;.9;1" dur="{dur:.2f}s" '
          f'begin="{begin:.2f}s" repeatCount="indefinite"/>'
          f'<animate attributeName="r" values="{size:.1f};{size:.1f};{size*.35:.1f}" keyTimes="0;.75;1" '
          f'dur="{dur:.2f}s" begin="{begin:.2f}s" repeatCount="indefinite"/></circle>')

    # ---------- event horizon + photon ring
    a(f'<circle cx="{CX}" cy="{CY}" r="{HORIZON}" fill="#000"/>')
    a(f'<circle cx="{CX}" cy="{CY}" r="{HORIZON+1.5}" fill="none" stroke="{WHITE}" stroke-width="1.6" filter="url(#glow)"/>')

    # ---------- front of disk (passes in front of the hole)
    a(disk_layer("front"))

    # ---------- relativistic jets
    a(f'<g opacity=".55" filter="url(#blur2)"><path d="M{CX} {CY-HORIZON-6} L{CX-3} {CY-150} L{CX+3} {CY-150}Z" fill="{CYAN}">'
      f'<animate attributeName="opacity" values=".2;.9;.2" dur="2.6s" repeatCount="indefinite"/></path>'
      f'<path d="M{CX} {CY+HORIZON+6} L{CX-3} {CY+150} L{CX+3} {CY+150}Z" fill="{PURPLE}">'
      f'<animate attributeName="opacity" values=".9;.2;.9" dur="2.6s" repeatCount="indefinite"/></path></g>')



def render(s, login, scene=blackhole_scene, labels=LABELS, extra_defs="", extra_css=""):
    rnd = random.Random(42)
    out = []
    a = out.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
      f'role="img" aria-labelledby="bhT bhD">')
    a(f'<title id="bhT">{login} contribution black hole</title>')
    a(f'<desc id="bhD">{s["total"]} total contributions. Current streak {s["cur"]} days. '
      f'Longest streak {s["best"]} days.</desc>')

    # ---------- defs
    a('<defs>')
    a(f'''<radialGradient id="halo" cx="{CX}" cy="{CY}" r="210" gradientUnits="userSpaceOnUse">
  <stop offset="0" stop-color="{PURPLE}" stop-opacity=".55"/><stop offset=".35" stop-color="#5B21B6" stop-opacity=".25"/>
  <stop offset="1" stop-color="#0D1117" stop-opacity="0"/></radialGradient>
<linearGradient id="dop" x1="{CX-200}" y1="0" x2="{CX+200}" y2="0" gradientUnits="userSpaceOnUse">
  <stop offset="0" stop-color="#FFFFFF"/><stop offset=".25" stop-color="{CYAN}"/>
  <stop offset=".7" stop-color="{PURPLE}"/><stop offset="1" stop-color="#4C1D95"/></linearGradient>
<linearGradient id="lens" x1="0" y1="{CY-90}" x2="0" y2="{CY+90}" gradientUnits="userSpaceOnUse">
  <stop offset="0" stop-color="#FFFFFF"/><stop offset=".3" stop-color="{CYAN}"/>
  <stop offset=".62" stop-color="{PURPLE}" stop-opacity=".55"/><stop offset="1" stop-color="{CYAN}" stop-opacity=".8"/></linearGradient>
<linearGradient id="bar" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="{PURPLE}"/><stop offset="1" stop-color="{CYAN}"/></linearGradient>
<linearGradient id="prog" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CYAN}"/><stop offset="1" stop-color="{PURPLE}"/></linearGradient>
<linearGradient id="panel" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#111827" stop-opacity=".85"/><stop offset="1" stop-color="#0B0F1A" stop-opacity=".6"/></linearGradient>
<filter id="blur6" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6"/></filter>
<filter id="blur2" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2"/></filter>
<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="2.4" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="back"><rect x="{CX-260}" y="{CY-140}" width="520" height="140"/></clipPath>
<clipPath id="front"><rect x="{CX-260}" y="{CY}" width="520" height="140"/></clipPath>
<clipPath id="card"><rect width="{W}" height="{H}" rx="16"/></clipPath>''')
    for i, c in enumerate([CYAN, "#7DD3FC", PURPLE, "#F0ABFC", "#FFFFFF"]):
        a(f'<radialGradient id="p{i}"><stop offset="0" stop-color="#fff"/><stop offset=".35" stop-color="{c}"/>'
          f'<stop offset="1" stop-color="{c}" stop-opacity="0"/></radialGradient>')
    a(extra_defs)
    a('</defs>')

    # ---------- styles
    a(f'''<style>
.tw{{animation:tw 3s ease-in-out infinite}}
@keyframes tw{{0%,100%{{opacity:.15}}50%{{opacity:.9}}}}
.flow{{fill:none;animation:flow linear infinite}}
@keyframes flow{{to{{stroke-dashoffset:-400}}}}
.spin{{transform-origin:{CX}px {CY}px;animation:spin 14s linear infinite}}
.spinr{{transform-origin:{CX}px {CY}px;animation:spin 22s linear infinite reverse}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.pulse{{animation:pulse 3.2s ease-in-out infinite}}
@keyframes pulse{{0%,100%{{opacity:.75}}50%{{opacity:1}}}}
.breath{{transform-origin:{CX}px {CY}px;animation:breath 6s ease-in-out infinite}}
@keyframes breath{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.06)}}}}
.in{{opacity:0;animation:in .8s ease-out forwards}}
@keyframes in{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
.gA,.gB{{opacity:0;animation:glitch 5s steps(1) infinite}}
.gB{{animation-delay:.07s}}
@keyframes glitch{{0%,86%,100%{{opacity:0;transform:none}}87%{{opacity:.85;transform:translate(-4px,1px)}}
 89%{{opacity:.85;transform:translate(3px,-2px)}}91%{{opacity:.6;transform:translate(-2px,0)}}93%{{opacity:0}}}}
.shake{{animation:shake 5s steps(1) infinite}}
@keyframes shake{{0%,86%,94%,100%{{transform:none}}88%{{transform:translate(1px,0) skewX(-6deg)}}90%{{transform:translate(-1px,0)}}}}
.blink{{animation:blink 1.1s steps(1) infinite}}
@keyframes blink{{50%{{opacity:.25}}}}
.scan{{animation:scan 4.5s linear infinite}}
@keyframes scan{{from{{transform:translateY(-20px)}}to{{transform:translateY({H+20}px)}}}}
{extra_css}
.lbl{{font:600 10.5px {MONO};letter-spacing:2px;fill:#7D8CA3}}
.sub{{font:500 12px {MONO};fill:#94A3B8}}
.big{{font:800 58px {SANS};letter-spacing:-1px}}
.mid{{font:800 34px {SANS}}}
.unit{{font:600 14px {SANS};fill:#94A3B8}}
</style>''')

    a('<g clip-path="url(#card)">')
    a(f'<rect width="{W}" height="{H}" fill="#0D1117"/>')

    # ---------- stars (some get "lensed" toward the hole)
    for _ in range(90):
        x, y = rnd.uniform(0, W), rnd.uniform(0, H)
        r = rnd.choice([.5, .6, .8, 1, 1.2, 1.5])
        a(f'<circle class="tw" cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="#CBD5E1" '
          f'style="animation-delay:{rnd.uniform(0,3):.2f}s;animation-duration:{rnd.uniform(2,5):.1f}s"/>')

    scene(a, s, rnd)
    hud(a, s, login, labels)
    # scanline + frame
    a(f'<rect class="scan" x="0" y="0" width="{W}" height="2" fill="{CYAN}" opacity=".06"/>')
    a('</g>')
    a(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="16" fill="none" stroke="#30363D"/>')
    a('</svg>')
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "harshadulshan"))
    ap.add_argument("--data", help="local JSON instead of the GitHub API")
    ap.add_argument("--out", default="assets/generated/blackhole.svg")
    args = ap.parse_args()

    if args.data:
        data = json.load(open(args.data))
    else:
        token = os.environ["GITHUB_TOKEN"]
        data = fetch_github(args.login, token)
    s = stats(data)
    svg = render(s, args.login)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {args.out} ({len(svg)/1024:.0f} KB) total={s['total']} cur={s['cur']} best={s['best']}")


if __name__ == "__main__":
    main()
