import json
import os
import stat
import subprocess
import time

from conftest import Fake, assert_no_secrets, rand, run

ALL = [Fake.discord, Fake.telegram, Fake.openai, Fake.anthropic, Fake.github, Fake.gateway]


def mode(p):
    return stat.S_IMODE(p.stat().st_mode)


def write_cfg(home, data, perm=0o600, raw=None):
    state = home / ".openclaw"
    state.mkdir(exist_ok=True)
    cfg = state / "openclaw.json"
    cfg.write_text(raw if raw is not None else json.dumps(data, indent=2) + "\n")
    os.chmod(cfg, perm)
    return cfg


# ── scan ──────────────────────────────────────────────────────────────────────

def test_scan_config_only(home, openclaw_home):
    r = run(home, "scan")
    assert r.returncode == 1
    out = json.loads(r.stdout)
    assert {f["path"] for f in out["findings"]} == {"gateway.auth.token", "channels.discord.token"}
    assert out["checks"]["file_permissions"]["ok"] is True
    assert "memory" not in out
    assert_no_secrets(r.stdout + r.stderr, *ALL)


def test_scan_missing_config_exit_2(home):
    assert run(home, "scan").returncode == 2


def test_scan_json5_and_permissions(home):
    write_cfg(home, None, perm=0o644,
              raw="{\n  // comment\n  channels: { discord: { token: '%s', }, },\n}\n" % Fake.discord)
    r = run(home, "scan")
    out = json.loads(r.stdout)
    assert r.returncode == 1
    assert out["findings"][0]["path"] == "channels.discord.token"
    assert out["checks"]["format"]["strict_json"] is False
    assert out["checks"]["file_permissions"]["ok"] is False
    assert_no_secrets(r.stdout + r.stderr, Fake.discord)


def test_scan_clean_exit_0(home):
    write_cfg(home, {"channels": {"discord": {"token": {"source": "env", "provider": "default", "id": "X"}}}})
    assert run(home, "scan").returncode == 0


# ── memory ────────────────────────────────────────────────────────────────────

def _secrets_by_detector(out):
    return {s["detector"]: s for s in out["memory"]["secrets"]}


def test_memory_openclaw_all_tiers(home, openclaw_home):
    r = run(home, "memory", "--platform", "openclaw")
    assert r.returncode == 1
    out = json.loads(r.stdout)
    found = _secrets_by_detector(out)
    assert set(found) >= {"discord-bot-token", "openai-api-key", "github-token", "telegram-bot-token", "live-secret"}
    assert found["discord-bot-token"]["live_match"] == "channels.discord.token"
    assert found["discord-bot-token"]["risk"] == "HIGH"
    assert found["live-secret"]["live_match"] == "gateway.auth.token"  # audit log argv leak
    assert "log" in found["live-secret"]["scopes"]
    assert found["openai-api-key"]["scopes"] == ["long_term"]
    assert found["github-token"]["scopes"] == ["transcript"]
    assert found["telegram-bot-token"]["locations"][0]["line"].startswith("messages:rowid=")
    assert out["memory"]["advice"]
    assert_no_secrets(r.stdout + r.stderr, *ALL)


def test_memory_no_transcripts(home, openclaw_home):
    out = json.loads(run(home, "memory", "--platform", "openclaw", "--no-transcripts").stdout)
    scopes = {s for x in out["memory"]["secrets"] for s in x["scopes"]}
    assert scopes <= {"long_term", "short_term"}


def test_memory_claude(home, claude_home, tmp_path):
    project = tmp_path / "proj"
    (project / ".claude" / "rules").mkdir(parents=True)
    (project / "CLAUDE.local.md").write_text(f"sandbox jwt eyJ{rand('h', 20)}.eyJ{rand('p', 30)}.{rand('s', 30)}\n")
    r = run(home, "memory", "--platform", "claude", "--project", str(project))
    assert r.returncode == 1
    found = _secrets_by_detector(json.loads(r.stdout))
    assert found["anthropic-api-key"]["locations"][0]["file"] == "~/.claude/rules/deploy.md"
    assert found["github-token"]["scopes"] == ["long_term"]          # auto memory topic file
    assert found["openai-api-key"]["scopes"] == ["transcript"]
    assert found["jwt"]["locations"][0]["file"].endswith("CLAUDE.local.md")
    assert_no_secrets(r.stdout + r.stderr, *ALL)


def test_memory_env_secretref_live_match(home, claude_home):
    write_cfg(home, {"tools": {"openai": {"apiKey": {"source": "env", "provider": "default", "id": "OAI"}}}})
    r = run(home, "memory", "--platform", "claude", extra_env={"OAI": Fake.openai})
    found = _secrets_by_detector(json.loads(r.stdout))
    assert found["openai-api-key"]["live_match"] == "$OAI"


def test_memory_clean(home):
    (home / ".claude" / "projects" / "-p" / "memory").mkdir(parents=True)
    (home / ".claude" / "projects" / "-p" / "memory" / "MEMORY.md").write_text("- likes tabs\n")
    r = run(home, "memory", "--platform", "claude")
    assert r.returncode == 0
    assert json.loads(r.stdout)["memory"]["secrets"] == []


def test_scan_memory_without_config(home, claude_home):
    r = run(home, "scan", "--memory", "--platform", "claude")
    out = json.loads(r.stdout)
    assert r.returncode == 1 and out["config"]["found"] is False and out["memory"]["secrets"]


# ── migrate ───────────────────────────────────────────────────────────────────

def scan_findings(home):
    return json.dumps(json.loads(run(home, "scan").stdout)["findings"])


def test_migrate_end_to_end(home):
    cfg = write_cfg(home, {"gateway": {"auth": {"token": Fake.gateway}},
                           "providers": [{"name": "x", "apiKey": Fake.openai}]})
    (home / ".bashrc").write_text("export FOO_TOKEN_2='x'\n")
    os.chmod(home / ".bashrc", 0o644)
    findings = scan_findings(home)

    dry = run(home, "migrate", "--findings", findings, "--dry-run")
    assert dry.returncode == 0 and "[DRY RUN] No files modified." in dry.stdout
    assert_no_secrets(dry.stdout + dry.stderr, Fake.gateway, Fake.openai)

    r = run(home, "migrate", "--findings", findings, "--secure-profile")
    assert r.returncode == 0, r.stderr
    assert_no_secrets(r.stdout + r.stderr, Fake.gateway, Fake.openai)
    data = json.loads(cfg.read_text())
    assert data["providers"][0]["apiKey"]["source"] == "env"       # list path migrated correctly
    assert "providers[0]" not in data
    assert data["gateway"]["auth"]["token"]["id"] == "OPENCLAW_GATEWAY_TOKEN"
    assert cfg.read_text().startswith("{\n  \"")                    # indentation preserved (2)
    assert mode(cfg) == 0o600
    profile = (home / ".bashrc").read_text()
    assert f"export OPENCLAW_GATEWAY_TOKEN='{Fake.gateway}'" in profile
    assert mode(home / ".bashrc") == 0o600
    backups = list((home / ".openclaw").glob("openclaw.json.bak-*"))
    assert len(backups) == 1 and mode(backups[0]) == 0o600


def test_migrate_profile_conflict_and_exact_match(home):
    write_cfg(home, {"gateway": {"auth": {"token": Fake.gateway}}})
    (home / ".bashrc").write_text("export OPENCLAW_GATEWAY_TOKEN_OLD='x'\nexport OPENCLAW_GATEWAY_TOKEN='stale'\n")
    r = run(home, "migrate", "--findings", scan_findings(home))
    assert r.returncode == 1 and "DIFFERENT value" in r.stderr
    assert_no_secrets(r.stderr, Fake.gateway)


def test_migrate_same_value_already_in_profile_is_skipped(home):
    write_cfg(home, {"gateway": {"auth": {"token": Fake.gateway}}})
    (home / ".bashrc").write_text(f"export OPENCLAW_GATEWAY_TOKEN='{Fake.gateway}'\n")
    r = run(home, "migrate", "--findings", scan_findings(home))
    assert r.returncode == 0 and "already present with the same value" in r.stdout
    assert (home / ".bashrc").read_text().count("OPENCLAW_GATEWAY_TOKEN") == 1


def test_migrate_distinct_values_sharing_hint(home):
    cfg = write_cfg(home, {"gateway": {"auth": {"token": Fake.gateway}, "remote": {"token": rand("r", 40)}}})
    r = run(home, "migrate", "--findings", scan_findings(home))
    assert r.returncode == 0, r.stderr
    data = json.loads(cfg.read_text())
    assert data["gateway"]["auth"]["token"]["id"] != data["gateway"]["remote"]["token"]["id"]


def test_migrate_rejects_user_forced_collision(home):
    write_cfg(home, {"gateway": {"auth": {"token": Fake.gateway}, "remote": {"token": rand("r", 40)}}})
    f = json.loads(scan_findings(home))
    for x in f:
        x["env_var"] = "SAME"
    r = run(home, "migrate", "--findings", json.dumps(f))
    assert r.returncode == 1 and "different secrets" in r.stderr


def test_migrate_refuses_json5(home):
    write_cfg(home, None, raw="{ // c\n channels: { discord: { token: '%s' } } }\n" % Fake.discord)
    r = run(home, "migrate", "--findings", scan_findings(home))
    assert r.returncode == 1 and "JSON5" in r.stderr


def test_backups_never_overwritten_and_restore_newest(home):
    cfg = write_cfg(home, {"a": {"token": Fake.gateway}})
    original = cfg.read_text()
    assert run(home, "migrate", "--findings", scan_findings(home)).returncode == 0
    time.sleep(1.1)
    data = json.loads(cfg.read_text())
    data["b"] = {"token": Fake.discord}
    cfg.write_text(json.dumps(data, indent=2))
    assert run(home, "migrate", "--findings", scan_findings(home)).returncode == 0
    backups = sorted((home / ".openclaw").glob("openclaw.json.bak-*"))
    assert len(backups) == 2
    assert backups[0].read_text() == original                       # first backup kept intact
    listing = run(home, "migrate", "--list-backups")
    assert listing.stdout.count("openclaw.json.bak-") == 2
    assert run(home, "migrate", "--restore").returncode == 0
    assert "b" in json.loads(cfg.read_text())                        # newest backup restored
    assert run(home, "migrate", "--restore", "--backup", str(backups[0])).returncode == 0
    assert cfg.read_text() == original


def test_restore_ignores_openclaw_rotating_backups(home):
    cfg = write_cfg(home, {"a": {"token": Fake.gateway}})
    original = cfg.read_text()
    assert run(home, "migrate", "--findings", scan_findings(home)).returncode == 0
    # OpenClaw writes its own .bak / .bak.1 later (newer mtime) — restore must still pick ours
    (home / ".openclaw" / "openclaw.json.bak").write_text('{"openclaw": "own-backup"}')
    assert run(home, "migrate", "--restore").returncode == 0
    assert cfg.read_text() == original


def test_verify_flags_and_cleans_leaky_openclaw_backups(home):
    write_cfg(home, {"a": {"token": {"source": "env", "provider": "default", "id": "V"}}})
    state = home / ".openclaw"
    (state / "openclaw.json.bak").write_text(json.dumps({"a": {"token": Fake.gateway}}))
    (state / "openclaw.json.bak.2").write_text('{"clean": true}')
    r = run(home, "verify", extra_env={"V": "x"})
    assert r.returncode == 1 and "created by OpenClaw itself: openclaw.json.bak" in r.stdout
    assert_no_secrets(r.stdout, Fake.gateway)
    r = run(home, "verify", "--clean-backup", extra_env={"V": "x"})
    assert r.returncode == 0, r.stdout
    assert not (state / "openclaw.json.bak").exists()
    assert (state / "openclaw.json.bak.2").exists()          # no plaintext → left alone


def test_legacy_v2_backup_is_restorable(home):
    cfg = write_cfg(home, {"x": 1})
    (home / ".openclaw" / "openclaw.json.bak").write_text('{"legacy": true}')
    assert run(home, "migrate", "--restore").returncode == 0
    assert json.loads(cfg.read_text()) == {"legacy": True}


# ── verify ────────────────────────────────────────────────────────────────────

def test_verify(home, tmp_path):
    secret_file = tmp_path / "secret.txt"
    secret_file.write_text("x")
    os.chmod(secret_file, 0o644)
    cfg = write_cfg(home, {
        "a": {"token": {"source": "env", "provider": "default", "id": "SET_VAR"}},
        "b": {"token": {"source": "env", "provider": "default", "id": "UNSET_VAR"}},
        "c": {"token": {"source": "file", "provider": "default", "id": str(secret_file)}},
    })
    (home / ".openclaw" / "openclaw.json.bak-20260101-000000").write_text(json.dumps({"a": {"token": Fake.gateway}}))
    r = run(home, "verify", extra_env={"SET_VAR": "v"})
    assert r.returncode == 1
    assert "$UNSET_VAR" in r.stdout and "$SET_VAR" not in r.stdout
    assert "readable by others" in r.stdout
    assert "backup file(s)" in r.stdout
    os.chmod(secret_file, 0o600)
    cfg_data = json.loads(cfg.read_text())
    del cfg_data["b"]
    cfg.write_text(json.dumps(cfg_data))
    r = run(home, "verify", "--clean-backup", extra_env={"SET_VAR": "v"})
    assert r.returncode == 0, r.stdout
    assert not list((home / ".openclaw").glob("openclaw.json.bak*"))


# ── git history ───────────────────────────────────────────────────────────────

def test_deep_scan_git_history(home):
    cfg = write_cfg(home, {"channels": {"discord": {"token": Fake.discord}}})
    git = ["git", "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(["git", "init", "-q"], cwd=cfg.parent, check=True)
    subprocess.run(git + ["add", "."], cwd=cfg.parent, check=True)
    subprocess.run(git + ["commit", "-qm", "c"], cwd=cfg.parent, check=True)
    r = run(home, "scan", "--deep")
    hist = json.loads(r.stdout)["git_history"]
    assert hist["supported"] and len(hist["exposed_commits"]) == 1
    assert_no_secrets(r.stdout + r.stderr, Fake.discord)
