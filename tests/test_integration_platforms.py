"""
Integration tests against the real OpenClaw and Claude Code CLIs.
Skipped automatically when the CLI is not on PATH (CI installs both).
"""
import json
import os
import shutil
import subprocess

import pytest

from conftest import ROOT, Fake, assert_no_secrets, env_for, run

needs_openclaw = pytest.mark.skipif(not shutil.which("openclaw"), reason="openclaw CLI not installed")
needs_claude = pytest.mark.skipif(not shutil.which("claude"), reason="claude CLI not installed")


def sh(cmd, home, extra_env=None, check=True, timeout=300):
    r = subprocess.run(cmd, cwd=home, env=env_for(home, extra_env), capture_output=True, text=True,
                       timeout=timeout)
    if check and r.returncode != 0:
        raise AssertionError(f"{cmd} failed: {r.stdout}\n{r.stderr}")
    return r


def package_skill(dest):
    """Copy the skill the way the ClawHub publish job does (no .git/.github/tests/tools/docs)."""
    ignore = shutil.ignore_patterns(".git", ".github", "tests", "tools", "docs", ".claude-plugin",
                                    "__pycache__", ".pytest_cache", "dist")
    shutil.copytree(ROOT, dest, ignore=ignore)
    return dest


def openclaw_init(home):
    """`openclaw setup` (≤ 2026.6) or non-interactive onboarding (2026.10+, which requires a TTY for setup)."""
    r = subprocess.run(["openclaw", "setup"], cwd=home, env=env_for(home), capture_output=True, text=True,
                       stdin=subprocess.DEVNULL, timeout=300)
    if r.returncode == 0 and (home / ".openclaw" / "openclaw.json").exists():
        return
    sh(["openclaw", "onboard", "--non-interactive", "--accept-risk", "--mode", "local", "--auth-choice", "skip",
        "--skip-channels", "--skip-daemon", "--skip-health", "--skip-search", "--skip-skills", "--skip-ui"], home)


@needs_openclaw
def test_openclaw_end_to_end(home, tmp_path):
    (home / ".bashrc").write_text("")
    openclaw_init(home)

    # Skill loads and its python3 requirement is recognised
    pkg = package_skill(tmp_path / "token-safety-checker")
    sh(["openclaw", "skills", "install", str(pkg)], home)
    info = sh(["openclaw", "skills", "info", "token-safety-checker"], home).stdout
    assert "Ready" in info and "python3" in info

    # Real user flow: secrets set through the OpenClaw CLI
    sh(["openclaw", "config", "set", "channels.discord.token", Fake.discord], home)
    sh(["openclaw", "config", "set", "gateway.auth.token", Fake.gateway], home)
    ws = home / ".openclaw" / "workspace"
    (ws / "MEMORY.md").write_text(f"- openai key {Fake.openai}\n")

    scan = run(home, "scan", "--memory", "--platform", "openclaw")
    assert scan.returncode == 1
    out = json.loads(scan.stdout)
    assert {f["path"] for f in out["findings"]} >= {"channels.discord.token", "gateway.auth.token"}
    assert any(s["detector"] == "openai-api-key" for s in out["memory"]["secrets"])
    assert_no_secrets(scan.stdout + scan.stderr, Fake.discord, Fake.gateway, Fake.openai)

    mig = run(home, "migrate", "--findings", json.dumps(out["findings"]), "--secure-profile")
    assert mig.returncode == 0, mig.stderr
    assert_no_secrets(mig.stdout + mig.stderr, Fake.discord, Fake.gateway)

    env = {"OPENCLAW_DISCORD_TOKEN": Fake.discord, "OPENCLAW_GATEWAY_TOKEN": Fake.gateway}
    valid = json.loads(sh(["openclaw", "config", "validate", "--json"], home, env).stdout.strip().splitlines()[-1])
    assert valid["valid"] is True
    audit = sh(["openclaw", "secrets", "audit", "--json"], home, env, check=False)
    assert json.loads(audit.stdout)["summary"]["plaintextCount"] == 0
    assert run(home, "verify", "--clean-backup", extra_env=env).returncode == 0


@needs_claude
def test_claude_plugin_validates_and_installs(home, tmp_path):
    r = subprocess.run(["claude", "plugin", "validate", "--strict", str(ROOT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr

    cfg = tmp_path / "claude-config"
    cfg.mkdir()
    env = {"CLAUDE_CONFIG_DIR": str(cfg)}
    sh(["claude", "plugin", "marketplace", "add", str(ROOT)], home, env)
    sh(["claude", "plugin", "install", "tightlip@maoisdamao"], home, env)
    details = sh(["claude", "plugin", "details", "tightlip"], home, env).stdout
    assert "token-safety-checker" in details


def test_claude_ai_bundle(tmp_path):
    """The claude.ai upload bundle has exactly one SKILL.md with only upload-safe frontmatter keys."""
    import zipfile
    out = tmp_path / "tightlip.zip"
    subprocess.run(["python3", str(ROOT / "tools" / "build_claude_skill.py"), "--out", str(out)], check=True)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert "tightlip/SKILL.md" in names and "tightlip/scripts/safeclaw.py" in names
        assert sum(n.endswith("SKILL.md") for n in names) == 1
        assert not any("tests/" in n or ".github" in n for n in names)
        skill = z.read("tightlip/SKILL.md").decode()
    assert skill.startswith("---\nname: tightlip\n")
