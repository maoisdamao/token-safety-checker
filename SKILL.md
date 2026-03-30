---
name: token-safety-checker
description: Scan openclaw.json for plaintext secrets (tokens, API keys, passwords) and migrate them to environment variables using SecretRef. Use when the user asks to "check token safety", "privatize secrets", "move tokens to env vars", "audit openclaw config for secrets", or after any openclaw.json edit that may have introduced plaintext credentials. Also use when setting up a new OpenClaw instance for the first time.
---

# Token Safety Checker

Scan `openclaw.json` for plaintext secrets and migrate them to environment variables via SecretRef.

## Workflow

### 1. Scan for plaintext secrets

```bash
python3 <skill_dir>/scripts/scan_tokens.py [path/to/openclaw.json]
```

Output JSON: `{ findings: [...], shell: { name, profile, source_cmd, export_fmt } }`

- Exit 0 = clean, exit 1 = findings present, exit 2 = file not found
- Shell detection uses `$SHELL` env var; supports zsh, bash, fish, dash, sh

If no findings → report clean and stop.

### 2. Confirm with user

Show a table of findings (path + suggested env var). Let the user rename any env var before proceeding. Do not write anything until confirmed.

### 3. Write env vars to shell profile

Use the `profile` path returned by the scanner. Check for existing `export` lines to avoid duplicates.

**Shell syntax differs:**
- zsh / bash / sh / dash: `export MY_VAR="value"`
- fish: `set -gx MY_VAR "value"` (written to `~/.config/fish/config.fish`)

Read the profile file first, append only missing lines.

### 4. Update openclaw.json with SecretRefs

Replace each plaintext value with:
```json
{ "source": "env", "provider": "default", "id": "ENV_VAR_NAME" }
```

Use Python to read/write JSON — avoids shell quoting issues with special characters in tokens.

Multiple paths sharing the same value (e.g. `gateway.auth.token` + `gateway.remote.token`) can point to the same env var.

### 5. Source profile AND restart gateway

⚠️ Both steps are required and must run in this order:

```bash
source <profile>          # use the path from scanner output
openclaw gateway restart
```

**Why:** The gateway daemon inherits env from the shell that started it. Without `source`, new env vars are invisible to the restarted process — causing auth failures even though the config looks correct.

For fish shell, use `. <profile>` or open a new terminal session.

### 6. Verify

```bash
python3 <skill_dir>/scripts/scan_tokens.py   # should show empty findings
openclaw gateway status                       # should show running
```

## SecretRef format

```json
{ "source": "env",  "provider": "default", "id": "MY_ENV_VAR" }
{ "source": "file", "provider": "default", "id": "/path/to/secret.txt" }
{ "source": "exec", "provider": "default", "id": "command --that --prints --secret" }
```

`env` is recommended for most setups.

## Scanner notes

- Flags fields whose key contains: `token`, `apikey`, `key`, `password`, `secret`, `credential` with value length ≥ 16
- Skips values already in SecretRef format `{ source: ... }`
- Common deduplication: Gemini API key often appears in both `tools.web.search.gemini.apiKey` and `skills.entries.*.apiKey` — safe to share one env var
