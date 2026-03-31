#!/usr/bin/env python3
"""
safeclaw.py — Token Safety Checker for OpenClaw

Two subcommands:

  scan     Detect plaintext secrets in openclaw.json.
           ONLY returns field paths and lengths — never secret values.
           Example output:
             {
               "findings": [
                 { "path": "channels.discord.token", "env_var": "OPENCLAW_DISCORD_TOKEN", "length": 72 },
                 { "path": "gateway.auth.token",     "env_var": "OPENCLAW_GATEWAY_TOKEN", "length": 48 }
               ],
               "shell": { "name": "zsh", "profile": "~/.zshrc", "source_cmd": "source ~/.zshrc" }
             }
           Secret values are NEVER included in findings output.

  migrate  Migrate plaintext secrets to env vars + SecretRef.
           Accepts findings (field paths + env var names) only — no secret values on CLI.
           Reads actual secret values directly from the config file at migration time,
           keeping them in memory only for the duration of the write. They are never
           passed as CLI arguments, never logged, and never included in any output.

           How we avoid secret exposure:
             1. scan output contains paths/lengths only (safe to show in agent context)
             2. migrate reads values internally from disk — not from CLI args
             3. --dry-run shows the export lines as "export VAR=***" (masked)
             4. No value is printed, logged, or returned at any point

Usage:
  python3 safeclaw.py scan [--config PATH]
  python3 safeclaw.py migrate --findings '[...]' [--config PATH] [--profile PATH] [--dry-run]
  python3 safeclaw.py migrate --restore [--config PATH]

Exit codes:
  scan:    0 = no findings, 1 = findings present, 2 = config not found
  migrate: 0 = success, 1 = error
"""

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

DEFAULT_CONFIG = Path.home() / ".openclaw" / "openclaw.json"

# ── Constants ──────────────────────────────────────────────────────────────────

SENSITIVE_KEYS  = {"token", "apikey", "key", "password", "secret", "credential"}
MIN_SECRET_LEN  = 16

ENV_HINTS = {
    "gateway.auth.token":             "OPENCLAW_GATEWAY_TOKEN",
    "gateway.remote.token":           "OPENCLAW_GATEWAY_TOKEN",
    "channels.discord.token":         "OPENCLAW_DISCORD_TOKEN",
    "channels.telegram.token":        "OPENCLAW_TELEGRAM_TOKEN",
    "channels.whatsapp.token":        "OPENCLAW_WHATSAPP_TOKEN",
    "tools.web.search.gemini.apiKey": "OPENCLAW_GEMINI_API_KEY",
    "tools.web.search.openai.apiKey": "OPENCLAW_OPENAI_API_KEY",
    "tools.web.search.brave.apiKey":  "OPENCLAW_BRAVE_API_KEY",
}

ENV_VAR_RE = re.compile(r'^[A-Z_][A-Z0-9_]*$')

SHELL_PROFILES = {
    "zsh":  ["~/.zshrc", "~/.zprofile"],
    "bash": ["~/.bashrc", "~/.bash_profile", "~/.profile"],
    "fish": ["~/.config/fish/config.fish"],
    "dash": ["~/.profile"],
    "sh":   ["~/.profile"],
}

# ── Helpers ────────────────────────────────────────────────────────────────────

def detect_shell() -> dict:
    shell_name = Path(os.environ.get("SHELL", "bash")).name
    candidates = SHELL_PROFILES.get(shell_name, SHELL_PROFILES["bash"])
    profile = next((p for p in candidates if Path(p).expanduser().exists()), candidates[0])
    return {
        "name":       shell_name,
        "profile":    profile,
        "source_cmd": f"source {profile}",
    }


def to_env_name(path: str) -> str:
    if path in ENV_HINTS:
        return ENV_HINTS[path]
    parts = path.split(".")
    last   = re.sub(r'(?<!^)(?=[A-Z])', '_', parts[-1]).upper()
    prefix = re.sub(r'[^A-Z0-9]', '_', parts[-2].upper()) if len(parts) >= 2 else parts[0].upper()
    return f"OPENCLAW_{prefix}_{last}".replace("__", "_")


def is_secretref(value) -> bool:
    return isinstance(value, dict) and value.get("source") in ("env", "file", "exec")


def scan_config(config: dict, path: str = "", findings: list = None) -> list:
    """
    Recursively scan config for plaintext secrets.
    Returns list of { path, env_var, length } — NO secret values.
    """
    if findings is None:
        findings = []
    if isinstance(config, dict):
        if is_secretref(config):
            return findings
        for k, v in config.items():
            scan_config(v, f"{path}.{k}" if path else k, findings)
    elif isinstance(config, list):
        for i, v in enumerate(config):
            scan_config(v, f"{path}[{i}]", findings)
    elif isinstance(config, str):
        key = path.split(".")[-1].lower().rstrip("[]0123456789")
        if any(s in key for s in SENSITIVE_KEYS) and len(config) >= MIN_SECRET_LEN:
            findings.append({
                "path":    path,
                "env_var": to_env_name(path),
                "length":  len(config),
            })
    return findings


def get_nested(d: dict, dot_path: str):
    """Read a value from a nested dict using dot-path notation."""
    for key in dot_path.split("."):
        if isinstance(d, dict):
            d = d.get(key)
        else:
            return None
    return d


def set_nested(d: dict, dot_path: str, value):
    """Write a value into a nested dict using dot-path notation."""
    keys = dot_path.split(".")
    for k in keys[:-1]:
        d = d.setdefault(k, {})
    d[keys[-1]] = value


def validate_env_var(name: str) -> str:
    """Validate env var name; raise ValueError if it contains unsafe characters."""
    if not ENV_VAR_RE.match(name):
        raise ValueError(
            f"Invalid env var name {name!r} — only A-Z, 0-9 and _ allowed, must start with a letter or _"
        )
    return name


def shell_single_quote(value: str) -> str:
    """
    Wrap value in single quotes for safe shell assignment.
    Single quotes prevent ALL interpolation ($, backtick, etc.).
    The only special case is a literal ' in the value, handled by:
        'before'"'"'after'  →  before'after
    """
    return "'" + value.replace("'", "'\\''") + "'"


def export_line(shell: str, env_var: str, value: str) -> str:
    safe_value = shell_single_quote(value)
    if shell == "fish":
        return f"set -gx {env_var} {safe_value}"
    return f"export {env_var}={safe_value}"

# ── Subcommands ────────────────────────────────────────────────────────────────

def cmd_scan(args):
    config_path = Path(args.config)
    if not config_path.exists():
        print(json.dumps({"error": f"Config not found: {config_path}"}))
        sys.exit(2)

    with open(config_path) as f:
        config = json.load(f)

    findings = scan_config(config)
    shell    = detect_shell()

    # Output: paths + env var names + lengths only. No secret values.
    print(json.dumps({"findings": findings, "shell": shell}, indent=2))
    sys.exit(1 if findings else 0)


def cmd_migrate(args):
    config_path = Path(args.config)
    bak_path    = config_path.with_suffix(".json.bak")

    # ── Restore mode ──────────────────────────────────────────────────────────
    if args.restore:
        if not bak_path.exists():
            print(f"[ERROR] No backup found at {bak_path}", file=sys.stderr)
            sys.exit(1)
        shutil.copy2(bak_path, config_path)
        print(f"[OK] Restored {config_path} from {bak_path}")
        return

    if not args.findings:
        print("[ERROR] --findings required", file=sys.stderr)
        sys.exit(1)

    findings = json.loads(args.findings)

    if not config_path.exists():
        print(f"[ERROR] Config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    # ── Re-read config to get secret values internally (never via CLI args) ───
    with open(config_path) as f:
        config = json.load(f)

    # Verify findings are still plaintext (re-scan confirms nothing changed)
    current_findings = {f["path"]: f for f in scan_config(config)}
    to_migrate = [f for f in findings if f["path"] in current_findings]

    if not to_migrate:
        print("[OK] Nothing to migrate — all findings already resolved.")
        return

    # ── Validate env var names before touching any file ──────────────────────
    for f in to_migrate:
        try:
            validate_env_var(f["env_var"])
        except ValueError as e:
            print(f"[ERROR] {e}", file=sys.stderr)
            sys.exit(1)

    profile_path = Path(args.profile or detect_shell()["profile"]).expanduser()
    shell_name   = Path(os.environ.get("SHELL", "bash")).name

    print(f"\n{'[DRY RUN] ' if args.dry_run else ''}Migration plan:")
    print(f"  config  : {config_path}")
    print(f"  backup  : {bak_path}")
    print(f"  profile : {profile_path}")
    print()

    profile_content = profile_path.read_text() if profile_path.exists() else ""
    lines_to_add = []

    for f in to_migrate:
        env_var = f["env_var"]
        # Export line shown with masked value — never prints the real secret
        masked_line = export_line(shell_name, env_var, "***")
        if env_var not in profile_content:
            lines_to_add.append(f["path"])   # store path; value read below
            print(f"  [profile +] {masked_line}")
        else:
            print(f"  [profile =] {env_var} already present, skipping")
        print(f"  [config  →] {f['path']}  →  SecretRef({env_var})")

    if args.dry_run:
        print("\n[DRY RUN] No files modified.")
        return

    # ── 1. Backup ─────────────────────────────────────────────────────────────
    shutil.copy2(config_path, bak_path)
    print(f"\n[OK] Backup: {bak_path}")

    # ── 2. Write shell profile (values read from config, never from CLI) ──────
    if lines_to_add:
        with open(profile_path, "a") as pf:
            pf.write("\n# Added by token-safety-checker\n")
            for finding in to_migrate:
                if finding["path"] in lines_to_add:
                    # Secret value read directly from disk here — not from CLI
                    value = get_nested(config, finding["path"])
                    if value and isinstance(value, str):
                        pf.write(export_line(shell_name, finding["env_var"], value) + "\n")
        print(f"[OK] Wrote {len(lines_to_add)} export(s) to {profile_path}")

    # ── 3. Update config with SecretRefs ──────────────────────────────────────
    for finding in to_migrate:
        set_nested(config, finding["path"], {
            "source": "env", "provider": "default", "id": finding["env_var"]
        })

    with open(config_path, "w") as f:
        json.dump(config, f, indent=4)
    print(f"[OK] Updated {config_path} with {len(to_migrate)} SecretRef(s)")

    print(f"""
[!] Next steps — source your profile before restarting:

    source {profile_path}
    openclaw gateway restart

    systemd: add vars to EnvironmentFile= in your unit instead of sourcing profile.
    Docker:  pass via -e or environment: in compose.
""")

# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="SafeClaw — token safety checker for OpenClaw",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd")

    # scan
    p_scan = sub.add_parser("scan", help="Detect plaintext secrets (returns paths only, no values)")
    p_scan.add_argument("--config", default=str(DEFAULT_CONFIG))

    # migrate
    p_mig = sub.add_parser("migrate", help="Migrate secrets to env vars + SecretRef")
    p_mig.add_argument("--findings", help="JSON list from scan output")
    p_mig.add_argument("--config",   default=str(DEFAULT_CONFIG))
    p_mig.add_argument("--profile",  default=None, help="Shell profile path (auto-detected if omitted)")
    p_mig.add_argument("--dry-run",  action="store_true")
    p_mig.add_argument("--restore",  action="store_true", help="Restore config from .bak")

    args = parser.parse_args()

    if args.cmd == "scan":
        cmd_scan(args)
    elif args.cmd == "migrate":
        cmd_migrate(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
