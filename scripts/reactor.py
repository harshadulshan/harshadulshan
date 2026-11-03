#!/usr/bin/env python3
"""Plasma reactor core streak card.

Same data and stats panel as blackhole.py, but the left side is a plasma
reactor: a churning plasma core held by spinning gimbal rings, with electric
arcs and every contribution day orbiting as a charged particle. The longer the
current streak (relative to the record), the bigger and brighter the core.
"""
import argparse
import json
import math
import os
import random

import blackhole as bh
from blackhole import CX, CY, CYAN, PURPLE, WHITE

LABELS = dict(title="REACTOR CORE", well="CORE OUTPUT", chart="ENERGY · 12 MO")

EXTRA_DEFS = f'''
<radialGradient id="core"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".3" stop-color="#E0FBFF"/>
  <stop offset=".6" stop-color="{CYAN}"/><stop offset="1" stop-color="{CYAN}" stop-opacity="0"/></radialGradient>
<radialGradient id="chamber" cx="{CX}" cy="{CY}" r="200" gradientUnits="userSpaceOnUse">
  <stop offset="0" stop-color="{CYAN}" stop-opacity=".35"/><stop offset=".4" stop-color="{PURPLE}" stop-opacity=".18"/>
  <stop offset="1" stop-color="#0D1117" stop-opacity="0"/></radialGradient>
<radialGradient id="fade" cx="{CX}" cy="{CY}" r="200" gradientUnits="userSpaceOnUse">
  <stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>
<mask id="hexmask"><rect width="460" height="360" fill="url(#fade)"/></mask>
<pattern id="hex" width="24" height="41.6" patternUnits="userSpaceOnUse">
  <path d="M12 0 L24 6.9 L24 20.8 L12 27.7 L0 20.8 L0 6.9Z M12 27.7 L12 41.6" fill="none" stroke="{CYAN}" stroke-width=".6"/></pattern>
<linearGradient id="ringg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#FFFFFF"/>
  <stop offset=".35" stop-color="{CYAN}"/><stop offset="1" stop-color="{PURPLE}"/></linearGradient>
<filter id="plasma" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="7"/></filter>
<filter id="arc" x="-20%" y="-20%" width="140%" height="140%"><feGaussianBlur stdDeviation="1.2" result="b"/>
  <feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
'''

EXTRA_CSS = f'''
.orb{{transform-origin:{CX}px {CY}px;animation:spin linear infinite;mix-blend-mode:screen}}
.throb{{transform-origin:{CX}px {CY}px;animation:throb 1.6s ease-in-out infinite}}
@keyframes throb{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.12)}}}}
.flick{{animation:flick 2.2s steps(1) infinite}}
@keyframes flick{{0%,100%{{opacity:0}}12%{{opacity:1}}18%{{opacity:.2}}22%{{opacity:1}}30%{{opacity:0}}}}
.inj{{fill:none;stroke-dasharray:4 10;animation:inj .6s linear infinite}}
@keyframes inj{{to{{stroke-dashoffset:14}}}}
'''


def jag(rnd, x1, y1, x2, y2, n=9, amp=9):
    pts = [(x1, y1)]
    for i in range(1, n):
        t = i / n
        x, y = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
        nx, ny = -(y2 - y1), (x2 - x1)
        L = math.hypot(nx, ny) or 1
        o = rnd.uniform(-amp, amp) * math.sin(math.pi * t)
        pts.append((x + nx / L * o, y + ny / L * o))
    pts.append((x2, y2))
    return "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)


def ellipse_path(rx, ry, rot, n=48):
    r = math.radians(rot)
    pts = []
    for i in range(n + 1):
        t = 2 * math.pi * i / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        pts.append(f"{CX + x*math.cos(r) - y*math.sin(r):.1f} {CY + x*math.sin(r) + y*math.cos(r):.1f}")
    return "M" + " L".join(pts) + "Z"


def reactor_scene(a, s, rnd):
    power = 0.7 + 0.3 * (min(1, s["cur"] / s["best"]) if s["best"] else 0)

    # chamber: glow + hex lattice
    a(f'<circle class="breath" cx="{CX}" cy="{CY}" r="200" fill="url(#chamber)"/>')
    a(f'<rect width="460" height="360" fill="url(#hex)" opacity=".13" mask="url(#hexmask)"/>')

    # outer containment ring with ticks
    ticks = []
    for i in range(72):
        ang = math.radians(i * 5)
        r1, r2 = (150, 158) if i % 6 else (146, 162)
        ticks.append(f"M{CX + r1*math.cos(ang):.1f} {CY + r1*math.sin(ang):.1f} L{CX + r2*math.cos(ang):.1f} {CY + r2*math.sin(ang):.1f}")
    a(f'<g class="spinr" style="animation-duration:60s"><path d="{" ".join(ticks)}" stroke="{CYAN}" stroke-width="1" opacity=".35"/>'
      f'<circle cx="{CX}" cy="{CY}" r="166" fill="none" stroke="{PURPLE}" stroke-width="1.2" stroke-dasharray="60 30 8 30" opacity=".5"/></g>')
    a(f'<circle class="spin" style="animation-duration:30s" cx="{CX}" cy="{CY}" r="140" fill="none" stroke="{CYAN}" '
      f'stroke-width="2" stroke-dasharray="1 7" opacity=".5"/>')

    # injector beams feeding the core
    for k in range(4):
        ang = math.radians(45 + k * 90)
        x1, y1 = CX + 144 * math.cos(ang), CY + 144 * math.sin(ang)
        x2, y2 = CX + 42 * math.cos(ang), CY + 42 * math.sin(ang)
        a(f'<path class="inj" d="M{x1:.1f} {y1:.1f} L{x2:.1f} {y2:.1f}" stroke="{CYAN if k % 2 else PURPLE}" '
          f'stroke-width="2.4" opacity=".7" filter="url(#glow)"/>')
        a(f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="4" fill="#0D1117" stroke="{CYAN}" stroke-width="1.5"/>')

    # gimbal rings: ellipses that "turn" in 3D by animating ry
    for i, (rx, rot, dur) in enumerate([(122, 0, 5.5), (104, 60, 7), (86, 120, 4.6)]):
        ry_vals = f"{rx};{rx*.12:.0f};{rx}" if i != 1 else f"{rx*.12:.0f};{rx};{rx*.12:.0f}"
        a(f'<g transform="rotate({rot} {CX} {CY})"><ellipse cx="{CX}" cy="{CY}" rx="{rx}" ry="{rx}" fill="none" '
          f'stroke="url(#ringg)" stroke-width="{3 - i*.6:.1f}" stroke-dasharray="{24 + i*10} 6 3 6" opacity=".85">'
          f'<animate attributeName="ry" values="{ry_vals}" dur="{dur}s" repeatCount="indefinite" calcMode="spline" '
          f'keyTimes="0;.5;1" keySplines=".45 0 .55 1;.45 0 .55 1"/>'
          f'<animate attributeName="stroke-dashoffset" from="0" to="-200" dur="{dur*1.4:.1f}s" repeatCount="indefinite"/>'
          f'</ellipse></g>')

    # contribution days as charged particles in orbit
    recent = s["recent"]
    mx = max([v for _, v in recent] + [1])
    parts = []
    for day, v in recent:
        parts += [v / mx] * (1 + min(3, round(3 * v / mx + 0.3)))
    rnd.shuffle(parts)
    for i, k in enumerate(parts[:120]):
        rx = rnd.uniform(64, 132)
        ry = rx * rnd.uniform(.18, .55)
        rot = rnd.uniform(0, 180)
        dur = (rnd.uniform(3.5, 7) * (1.25 - .5 * k)) / power
        size = 1.6 + k * 3.6
        grad = 4 if k > .75 else 3 if k > .5 else 2 if k > .3 else rnd.choice([0, 1])
        rev = ' keyPoints="1;0" keyTimes="0;1" calcMode="linear"' if rnd.random() < .35 else ""
        a(f'<circle r="{size:.1f}" fill="url(#p{grad})"><animateMotion dur="{dur:.2f}s" begin="{-rnd.uniform(0, 8):.2f}s" '
          f'repeatCount="indefinite" path="{ellipse_path(rx, ry, rot)}"{rev}/></circle>')

    # electric arcs: each flickers between 3 jagged shapes
    for i in range(7):
        ang = rnd.uniform(0, 2 * math.pi)
        r_end = rnd.uniform(86, 128)
        x1, y1 = CX + 24 * math.cos(ang), CY + 24 * math.sin(ang)
        x2, y2 = CX + r_end * math.cos(ang + rnd.uniform(-.4, .4)), CY + r_end * math.sin(ang + rnd.uniform(-.4, .4))
        ds = ";".join(jag(rnd, x1, y1, x2, y2) for _ in range(3))
        col = rnd.choice([WHITE, CYAN, "#C4B5FD"])
        a(f'<path class="flick" d="{jag(rnd, x1, y1, x2, y2)}" fill="none" stroke="{col}" stroke-width="1.3" '
          f'filter="url(#arc)" style="animation-delay:{rnd.uniform(0, 2.2):.2f}s;animation-duration:{rnd.uniform(1.6, 3.4):.1f}s">'
          f'<animate attributeName="d" values="{ds}" dur=".24s" repeatCount="indefinite" calcMode="discrete"/></path>')

    # plasma core: blurred blobs churning around each other
    pr = 42 * power
    a(f'<circle cx="{CX}" cy="{CY}" r="{pr*2.2:.0f}" fill="{CYAN}" opacity=".25" filter="url(#plasma)" class="throb"/>')
    a(f'<g filter="url(#plasma)">')
    blobs = [(CYAN, 9, 0), (PURPLE, 6.5, 120), ("#F0ABFC", 11, 240), ("#7DD3FC", 4.8, 60), ("#FFFFFF", 7.5, 300)]
    for col, dur, ph in blobs:
        ox = pr * .45 * math.cos(math.radians(ph))
        oy = pr * .45 * math.sin(math.radians(ph))
        a(f'<ellipse class="orb" cx="{CX + ox:.1f}" cy="{CY + oy:.1f}" rx="{pr*.95:.1f}" ry="{pr*.6:.1f}" fill="{col}" '
          f'opacity=".7" style="animation-duration:{dur}s;animation-direction:{"reverse" if ph % 120 else "normal"}"/>')
    a('</g>')
    a(f'<g class="throb"><circle cx="{CX}" cy="{CY}" r="{pr*.62:.1f}" fill="url(#core)"/>'
      f'<circle cx="{CX}" cy="{CY}" r="{pr*.2:.1f}" fill="#fff"/></g>')
    a(f'<circle cx="{CX}" cy="{CY}" r="{pr+16:.0f}" fill="none" stroke="{WHITE}" stroke-width="1" opacity=".5" '
      f'stroke-dasharray="3 5" class="spin" style="animation-duration:4s"/>')

    # readout under the reactor
    a(f'<text x="{CX}" y="{CY+170}" text-anchor="middle" class="lbl" style="fill:{CYAN}">'
      f'CORE TEMP {int(4000 + 6000*power):,} K · CONTAINMENT STABLE</text>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--login", default=os.environ.get("GITHUB_REPOSITORY_OWNER", "harshadulshan"))
    ap.add_argument("--data")
    ap.add_argument("--out", default="assets/generated/reactor.svg")
    args = ap.parse_args()
    data = json.load(open(args.data)) if args.data else bh.fetch_github(args.login, os.environ["GITHUB_TOKEN"])
    s = bh.stats(data)
    svg = bh.render(s, args.login, scene=reactor_scene, labels=LABELS, extra_defs=EXTRA_DEFS, extra_css=EXTRA_CSS)
    svg = svg.replace("contribution black hole", "contribution reactor core")
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"wrote {args.out} ({len(svg)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
