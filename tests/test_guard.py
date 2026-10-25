import json
import os
import subprocess

from conftest import Fake, assert_no_secrets, run


def hook(home, tool, tool_input, scope="memory"):
    payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": tool_input})
    return run(home, "guard-hook", "--scope", scope, input=payload)


def denied(r):
    return r.stdout.strip() and json.loads(r.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_hook_blocks_secret_in_memory_write(home):
    r = hook(home, "Write", {"file_path": "/h/.claude/projects/-p/memory/ref.md", "content": f"key {Fake.openai}"})
    assert r.returncode == 0 and denied(r)
    reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
    assert "openai-api-key" in reason
    assert_no_secrets(r.stdout + r.stderr, Fake.openai)


def test_hook_blocks_edit_and_multiedit(home):
    assert denied(hook(home, "Edit", {"file_path": "/r/CLAUDE.md", "old_string": "a", "new_string": Fake.github}))
    assert denied(hook(home, "MultiEdit", {"file_path": "/r/AGENTS.md",
                                           "edits": [{"old_string": "a", "new_string": Fake.discord}]}))


def test_hook_allows_clean_or_non_memory(home):
    assert hook(home, "Write", {"file_path": "/r/CLAUDE.md", "content": "use ${OPENAI_API_KEY}"}).stdout == ""
    assert hook(home, "Write", {"file_path": "/r/src/app.py", "content": Fake.openai}).stdout == ""
    assert hook(home, "Bash", {"command": f"echo {Fake.openai}"}).stdout == ""


def test_hook_scope_all(home):
    assert denied(hook(home, "Write", {"file_path": "/r/src/app.py", "content": Fake.openai}, scope="all"))


def test_hook_fails_open(home):
    r = run(home, "guard-hook", input="not json")
    assert r.returncode == 0 and r.stdout == ""


def test_install_guard_claude_idempotent_and_preserving(home):
    cfg = home / ".claude"
    cfg.mkdir()
    existing = {"model": "opus", "hooks": {"PreToolUse": [
        {"matcher": "Bash", "hooks": [{"type": "command", "command": "echo other"}]}]}}
    (cfg / "settings.json").write_text(json.dumps(existing))
    for _ in range(2):
        r = run(home, "install-guard", "--platform", "claude")
        assert r.returncode == 0, r.stderr
    s = json.loads((cfg / "settings.json").read_text())
    assert s["model"] == "opus"
    cmds = [h["command"] for e in s["hooks"]["PreToolUse"] for h in e["hooks"]]
    assert "echo other" in cmds
    guard_cmds = [c for c in cmds if "token-safety-guard" in c]
    assert len(guard_cmds) == 1

    # The installed command really works as a hook (runs the copied script, not the repo one)
    payload = json.dumps({"tool_name": "Write",
                          "tool_input": {"file_path": "/r/CLAUDE.md", "content": Fake.anthropic}})
    out = subprocess.run(guard_cmds[0], shell=True, input=payload, capture_output=True, text=True)
    assert json.loads(out.stdout)["hookSpecificOutput"]["permissionDecision"] == "deny"

    r = run(home, "uninstall-guard", "--platform", "claude")
    s = json.loads((cfg / "settings.json").read_text())
    assert [h["command"] for e in s["hooks"]["PreToolUse"] for h in e["hooks"]] == ["echo other"]
    assert not (cfg / "hooks" / "token-safety-guard.py").exists()


def _git(ws, *args, check=True):
    return subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=ws,
                          capture_output=True, text=True, check=check)


def test_install_guard_openclaw_blocks_commit(home, openclaw_home):
    ws = openclaw_home / "workspace"
    _git(ws, "init", "-q")
    r = run(home, "install-guard", "--platform", "openclaw")
    assert r.returncode == 0 and "OpenClaw guard installed" in r.stdout, r.stdout + r.stderr
    (ws / "notes.md").write_text("clean\n")
    _git(ws, "add", "notes.md")
    assert _git(ws, "commit", "-qm", "ok", check=False).returncode == 0
    _git(ws, "add", "MEMORY.md")
    res = _git(ws, "commit", "-qm", "leak", check=False)
    assert res.returncode != 0 and "commit blocked" in res.stderr
    assert_no_secrets(res.stdout + res.stderr, Fake.openai)
    run(home, "uninstall-guard", "--platform", "openclaw")
    assert not (ws / ".git" / "hooks" / "pre-commit").exists()


def test_install_guard_openclaw_respects_foreign_hook(home, openclaw_home):
    ws = openclaw_home / "workspace"
    _git(ws, "init", "-q")
    hook_path = ws / ".git" / "hooks" / "pre-commit"
    hook_path.write_text("#!/bin/sh\necho mine\n")
    r = run(home, "install-guard", "--platform", "openclaw")
    assert "[SKIP]" in r.stdout
    assert hook_path.read_text() == "#!/bin/sh\necho mine\n"
