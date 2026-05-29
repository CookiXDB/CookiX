"""Render the 30-second CookiX demo video (reproducible).

Frames are drawn with matplotlib on the CookiX dark-amber palette, then assembled
into assets/demo.mp4 (+ a README-embeddable assets/demo.gif) via the ffmpeg CLI.

Run:  python scripts/make_demo_video.py
Needs: matplotlib (always) + ffmpeg on PATH (for the mp4/gif assembly).

Storyboard (≈30s @ 15 fps):
  0–4s   title          "CookiX — the database that explains its answers"
  4–9s   the problem    a relational question a vector search can't answer
  9–16s  the answer     the typed reasoning path lights up, edge by edge
  16–23s real use case  supply-chain: a CVE's blast radius, with the chain
  23–27s honest proof   2WikiMultiHopQA — CookiX 0.58 vs BM25 0.39 (oracle)
  27–30s call to action  pip install cookix
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch  # noqa: E402

# CookiX brand palette
BG, PANEL, TEXT, MUTED = "#1a1410", "#241b14", "#f3ead9", "#b09b82"
ACCENT, PATH, NODE, NB = "#e0a458", "#ff7a45", "#4a3b2c", "#8a6f52"

FPS = 15
W, H = 12.0, 6.75   # inches @ 100 dpi -> 1200x675
ASSETS = Path(__file__).resolve().parent.parent / "assets"

SCENES = [  # (name, duration_seconds)
    ("title", 4.0), ("problem", 5.0), ("answer", 7.0),
    ("supply", 7.0), ("proof", 4.0), ("cta", 3.0),
]


def _ease(x: float) -> float:
    return x * x * (3 - 2 * x)  # smoothstep


def _fig():
    fig = plt.figure(figsize=(W, H), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 56)
    ax.axis("off")
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    return fig, ax


def _t(ax, x, y, s, size, color=TEXT, weight="normal", ha="center", alpha=1.0, mono=False):
    ax.text(x, y, s, color=color, fontsize=size, fontweight=weight, ha=ha, va="center",
            alpha=alpha, family=("monospace" if mono else "sans-serif"))


def _node(ax, x, y, label, on=False, r=2.4, alpha=1.0):
    ax.add_patch(plt.Circle((x, y), r, facecolor=(PATH if on else NODE),
                            edgecolor=(PATH if on else NB), lw=2, alpha=alpha, zorder=3))
    _t(ax, x, y - r - 1.8, label, 11, TEXT if on else MUTED, "bold" if on else "normal",
       alpha=alpha)


def _edge(ax, p, q, rel, on=False, alpha=1.0):
    col = PATH if on else NB
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=18,
                 color=col, lw=3 if on else 1.6, alpha=alpha,
                 shrinkA=26, shrinkB=26, zorder=2))
    mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
    _t(ax, mx, my + 1.6, rel, 9.5, ACCENT if on else MUTED, alpha=alpha, mono=True)


# --------------------------------------------------------------------------- #
# Scenes (lt = local time within the scene, 0..duration)
# --------------------------------------------------------------------------- #
def title(ax, lt):
    a = _ease(min(1, lt / 0.8))
    _t(ax, 50, 38, "CookiX", 54, ACCENT, "bold", alpha=a)
    _t(ax, 50, 28, "the database that explains its answers", 19, TEXT, alpha=_ease(min(1, lt / 1.4)))
    _t(ax, 50, 18, "pip install cookix", 16, MUTED, alpha=_ease(max(0, min(1, (lt - 1.0) / 1.0))), mono=True)


def problem(ax, lt):
    _t(ax, 50, 50, "“what prevents rain?”", 22, TEXT, "bold", alpha=_ease(min(1, lt / 0.7)))
    if lt > 1.2:
        a = _ease(min(1, (lt - 1.2) / 1.2))
        pts = [(30, 30), (38, 24), (46, 33), (55, 27), (63, 22), (70, 31), (48, 18)]
        for x, y in pts:
            ax.add_patch(plt.Circle((x, y), 2.0, facecolor=NODE, edgecolor=NB, lw=1.4, alpha=a, zorder=3))
        _t(ax, 50, 9, "a vector DB returns nearby blobs — similar scores, no direction, no reason",
           14, MUTED, alpha=_ease(max(0, min(1, (lt - 2.4) / 1.2))))


def _umbrella_layout():
    return {"umbrella": (22, 34), "rain": (50, 40), "wet_coat": (78, 34),
            "raincoat": (50, 14), "storm": (24, 14)}


def answer(ax, lt):
    pos = _umbrella_layout()
    _t(ax, 50, 52, "CookiX returns the PATH that proves it", 19, TEXT, "bold",
       alpha=_ease(min(1, lt / 0.7)))
    ctx_edges = [("storm", "rain", "causes"), ("raincoat", "wet_coat", "prevents")]
    # reveal path edges one at a time
    e1 = _ease(max(0, min(1, (lt - 1.5) / 1.4)))
    e2 = _ease(max(0, min(1, (lt - 3.2) / 1.4)))
    on = {"umbrella": e1 > 0.3, "rain": e1 > 0.6, "wet_coat": e2 > 0.6}
    for s, q, rel in ctx_edges:
        _edge(ax, pos[s], pos[q], rel, on=False, alpha=0.5)
    if e1 > 0.05:
        _edge(ax, pos["umbrella"], pos["rain"], "prevents", on=True, alpha=e1)
    if e2 > 0.05:
        _edge(ax, pos["rain"], pos["wet_coat"], "causes", on=True, alpha=e2)
    for name, p in pos.items():
        _node(ax, *p, name, on=on.get(name, False))
    if lt > 4.8:
        _t(ax, 50, 5, "umbrella —[prevents]→ rain —[causes]→ wet_coat", 13, PATH, "bold",
           alpha=_ease(min(1, (lt - 4.8) / 1.0)), mono=True)


def supply(ax, lt):
    _t(ax, 50, 52, "real use case: which services does a CVE reach?", 18, TEXT, "bold",
       alpha=_ease(min(1, lt / 0.7)))
    chain = [("checkout_api", 12), ("fast_json", 36), ("tinyparse", 60), ("CVE-2024-5001", 86)]
    rels = ["depends_on", "depends_on", "affected_by"]
    y = 32
    pos = [(x, y) for _, x in chain]
    steps = [_ease(max(0, min(1, (lt - (1.2 + i * 1.3)) / 1.1))) for i in range(3)]
    for i, rel in enumerate(rels):
        if steps[i] > 0.05:
            _edge(ax, pos[i], pos[i + 1], rel, on=True, alpha=steps[i])
    for i, (label, x) in enumerate(chain):
        lit = (i == 0) or (i <= sum(1 for s in steps if s > 0.6))
        _node(ax, x, y, label, on=lit, r=2.2)
    if lt > 5.0:
        _t(ax, 50, 10, "3 hops, no shared words — the link lives only in the typed edges",
           13, MUTED, alpha=_ease(min(1, (lt - 5.0) / 1.0)))


def proof(ax, lt):
    _t(ax, 50, 52, "honest proof — 2WikiMultiHopQA (real multi-hop data)", 17, TEXT, "bold",
       alpha=_ease(min(1, lt / 0.6)))
    grow = _ease(min(1, lt / 1.6))
    base = 14
    # BM25 bar
    bm = 0.386
    ax.add_patch(plt.Rectangle((28, base), 12, 26 * bm * grow, facecolor=NB, edgecolor=NB))
    _t(ax, 34, base - 3, "BM25", 13, MUTED)
    _t(ax, 34, base + 26 * bm * grow + 2.5, f"{bm:.2f}", 13, MUTED, alpha=grow)
    # CookiX bar
    ck = 0.580
    ax.add_patch(plt.Rectangle((60, base), 12, 26 * ck * grow, facecolor=ACCENT, edgecolor=PATH, lw=2))
    _t(ax, 66, base - 3, "CookiX", 13, ACCENT, "bold")
    _t(ax, 66, base + 26 * ck * grow + 2.5, f"{ck:.2f}", 14, ACCENT, "bold", alpha=grow)
    if lt > 2.2:
        _t(ax, 50, 7, "hits@10  ·  +50% over BM25  ·  and it returns the reasoning path",
           13, TEXT, alpha=_ease(min(1, (lt - 2.2) / 1.0)))


def cta(ax, lt):
    a = _ease(min(1, lt / 0.7))
    _t(ax, 50, 36, "pip install cookix", 30, ACCENT, "bold", alpha=a, mono=True)
    _t(ax, 50, 25, "github.com/CookiXDB/CookiX", 16, TEXT, alpha=_ease(min(1, lt / 1.2)), mono=True)
    _t(ax, 50, 16, "open source · Apache-2.0 · built in Morocco", 13, MUTED,
       alpha=_ease(max(0, min(1, (lt - 0.8) / 1.0))))


RENDER = {"title": title, "problem": problem, "answer": answer,
          "supply": supply, "proof": proof, "cta": cta}


def render_frames(outdir: Path) -> int:
    idx = 0
    for name, dur in SCENES:
        for f in range(int(dur * FPS)):
            lt = f / FPS
            fig, ax = _fig()
            # subtle footer wordmark on every non-title frame
            if name not in ("title", "cta"):
                _t(ax, 6, 2.5, "CookiX", 11, MUTED, "bold", ha="left", alpha=0.7)
            RENDER[name](ax, lt)
            fig.savefig(outdir / f"f{idx:04d}.png", facecolor=BG)
            plt.close(fig)
            idx += 1
    return idx


def assemble(frames_dir: Path) -> None:
    ASSETS.mkdir(exist_ok=True)
    mp4 = ASSETS / "demo.mp4"
    gif = ASSETS / "demo.gif"
    palette = frames_dir / "palette.png"
    subprocess.run([
        "ffmpeg", "-y", "-framerate", str(FPS), "-i", str(frames_dir / "f%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", str(mp4),
    ], check=True, capture_output=True)
    # README-friendly GIF (smaller, palette-optimised)
    subprocess.run(["ffmpeg", "-y", "-i", str(mp4),
                    "-vf", "fps=12,scale=860:-1:flags=lanczos,palettegen", str(palette)],
                   check=True, capture_output=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(mp4), "-i", str(palette),
                    "-lavfi", "fps=12,scale=860:-1:flags=lanczos,paletteuse", str(gif)],
                   check=True, capture_output=True)
    print(f"wrote {mp4} ({mp4.stat().st_size//1024} KB) and {gif} ({gif.stat().st_size//1024} KB)")


def main() -> None:
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg not found on PATH — needed to assemble the video")
    tmp = Path(tempfile.mkdtemp(prefix="cookix-demo-"))
    try:
        n = render_frames(tmp)
        print(f"rendered {n} frames at {FPS} fps (~{n / FPS:.0f}s)")
        assemble(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
