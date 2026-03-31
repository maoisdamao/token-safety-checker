#!/usr/bin/env python3
"""
migrate_tokens.py — Migrate plaintext secrets in openclaw.json to env vars.

Performs three writes atomically:
  1. Backup openclaw.json → openclaw.json.bak
  2. Append env var exports to shell profile (skips duplicates)
  3. Replace plaintext values in openclaw.json with SecretRef

Usage:
  python3 migrate_tokens.py --findings '[{"path":"...","env_var":"..."}]' [--values '{"path":"value"}']
  python3 migrate_tokens.py --dry-run --findings '[...]'
  python3 migrate_tokens.py --restore   # restore from .bak

Options:
  --findings JSON   List of findings from scan_tokens.py (required)
  --values JSON     Map of path→plaintext value (required unless --dry-run)
  --config PATH     Path to openclaw.json (default: ~/.openclaw/openclaw.json)
  --profile PATH    Shell profile to write (default: auto-detected)
  --dry-run         Print what would be written without making changes
  --restore         Restore openclaw.json from .bak file
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

DEFAULT_CONFIG = Path.home() / ".openclaw" / "openclaw.json"


def detect_profile() -> Path:
    shell = Path(os.environ.get("SHELL", "")).name
    candidates = {
        "zsh":  ["~/.zshrc", "~/.zprofile"],
        "bash": ["~/.bashrc", "~/.bash_profile", "~/.profile"],
        "fish": ["~/.config/fish/config.fish"],
    }.get(shell, ["~/.profile"])
    for c in candidates:
        p = Path(c).expanduser()
        if p.exists():
            return p
    return Path(candidates[0]).expanduser()


def set_nested(d: dict, dot_path: str, value):
    keys = dot_path.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def export_line(shell: str, env_var: str, value: str) -> str:
    if shell == "fish":
        return f'set -gx {env_var} "{value}"'
    return f'export {env_var}="{value}"'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--findings", required=False, help="JSON list of findings")
    parser.add_argument("--values",   required=False, help="JSON map path→value")
    parser.add_argument("--config",   default=str(DEFAULT_CONFIG))
    parser.add_argument("--profile",  default=None)
    parser.add_argument("--dry-run",  action="store_true")
    parser.add_argument("--restore",  action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    bak_path = config_path.with_suffix(".json.bak")

    # ── Restore mode ──────────────────────────────────────────────────────────
    if args.restore:
        if not bak_path.exists():
            print(f"[ERROR] No backup found at {bak_path}", file=sys.stderr)
            sys.exit(1)
        shutil.copy2(bak_path, config_path)
        print(f"[OK] Restored {config_path} from {bak_path}")
        sys.exit(0)

    if not args.findings:
        parser.print_help()
        sys.exit(1)

    findings = json.loads(args.findings)
    values   = json.loads(args.values) if args.values else {}

    if not args.dry_run and not values:
        print("[ERROR] --values required unless --dry-run", file=sys.stderr)
        sys.exit(1)

    profile_path = Path(args.profile).expanduser() if args.profile else detect_profile()
    shell_name   = Path(os.environ.get("SHELL", "bash")).name

    # ── Preview ───────────────────────────────────────────────────────────────
    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Migration plan:")
    print(f"  config  : {config_path}")
    print(f"  backup  : {bak_path}")
    print(f"  profile : {profile_path}")
    print(f"  shell   : {shell_name}")
    print()

    profile_content = profile_path.read_text() if profile_path.exists() else ""
    lines_to_add = []
    for f in findings:
        env_var = f["env_var"]
        path    = f["path"]
        val     = values.get(path, "<value>")
        line    = export_line(shell_name, env_var, val)
        if env_var not in profile_content:
            lines_to_add.append(line)
            print(f"  [profile +] {export_line(shell_name, env_var, '***')}")
        else:
            print(f"  [profile =] {env_var} already present, skipping")
        print(f"  [config  →] {path}  →  SecretRef({env_var})")

    if args.dry_run:
        print("\n[DRY RUN] No files were modified.")
        sys.exit(0)

    # ── 1. Backup config ──────────────────────────────────────────────────────
    shutil.copy2(config_path, bak_path)
    print(f"\n[OK] Backup: {bak_path}")

    # ── 2. Write shell profile ────────────────────────────────────────────────
    if lines_to_add:
        with open(profile_path, "a") as f:
            f.write("\n# Added by token-safety-checker\n")
            for line in lines_to_add:
                f.write(line + "\n")
        print(f"[OK] Wrote {len(lines_to_add)} export(s) to {profile_path}")

    # ── 3. Update openclaw.json ───────────────────────────────────────────────
    with open(config_path) as f:
        config = json.load(f)

    for finding in findings:
        set_nested(config, finding["path"], {
            "source": "env",
            "provider": "default",
            "id": finding["env_var"],
        })

    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    print(f"[OK] Updated {config_path} with {len(findings)} SecretRef(s)")

    # ── 4. Warn about service managers ───────────────────────────────────────
    print("""
[!] IMPORTANT — source your profile before restarting the gateway:

    source """ + str(profile_path) + """
    openclaw gateway restart

    If the gateway is managed by systemd or runs in a container,
    sourcing the shell profile will NOT inject env vars into the service.
    In that case, add the vars to your systemd unit's EnvironmentFile=
    or your container's env config instead.
""")


if __name__ == "__main__":
    main()
