import json

import pytest

import safeclaw as sc
from conftest import Fake, rand


@pytest.mark.parametrize("name,value", [
    ("discord-bot-token", Fake.discord),
    ("telegram-bot-token", Fake.telegram),
    ("openai-api-key", Fake.openai),
    ("anthropic-api-key", Fake.anthropic),
    ("github-token", Fake.github),
    ("aws-access-key-id", "AKIA" + rand("aws", 16, "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")),
    ("google-api-key", "AIza" + rand("google", 35)),
    ("jwt", "eyJ" + rand("h", 20) + ".eyJ" + rand("p", 30) + "." + rand("s", 30)),
    ("private-key", "-----BEGIN OPENSSH " + "PRIVATE KEY-----"),
], ids=lambda x: x if x in {n for n, *_ in sc.DETECTORS} else "")
def test_provider_detectors(name, value):
    hits = sc.detect_secrets(f"note: {value} end")
    assert [h["detector"] for h in hits] == [name]


def test_anthropic_is_not_reported_as_openai():
    hits = sc.detect_secrets(Fake.anthropic)
    assert len(hits) == 1 and hits[0]["detector"] == "anthropic-api-key"


def test_contextual_detectors():
    assert sc.detect_secrets("Authorization: Bearer " + rand("bearer", 32))[0]["detector"] == "bearer-token"
    assert sc.detect_secrets("postgres://app:" + rand("pw", 12) + "@db:5432/x")[0]["detector"] == "url-credentials"
    assert sc.detect_secrets("api_key = " + Fake.generic)[0]["detector"] == "generic-secret"


@pytest.mark.parametrize("text", [
    "OPENAI_API_KEY=${OPENAI_API_KEY}",
    "api_key: your-api-key-goes-here-xxxx",
    "password = changeme_changeme_changeme",
    "token: aaaaaaaaaaaaaaaaaaaaaaaa",
    "Authorization: Bearer <YOUR_TOKEN_HERE_PLEASE>",
    "secret: thisisjustalongwordwithoutdigits",
    "the tokenizer splits text into tokens",
])
def test_placeholders_and_prose_are_ignored(text):
    assert sc.detect_secrets(text) == []


def test_live_secret_match_keeps_provider_hint():
    hits = sc.detect_secrets(f"x {Fake.discord} y", known={Fake.discord: "channels.discord.token"})
    assert len(hits) == 1
    assert hits[0]["live_match"] == "channels.discord.token"
    assert hits[0]["detector_hint"] == "discord-bot-token"


def test_live_secret_without_pattern_is_found():
    hits = sc.detect_secrets(f"argv {Fake.gateway}", known={Fake.gateway: "gateway.auth.token"})
    assert hits[0]["detector"] == "live-secret" and hits[0]["live_match"] == "gateway.auth.token"


def test_json5_to_json():
    src = """// top comment
{
  gateway: { auth: { token: 'abc"def', }, },  /* trailing */
  url: "https://example.com/a//b",
  list: [1, 2, 3,],
  flag: true,
}
"""
    data = json.loads(sc.json5_to_json(src))
    assert data == {"gateway": {"auth": {"token": 'abc"def'}}, "url": "https://example.com/a//b",
                    "list": [1, 2, 3], "flag": True}


def test_nested_paths_with_lists():
    cfg = {"providers": [{"name": "a"}, {"name": "b", "apiKey": "x"}]}
    assert sc.get_nested(cfg, "providers[1].apiKey") == "x"
    sc.set_nested(cfg, "providers[1].apiKey", {"source": "env"})
    assert cfg["providers"][1]["apiKey"] == {"source": "env"}
    assert sc.get_nested(cfg, "providers[5].apiKey") is None


def test_scan_config_key_value_and_skips():
    cfg = {
        "providers": [{"apiKey": Fake.openai}],
        "mcp": {"headers": {"X-Custom": Fake.github}},            # non-sensitive key, provider value
        "web": {"Authorization": "Bearer " + rand("auth", 30)},   # new sensitive key
        "env": {"token": "${OPENCLAW_TOKEN}"},                   # env template
        "ref": {"token": {"source": "env", "provider": "default", "id": "X"}},
        "short": {"token": "abc"},
    }
    paths = {f["path"]: f for f in sc.scan_config(cfg)}
    assert set(paths) == {"providers[0].apiKey", "mcp.headers.X-Custom", "web.Authorization"}
    assert paths["mcp.headers.X-Custom"]["detector"] == "github-token"
    assert paths["mcp.headers.X-Custom"]["risk"] == "MEDIUM"
    for f in paths.values():
        assert sc.ENV_VAR_RE.match(f["env_var"])
        assert "value" not in f


def test_current_openclaw_channel_keys():
    cfg = {"channels": {
        "telegram": {"botToken": Fake.telegram, "tokenFile": "/run/secrets/telegram-bot-token"},
        "slack": {"botToken": "xox" + "b-" + rand("slack", 40), "signingSecret": rand("sign", 32)},
        "discord": {"accounts": {"work": {"token": Fake.discord}}},
    }}
    found = {f["path"]: f for f in sc.scan_config(cfg)}
    assert set(found) == {"channels.telegram.botToken", "channels.slack.botToken",
                          "channels.slack.signingSecret", "channels.discord.accounts.work.token"}
    assert all(f["risk"] == "HIGH" for f in found.values())
    assert found["channels.telegram.botToken"]["env_var"] == "OPENCLAW_TELEGRAM_TOKEN"
    assert found["channels.slack.signingSecret"]["env_var"] == "OPENCLAW_SLACK_SIGNING_SECRET"


def test_assign_env_names_collision():
    cfg = {"gateway": {"auth": {"token": Fake.gateway}, "remote": {"token": rand("other", 40)}}}
    f = sc.assign_env_names(sc.scan_config(cfg), cfg)
    names = {x["path"]: x["env_var"] for x in f}
    assert names["gateway.auth.token"] == "OPENCLAW_GATEWAY_TOKEN"
    assert names["gateway.remote.token"] != "OPENCLAW_GATEWAY_TOKEN"


def test_assign_env_names_same_value_shares():
    cfg = {"gateway": {"auth": {"token": Fake.gateway}, "remote": {"token": Fake.gateway}}}
    f = sc.assign_env_names(sc.scan_config(cfg), cfg)
    assert {x["env_var"] for x in f} == {"OPENCLAW_GATEWAY_TOKEN"}


def test_profile_exports_exact_names():
    text = "export FOO_TOKEN_2='a'\nexport FOO_TOKEN='b'\\''c'\nset -gx BAR 'z'\n# export NOPE=1\n"
    assert sc.profile_exports(text) == {"FOO_TOKEN_2": "a", "FOO_TOKEN": "b'c", "BAR": "z"}


@pytest.mark.parametrize("path,expected", [
    ("/home/u/.claude/projects/-x/memory/MEMORY.md", True),
    ("/home/u/.claude/projects/-x/memory/feedback_testing.md", True),
    ("/repo/CLAUDE.md", True),
    ("/repo/CLAUDE.local.md", True),
    ("/repo/.claude/rules/deploy.md", True),
    ("/home/u/.openclaw/workspace/memory/2026-10-20.md", True),
    ("C:\\Users\\u\\.claude\\CLAUDE.md", True),
    ("/repo/src/app.py", False),
    ("/repo/src/memory/cache.ts", False),
    ("/repo/README.md", False),
])
def test_is_memory_path(path, expected):
    assert sc.is_memory_path(path) is expected
