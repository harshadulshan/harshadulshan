#!/usr/bin/env python3
"""Plasma serpent: a glowing energy snake that absorbs your contribution grid.

The serpent weaves through every active day of the last year (in date order).
Each square it absorbs flashes, crackles with electricity and bursts into
sparks; busier days burst bigger. When it leaves, the grid recharges from left
to right and the loop starts again. Pure SVG (SMIL + CSS), no scripts.
"""
import argparse
import datetime as dt
import json
import math
import os
import random

import blackhole as bh
from blackhole import CYAN, PURPLE, WHITE, MONO

W, H = 900, 210
CELL, GAP = 12, 3
STEP = CELL + GAP
GX, GY = 52, 62             # grid origin
TRAVEL = 11.0               # seconds the serpent is on screen
CYCLE = 14.0                # full loop
LEVEL = ["#161B22", "#164E63", "#0E7490", "#22D3EE", "#C084FC"]


def grid(data):
    days = {dt.date.fromisoformat(k): v for k, v in data["days"].items()}
    today = dt.date.fromisoformat(data["today"])
    start = today - dt.timedelta(days=(today.weekday() + 1) % 7) - dt.timedelta(weeks=52)
    cells = []
    d = start
    while d <= today:
        col, row = (d - start).days // 7, (d.weekday() + 1) % 7
        cells.append((d, col, row, days.get(d, 0)))
        d += dt.timedelta(days=1)
    vals = sorted(v for *_, v in cells if v)
    q = lambda p: vals[min(len(vals) - 1, int(p * len(vals)))] if vals else 1
    t1, t2, t3 = q(.25), q(.5), q(.75)
    out = []
    for d, c, r, v in cells:
        lvl = 0 if v == 0 else 1 if v <= t1 else 2 if v <= t2 else 3 if v <= t3 else 4
        out.append(dict(date=d, col=c, row=r, v=v, lvl=lvl,
                        x=GX + c * STEP + CELL / 2, y=GY + r * STEP + CELL / 2))
    return out, start, today


def catmull(points):
    """Catmull-Rom through points -> list of cubic segments (p0, c1, c2, p1)."""
    segs = []
    pts = [points[0]] + points + [points[-1]]
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        segs.append((p1, c1, c2, p2))
    return segs


def bez(seg, t):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = seg
    u = 1 - t
    return (u**3*x0 + 3*u*u*t*x1 + 3*u*t*t*x2 + t**3*x3, u**3*y0 + 3*u*u*t*y1 + 3*u*t*t*y2 + t**3*y3)


def seg_len(seg, n=24):
    L, prev = 0, bez(seg, 0)
    for i in range(1, n + 1):
        p = bez(seg, i / n)
        L += math.hypot(p[0] - prev[0], p[1] - prev[1])
        prev = p
    return L


def jag(rnd, x1, y1, x2, y2, n=5, amp=4):
    pts = [(x1, y1)]
    for i in range(1, n):
        t = i / n
        pts.append((x1 + (x2 - x1) * t + rnd.uniform(-amp, amp), y1 + (y2 - y1) * t + rnd.uniform(-amp, amp)))
    pts.append((x2, y2))
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)


def kt(*ts):
    return ";".join(f"{max(0, min(1, t)):.4f}" for t in ts)


def render(data, login):
    rnd = random.Random(7)
    cells, start, today = grid(data)
    active = [c for c in cells if c["v"] > 0]
    total = sum(c["v"] for c in active)

    # ---- path through active days, in date order
    mid = GY + 3 * STEP + CELL / 2
    pts = [(-60, mid), (GX - 20, mid)] + [(c["x"], c["y"]) for c in active] + [(W - 30, mid), (W + 80, mid)]
    # wiggle long empty stretches so the serpent snakes instead of sliding
    smooth = [pts[0]]
    for p in pts[1:]:
        q = smooth[-1]
        dist = p[0] - q[0]
        if dist > 4 * STEP:
            k = int(dist // (3 * STEP))
            for i in range(1, k):
                x = q[0] + dist * i / k
                y = GY + CELL / 2 + (1.5 + 1.5 * math.sin(i * 1.7 + x / 90)) * STEP * (1 if i % 2 else 1.6)
                smooth.append((x, min(GY + 6 * STEP + CELL / 2, y)))
        smooth.append(p)
    segs = catmull(smooth)
    lens = [seg_len(s) for s in segs]
    total_len = sum(lens)
    d = f"M{segs[0][0][0]:.1f} {segs[0][0][1]:.1f}" + "".join(
        f" C{s[1][0]:.1f} {s[1][1]:.1f} {s[2][0]:.1f} {s[2][1]:.1f} {s[3][0]:.1f} {s[3][1]:.1f}" for s in segs)

    # arc-length position of every point we passed through
    cum, acc = {}, 0
    for i, s in enumerate(segs):
        acc += lens[i]
        cum[s[3]] = acc
    f_travel = TRAVEL / CYCLE

    def t_at(c):  # fraction of the cycle when the head reaches this cell
        return cum[(c["x"], c["y"])] / total_len * f_travel

    o = []
    a = o.append
    a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="psT psD">')
    a(f'<title id="psT">{login} plasma serpent</title><desc id="psD">An energy serpent absorbs {len(active)} active '
      f'contribution days ({total} contributions) from the last year.</desc>')
    a(f'''<defs>
<linearGradient id="body" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="{W}" y2="0">
 <stop offset="0" stop-color="{PURPLE}"/><stop offset=".5" stop-color="{CYAN}"/><stop offset="1" stop-color="{PURPLE}"/></linearGradient>
<radialGradient id="head"><stop offset="0" stop-color="#fff"/><stop offset=".4" stop-color="{WHITE}"/>
 <stop offset=".7" stop-color="{CYAN}" stop-opacity=".6"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>
<radialGradient id="spark"><stop offset="0" stop-color="#fff"/><stop offset=".5" stop-color="{CYAN}"/>
 <stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>
<radialGradient id="sparkp"><stop offset="0" stop-color="#fff"/><stop offset=".5" stop-color="#E879F9"/>
 <stop offset="1" stop-color="{PURPLE}" stop-opacity="0"/></radialGradient>
<filter id="sg" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="5"/></filter>
<filter id="sg2" x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="1.6" result="b"/>
 <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
<clipPath id="pc"><rect width="{W}" height="{H}" rx="16"/></clipPath>
</defs>
<style>
.lbl{{font:600 10.5px {MONO};letter-spacing:2px;fill:#7D8CA3}}
.mo{{font:600 9px {MONO};fill:#64748B}}
.shim{{animation:shim .9s linear infinite}}
@keyframes shim{{to{{stroke-dashoffset:-24}}}}
.blink{{animation:blink 1.1s steps(1) infinite}}
@keyframes blink{{50%{{opacity:.25}}}}
</style>''')
    a('<g clip-path="url(#pc)">')
    a(f'<rect width="{W}" height="{H}" fill="#0D1117"/>')
    for _ in range(40):
        a(f'<circle cx="{rnd.uniform(0,W):.0f}" cy="{rnd.uniform(0,H):.0f}" r="{rnd.choice([.5,.7,1])}" fill="#94A3B8" opacity="{rnd.uniform(.15,.5):.2f}"/>')

    # header
    a(f'<circle cx="28" cy="27" r="4" fill="#F43F5E" class="blink"/>'
      f'<text x="40" y="31" class="lbl">PLASMA SERPENT // CONTRIBUTION GRID</text>'
      f'<text x="{W-26}" y="31" class="lbl" text-anchor="end">{len(active)} DAYS ABSORBED · {total} CONTRIBUTIONS</text>')

    # month labels
    seen = set()
    for c in cells:
        if c["date"].day <= 7 and c["row"] == 0 and c["col"] not in seen and c["col"] < 52:
            seen.add(c["col"])
            a(f'<text x="{GX + c["col"]*STEP}" y="{GY-8}" class="mo">{c["date"].strftime("%b")}</text>')
    for r, lab in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
        a(f'<text x="{GX-8}" y="{GY + r*STEP + 9}" class="mo" text-anchor="end">{lab}</text>')

    # ---- grid cells
    for c in cells:
        x, y = c["x"] - CELL / 2, c["y"] - CELL / 2
        if c["v"] == 0:
            a(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{LEVEL[0]}"/>')
            continue
        col = LEVEL[c["lvl"]]
        te = t_at(c)
        rel = f_travel + 0.04 + (c["col"] / 53) * (1 - f_travel - 0.1)   # recharge wave, left -> right
        a(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="2.5" fill="{col}">'
          f'<animate attributeName="fill" values="{col};{col};#FFFFFF;{LEVEL[0]};{LEVEL[0]};#FFFFFF;{col};{col}" '
          f'keyTimes="{kt(0, te-.004, te, te+.03, rel, rel+.012, rel+.04, 1)}" dur="{CYCLE}s" repeatCount="indefinite"/></rect>')
        # glow halo that pops when absorbed
        a(f'<rect x="{x-3}" y="{y-3}" width="{CELL+6}" height="{CELL+6}" rx="5" fill="{CYAN if c["lvl"] < 4 else PURPLE}" '
          f'opacity="0" filter="url(#sg2)"><animate attributeName="opacity" values="0;0;.9;0;0" '
          f'keyTimes="{kt(0, te-.002, te+.003, te+.03, 1)}" dur="{CYCLE}s" repeatCount="indefinite"/></rect>')
        # electric crackle just before the bite
        for _ in range(2):
            ang = rnd.uniform(0, 2 * math.pi)
            x2, y2 = c["x"] + 16 * math.cos(ang), c["y"] + 16 * math.sin(ang)
            ds = ";".join(jag(rnd, c["x"], c["y"], x2, y2) for _ in range(3))
            a(f'<path d="{jag(rnd, c["x"], c["y"], x2, y2)}" fill="none" stroke="{WHITE}" stroke-width="1" '
              f'filter="url(#sg2)" opacity="0"><animate attributeName="d" values="{ds}" dur=".18s" repeatCount="indefinite" calcMode="discrete"/>'
              f'<animate attributeName="opacity" values="0;0;1;.3;1;0;0" keyTimes="{kt(0, te-.022, te-.018, te-.012, te-.006, te+.002, 1)}" '
              f'dur="{CYCLE}s" repeatCount="indefinite"/></path>')
        # spark burst, bigger for busier days
        n = 4 + 2 * c["lvl"]
        for k in range(n):
            ang = 2 * math.pi * k / n + rnd.uniform(-.3, .3)
            dist = rnd.uniform(14, 22 + 7 * c["lvl"])
            sx, sy = c["x"] + dist * math.cos(ang), c["y"] + dist * math.sin(ang)
            g = "sparkp" if c["lvl"] == 4 or rnd.random() < .3 else "spark"
            ks = kt(0, te, te + .05, 1)
            a(f'<circle cx="{c["x"]}" cy="{c["y"]}" r="{rnd.uniform(1.6, 2.8):.1f}" fill="url(#{g})" opacity="0">'
              f'<animate attributeName="cx" values="{c["x"]};{c["x"]};{sx:.1f};{sx:.1f}" keyTimes="{ks}" dur="{CYCLE}s" repeatCount="indefinite"/>'
              f'<animate attributeName="cy" values="{c["y"]};{c["y"]};{sy:.1f};{sy:.1f}" keyTimes="{ks}" dur="{CYCLE}s" repeatCount="indefinite"/>'
              f'<animate attributeName="opacity" values="0;0;1;0;0" keyTimes="{kt(0, te, te+.006, te+.05, 1)}" dur="{CYCLE}s" repeatCount="indefinite"/></circle>')

    # ---- the serpent: stacked dash segments that all end at the head -> tapered glowing body
    layers = [(260, 18, PURPLE, .45, "sg"), (210, 8, "url(#body)", .95, None), (150, 4.5, CYAN, 1, None), (70, 2, "#fff", 1, None)]
    for L, w, col, op, flt in layers:
        a(f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{w}" stroke-linecap="round" opacity="{op}" '
          f'stroke-dasharray="{L} {total_len + 400:.0f}"{" filter=" + chr(34) + "url(#" + flt + ")" + chr(34) if flt else ""}>'
          f'<animate attributeName="stroke-dashoffset" values="{L};{L - total_len:.1f};{L - total_len:.1f}" '
          f'keyTimes="0;{f_travel:.4f};1" dur="{CYCLE}s" repeatCount="indefinite"/></path>')
    a(f'<g><circle r="13" fill="url(#head)"/><circle r="3.6" fill="#fff"/>'
      f'<circle r="18" fill="none" stroke="{CYAN}" stroke-width="1" stroke-dasharray="3 4" opacity=".7">'
      f'<animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="1.2s" repeatCount="indefinite"/></circle>'
      f'<animateMotion path="{d}" keyPoints="0;1;1" keyTimes="0;{f_travel:.4f};1" calcMode="linear" '
      f'dur="{CYCLE}s" repeatCount="indefinite"/></g>')

    # legend
    lx = W - 26 - 5 * 15 - 72
    a(f'<text x="{lx}" y="{H-18}" class="mo">LOW</text>')
    for i, col in enumerate(LEVEL):
        a(f'<rect x="{lx + 26 + i*15}" y="{H-27}" width="{CELL}" height="{CELL}" rx="2.5" fill="{col}"/>')
    a(f'<text x="{lx + 26 + 5*15 + 4}" y="{H-18}" class="mo">HIGH</text>')
    a(f'<text x="28" y="{H-18}" class="mo">{bh.fmt_date(start, True)} – {bh.fmt_date(today, True)}</text>')
    a('</g>')
    a(f'<rect x=".5" y=".5" width="{W-1}" height="{H-1}" rx="16" fill="none" stroke="#30363D"/>')
    a('</svg>')
    return "\n".join(o)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "harshadulshan"))
    ap.add_argument("--data")
    ap.add_argument("--out", default="assets/generated/serpent.svg")
    args = ap.parse_args()
    data = json.load(open(args.data)) if args.data else bh.fetch_github(args.login, os.environ["GITHUB_TOKEN"])
    svg = render(data, args.login)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {args.out} ({len(svg)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
