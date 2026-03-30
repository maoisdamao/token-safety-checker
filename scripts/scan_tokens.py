#!/usr/bin/env python3
"""
scan_tokens.py — Scan openclaw.json for plaintext secrets.

Usage:
  python3 scan_tokens.py [path/to/openclaw.json]
  python3 scan_tokens.py --detect-shell   # only print shell profile info

Output (default): JSON with keys:
  findings: list of { path, env_var, preview, length }
  shell:    { name, profile, source_cmd }

Exit code 0 = no plaintext found, 1 = plaintext found, 2 = file not found.
"""

import json
import os
import re
import sys
from pathlib import Path

DEFAULT_CONFIG = Path.home() / ".openclaw" / "openclaw.json"

SENSITIVE_KEYS = {"token", "apikey", "key", "password", "secret", "credential"}
MIN_SECRET_LEN = 16

ENV_HINTS = {
    "gateway.auth.token":              "OPENCLAW_GATEWAY_TOKEN",
    "gateway.remote.token":            "OPENCLAW_GATEWAY_TOKEN",
    "channels.discord.token":          "OPENCLAW_DISCORD_TOKEN",
    "channels.telegram.token":         "OPENCLAW_TELEGRAM_TOKEN",
    "channels.whatsapp.token":         "OPENCLAW_WHATSAPP_TOKEN",
    "tools.web.search.gemini.apiKey":  "OPENCLAW_GEMINI_API_KEY",
    "tools.web.search.openai.apiKey":  "OPENCLAW_OPENAI_API_KEY",
    "tools.web.search.brave.apiKey":   "OPENCLAW_BRAVE_API_KEY",
}

# ── Shell detection ────────────────────────────────────────────────────────────

SHELL_PROFILES = {
    "zsh":  ["~/.zshrc", "~/.zprofile"],
    "bash": ["~/.bashrc", "~/.bash_profile", "~/.profile"],
    "fish": ["~/.config/fish/config.fish"],
    "dash": ["~/.profile"],
    "sh":   ["~/.profile"],
}

def detect_shell() -> dict:
    """Return the active shell name, best profile path, and source command."""
    # 1. $SHELL env var (most reliable on macOS/Linux)
    shell_path = os.environ.get("SHELL", "")
    shell_name = Path(shell_path).name if shell_path else ""

    # 2. Fall back: check $0 or parent process name (best-effort)
    if not shell_name:
        shell_name = "bash"  # safest default

    candidates = SHELL_PROFILES.get(shell_name, SHELL_PROFILES["bash"])

    # Pick the first profile file that already exists; else use the first candidate
    profile = next(
        (p for p in candidates if Path(p).expanduser().exists()),
        candidates[0]
    )

    # fish uses a different syntax
    if shell_name == "fish":
        source_cmd = f"source {profile}"
        export_fmt = 'set -gx {{env_var}} "{{value}}"'
    else:
        source_cmd = f"source {profile}"
        export_fmt = 'export {{env_var}}="{{value}}"'

    return {
        "name": shell_name,
        "profile": profile,
        "source_cmd": source_cmd,
        "export_fmt": export_fmt,
    }

# ── Secret scanning ────────────────────────────────────────────────────────────

def to_env_name(path: str) -> str:
    if path in ENV_HINTS:
        return ENV_HINTS[path]
    parts = path.split(".")
    last = parts[-1]
    prefix = parts[-2] if len(parts) >= 2 else parts[0]
    name = re.sub(r'(?<!^)(?=[A-Z])', '_', last).upper()
    prefix_clean = re.sub(r'[^A-Z0-9]', '_', prefix.upper())
    return f"OPENCLAW_{prefix_clean}_{name}".replace("__", "_")

def is_secretref(value) -> bool:
    return isinstance(value, dict) and value.get("source") in ("env", "file", "exec")

def scan(obj, path="", findings=None):
    if findings is None:
        findings = []
    if isinstance(obj, dict):
        if is_secretref(obj):
            return findings  # already a SecretRef, skip
        for k, v in obj.items():
            scan(v, f"{path}.{k}" if path else k, findings)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            scan(v, f"{path}[{i}]", findings)
    elif isinstance(obj, str):
        key = path.split(".")[-1].lower().rstrip("[]0123456789")
        if (
            any(s in key for s in SENSITIVE_KEYS)
            and len(obj) >= MIN_SECRET_LEN
            and not obj.startswith("$")
        ):
            findings.append({
                "path": path,
                "env_var": to_env_name(path),
                "preview": obj[:12] + "...",
                "length": len(obj),
            })
    return findings

# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if "--detect-shell" in sys.argv:
        print(json.dumps(detect_shell(), indent=2))
        sys.exit(0)

    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else DEFAULT_CONFIG
    if not config_path.exists():
        print(json.dumps({"error": f"Not found: {config_path}"}))
        sys.exit(2)

    with open(config_path) as f:
        config = json.load(f)

    findings = scan(config)
    shell = detect_shell()

    print(json.dumps({"findings": findings, "shell": shell}, indent=2))
    sys.exit(1 if findings else 0)

if __name__ == "__main__":
    main()
