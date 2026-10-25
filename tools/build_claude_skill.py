#!/usr/bin/env python3
"""
Build the claude.ai / Skills API upload bundle (tightlip.zip) from this repo's SKILL.md.

claude.ai accepts exactly one SKILL.md per bundle and only these frontmatter keys:
name, description, license, allowed-tools, metadata, compatibility.
The repo SKILL.md already satisfies that; this script only renames the skill to `tightlip`
(the Claude-facing brand) and packs SKILL.md + scripts/ + LICENSE.md under tightlip/.

Usage: python3 tools/build_claude_skill.py [--out dist/tightlip.zip] [--name tightlip]
"""
import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ALLOWED = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}


def check_frontmatter(text: str, name: str):
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        sys.exit("SKILL.md: missing frontmatter")
    keys = {line.split(":", 1)[0] for line in m.group(1).splitlines() if re.match(r"^[A-Za-z-]+:", line)}
    if keys - ALLOWED:
        sys.exit(f"SKILL.md: frontmatter keys not accepted by claude.ai: {sorted(keys - ALLOWED)}")
    desc = re.search(r"^description: (.*)$", m.group(1), re.M).group(1)
    if len(desc) > 1024 or "<" in desc or ">" in desc:
        sys.exit("SKILL.md: description must be <= 1024 chars without angle brackets")
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name) or len(name) > 64:
        sys.exit(f"invalid skill name {name!r}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist" / "tightlip.zip"))
    ap.add_argument("--name", default="tightlip")
    args = ap.parse_args()

    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    skill = re.sub(r"^name: .*$", f"name: {args.name}", skill, count=1, flags=re.M)
    check_frontmatter(skill, args.name)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{args.name}/SKILL.md", skill)
        z.write(ROOT / "scripts" / "safeclaw.py", f"{args.name}/scripts/safeclaw.py")
        z.write(ROOT / "LICENSE.md", f"{args.name}/LICENSE.md")
    print(f"[OK] {out}")


if __name__ == "__main__":
    main()
