import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = ROOT / "plugins" / "tightlip"
SCRIPT = SKILL_DIR / "scripts" / "safeclaw.py"
sys.path.insert(0, str(SKILL_DIR / "scripts"))

_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def rand(seed: str, n: int, alphabet: str = _ALPHABET) -> str:
    """Deterministic pseudo-random string. Test secrets are built at runtime so the repo holds none."""
    out, i = [], 0
    while len(out) < n:
        for b in hashlib.sha256(f"{seed}:{i}".encode()).digest():
            out.append(alphabet[b % len(alphabet)])
        i += 1
    return "".join(out[:n])


class Fake:
    """Fake credentials shaped like the real thing (never valid anywhere)."""
    discord = "MTA5" + rand("discord-a", 20) + "." + rand("discord-b", 6) + "." + rand("discord-c", 38)
    telegram = "7012345678:AA" + rand("telegram", 33)
    openai = "sk-" + "proj-" + rand("openai", 40)
    anthropic = "sk-" + "ant-" + "api03-" + rand("anthropic", 60)
    github = "gh" + "p_" + rand("github", 36)
    gateway = rand("gateway", 40, "0123456789abcdef")
    brave = "BSA" + rand("brave", 28)
    generic = rand("generic", 24) + "9"


@pytest.fixture
def fake():
    return Fake


@pytest.fixture
def home(tmp_path):
    h = tmp_path / "home"
    h.mkdir()
    return h


def env_for(home: Path, extra=None):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("OPENCLAW_", "CLAUDE_CONFIG_DIR"))}
    env.update({"HOME": str(home), "SHELL": "/bin/bash"})
    if extra:
        env.update(extra)
    return env


def run(home: Path, *args, input=None, cwd=None, extra_env=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
                          input=input, cwd=str(cwd or home), env=env_for(home, extra_env))


def assert_no_secrets(text: str, *secrets):
    for s in secrets:
        assert s not in text, "secret value leaked into output"


@pytest.fixture
def openclaw_home(home, fake):
    """A small but realistic ~/.openclaw layout with leaks in every memory tier."""
    state = home / ".openclaw"
    ws = state / "workspace"
    (ws / "memory" / "imports" / "claude-code").mkdir(parents=True)
    (state / "agents" / "main" / "sessions").mkdir(parents=True)
    (state / "agents" / "main" / "agent").mkdir(parents=True)
    (state / "logs").mkdir()
    config = {
        "agents": {"defaults": {"workspace": str(ws)}},
        "gateway": {"mode": "local", "auth": {"token": fake.gateway}},
        "channels": {"discord": {"token": fake.discord}},
    }
    cfg = state / "openclaw.json"
    cfg.write_text(json.dumps(config, indent=2) + "\n")
    os.chmod(cfg, 0o600)
    (ws / "MEMORY.md").write_text(f"# Memory\n- prefers dark mode\n- OpenAI key is {fake.openai}\n")
    (ws / "memory" / "2026-10-20.md").write_text(f"- set up discord bot with {fake.discord}\n")
    (ws / "memory" / "imports" / "claude-code" / "notes.md").write_text("- nothing secret here\n")
    (state / "agents" / "main" / "sessions" / "s1.jsonl").write_text(
        json.dumps({"role": "user", "content": f"here is my github token {fake.github}"}) + "\n")
    (state / "logs" / "config-audit.jsonl").write_text(
        json.dumps({"argv": ["openclaw", "config", "set", "gateway.auth.token", fake.gateway]}) + "\n")
    import sqlite3
    con = sqlite3.connect(state / "agents" / "main" / "agent" / "openclaw-agent.sqlite")
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY, body TEXT)")
    con.execute("INSERT INTO messages (body) VALUES (?)", (f"telegram bot token {fake.telegram} ok",))
    con.commit()
    con.close()
    return state


@pytest.fixture
def claude_home(home, fake):
    cfg = home / ".claude"
    mem = cfg / "projects" / "-work-app" / "memory"
    mem.mkdir(parents=True)
    (cfg / "rules").mkdir()
    (cfg / "CLAUDE.md").write_text("# Personal prefs\n- use pnpm\n")
    (cfg / "rules" / "deploy.md").write_text(f"Deploy with ANTHROPIC_API_KEY={fake.anthropic}\n")
    (mem / "MEMORY.md").write_text("- [reference_api](reference_api.md)\n")
    (mem / "reference_api.md").write_text(f"---\ntype: reference\n---\nstaging token: {fake.github}\n")
    (cfg / "projects" / "-work-app" / "abc.jsonl").write_text(
        json.dumps({"type": "user", "message": {"content": f"use {fake.openai}"}}) + "\n")
    (cfg / "history.jsonl").write_text(json.dumps({"display": "nothing to see"}) + "\n")
    return cfg
