---
name: token-safety-checker
description: Scan openclaw.json for plaintext secrets (tokens, API keys, passwords) and migrate them to environment variables using SecretRef. Use when the user asks to "check token safety", "privatize secrets", "move tokens to env vars", "audit openclaw config for secrets", or after any openclaw.json edit that may have introduced plaintext credentials. Also use when setting up a new OpenClaw instance for the first time.
---

# Token Safety Checker

Scan `openclaw.json` for plaintext secrets and migrate them to environment variables via SecretRef.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/scan_tokens.py` | Detect plaintext secrets; output findings + shell info |
| `scripts/migrate_tokens.py` | Perform all writes: backup → profile → config update |

All file modifications go through `migrate_tokens.py` — the agent never writes files directly.

## Workflow

### 1. Scan

```bash
python3 <skill_dir>/scripts/scan_tokens.py [path/to/openclaw.json]
```

Output: `{ findings: [{path, env_var, length}], shell: {name, profile, source_cmd} }`

- Exit 0 = clean → report and stop
- Exit 1 = findings present → continue
- Exit 2 = config file not found

### 2. Show findings to user and confirm

Present a table: `path | suggested env_var | length`. Allow the user to rename any env var. **Do not proceed without explicit confirmation.**

### 3. Collect plaintext values

Read `openclaw.json` to extract the current plaintext values for each flagged path. These are passed to `migrate_tokens.py` and never logged or displayed.

### 4. Dry-run first

```bash
python3 <skill_dir>/scripts/migrate_tokens.py \
  --dry-run \
  --findings '<JSON>' \
  --config ~/.openclaw/openclaw.json
```

Show the dry-run output to the user. Confirm before proceeding.

### 5. Run migration

```bash
python3 <skill_dir>/scripts/migrate_tokens.py \
  --findings '<JSON>' \
  --values '<path→value JSON>' \
  --config ~/.openclaw/openclaw.json
```

The script:
1. **Backs up** `openclaw.json` → `openclaw.json.bak`
2. **Appends** env exports to the shell profile (skips duplicates)
3. **Replaces** plaintext values with SecretRef in `openclaw.json`

### 6. Source profile + restart gateway

⚠️ **Check how the gateway is managed before this step:**

**Shell-launched gateway (most local setups):**
```bash
source <profile>          # e.g. source ~/.zshrc
openclaw gateway restart
```

**systemd-managed gateway:**
```
source profile does NOT work — env vars won't reach the service.
Add vars to the systemd unit's EnvironmentFile= instead:
  sudo systemctl edit openclaw-gateway
  # Add: EnvironmentFile=/etc/openclaw/gateway.env
```

**Docker / container:**
```
Pass env vars via docker run -e or docker-compose environment: section.
```

### 7. Verify

```bash
python3 <skill_dir>/scripts/scan_tokens.py   # exit 0 = clean
openclaw gateway status                       # should show running
```

### 8. Rollback (if needed)

```bash
python3 <skill_dir>/scripts/migrate_tokens.py --restore
```

## SecretRef format

```json
{ "source": "env",  "provider": "default", "id": "MY_ENV_VAR" }
{ "source": "file", "provider": "default", "id": "/path/to/secret.txt" }
{ "source": "exec", "provider": "default", "id": "command --that --prints --secret" }
```

## Security notes

- `env`-based SecretRefs store values in shell profile files, which are **plaintext on disk**. This is better than openclaw.json (which may be shared/committed), but consider `file` or `exec` refs for higher-security environments.
- The scanner flags fields matching sensitive key names (`token`, `apikey`, `key`, `password`, `secret`, `credential`) with value length ≥ 16. Existing SecretRefs are skipped.
- Gemini API key often appears at multiple paths — safe to share one env var.
