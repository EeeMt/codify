#!/usr/bin/env python3
"""Render every guide diagram and pin its intrinsic size.

`d2` writes an SVG whose root element carries no `width`/`height`, so a browser
that embeds the file falls back to its default intrinsic size and draws the
diagram at the wrong aspect ratio. The guide embeds these SVGs as `<img>`, so
this is not a cosmetic step: before it, an 867x351 diagram was laid out from a
300x117 natural size.

Run from the repository root:

    python3 scripts/guide/render-diagrams.py

Idempotent: re-running reproduces the committed files byte for byte.
`frontend/src/guide/guideContent.spec.ts` fails when a diagram is missing the
attributes, so a bare `d2` run cannot slip through unnoticed.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIAGRAM_ROOT = REPO_ROOT / "frontend" / "src" / "guide" / "assets" / "diagrams"

ROOT_SVG_TAG = re.compile(r"<svg\b[^>]*>")
VIEW_BOX = re.compile(r'viewBox="0 0 ([\d.]+) ([\d.]+)"')


def pin_intrinsic_size(svg_path: Path) -> tuple[str, str, bool]:
    """Copy the root viewBox size onto the root element. Returns (w, h, changed)."""
    text = svg_path.read_text(encoding="utf-8")
    tag_match = ROOT_SVG_TAG.search(text)
    if tag_match is None:
        raise SystemExit(f"{svg_path}: no root <svg> element")

    tag = tag_match.group(0)
    box = VIEW_BOX.search(tag)
    if box is None:
        raise SystemExit(f"{svg_path}: root <svg> has no '0 0 W H' viewBox")

    width, height = box.group(1), box.group(2)
    pinned = f'viewBox="0 0 {width} {height}" width="{width}" height="{height}"'
    if pinned in tag:
        return width, height, False

    rebuilt = tag.replace(f'viewBox="0 0 {width} {height}"', pinned)
    svg_path.write_text(text[: tag_match.start()] + rebuilt + text[tag_match.end() :], encoding="utf-8")
    return width, height, True


def main() -> int:
    sources = sorted(DIAGRAM_ROOT.glob("*/*.d2"))
    if not sources:
        print(f"no .d2 sources under {DIAGRAM_ROOT}", file=sys.stderr)
        return 1

    failures: list[str] = []
    for source in sources:
        target = source.with_suffix(".svg")
        rendered = subprocess.run(
            [
                "d2",
                str(source.relative_to(REPO_ROOT)),
                str(target.relative_to(REPO_ROOT)),
                "--pad",
                "24",
                "--theme",
                "0",
                "--layout",
                "elk",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        if rendered.returncode != 0:
            failures.append(f"{source.relative_to(REPO_ROOT)}: d2 failed\n{rendered.stderr.strip()}")
            continue

        width, height, changed = pin_intrinsic_size(target)
        label = source.relative_to(DIAGRAM_ROOT)
        print(f"  {str(label):<48} {width} x {height}  {'pinned' if changed else 'already pinned'}")

    if failures:
        print("\nfailures:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print(f"\n{len(sources)} diagram(s) rendered")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        # Piping into `head`/`grep -q` closes stdout early; that is not an error.
        raise SystemExit(0)
