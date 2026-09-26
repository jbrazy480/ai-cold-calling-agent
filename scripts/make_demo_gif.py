"""Capture the actual offline commands and render terminal frames with Pillow."""
import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
FONT_PATH = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")
FONT = ImageFont.truetype(str(FONT_PATH), 16) if FONT_PATH.exists() else ImageFont.load_default(size=16)
WIDTH, HEIGHT = 1120, 620


def capture() -> list[str]:
    lines = []
    with tempfile.TemporaryDirectory() as temp:
        env = {**os.environ, "DATA_DIR": temp, "DNC_PATH": str(Path(temp) / "dnc.txt")}
        for module, args in [("coldcaller.run", ["--dry-run"]), ("coldcaller.simulate", [])]:
            lines.append("$ python -m " + module + (" " + " ".join(args) if args else ""))
            result = subprocess.run([sys.executable, "-m", module, *args], cwd=ROOT, env=env,
                                    text=True, capture_output=True, check=True)
            for line in result.stdout.splitlines():
                lines.extend(textwrap.wrap(line, width=108, replace_whitespace=False) or [""])
            lines.append("")
    return lines


def render(lines: list[str]):
    frames = []
    for count in range(1, len(lines) + 1):
        canvas = Image.new("RGB", (WIDTH, HEIGHT), "#0f172a")
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((12, 12, WIDTH - 12, HEIGHT - 12), radius=12, outline="#334155", width=2)
        draw.text((30, 26), "AI COLD CALLING AGENT | offline demo", font=FONT, fill="#e2e8f0")
        draw.line((30, 58, WIDTH - 30, 58), fill="#334155", width=1)
        for index, line in enumerate(lines[:count][-23:]):
            color = "#cbd5e1"
            if line.startswith("$"):
                color = "#67e8f9"
            elif line.startswith(("Tool", "Outcome")):
                color = "#86efac"
            elif line.startswith("Prospect"):
                color = "#fde68a"
            draw.text((30, 78 + index * 22), line, font=FONT, fill=color)
        frames.append(canvas.convert("P", palette=Image.Palette.ADAPTIVE, colors=32))
    target = ROOT / "docs/demo.gif"
    target.parent.mkdir(exist_ok=True)
    frames[0].save(target, save_all=True, append_images=frames[1:],
                   duration=[550] * (len(frames) - 1) + [2500], loop=0, optimize=True)
    if target.stat().st_size >= 2_000_000:
        raise RuntimeError("Demo GIF exceeded size budget")
    print(f"Generated {target.relative_to(ROOT)}: {target.stat().st_size} bytes")


if __name__ == "__main__":
    render(capture())
