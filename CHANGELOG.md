# Changelog

All notable changes to token-safety-checker are documented here.

---

## [3.0.0] - 2026-10-25

**tightlip** — v3 takes secrets out of agent memory, not just config. Same skill on ClawHub
(`token-safety-checker`) and now on Claude (`tightlip`).

### Added
- **Memory + transcript scan** (`memory`, or `scan --memory`) for OpenClaw and Claude Code
  - long-term: OpenClaw `MEMORY.md` / `USER.md` / `DREAMS.md` / persona files / `memory/imports`; Claude Code `CLAUDE.md`, `CLAUDE.local.md`, `.claude/rules`, auto memory (`~/.claude/projects/*/memory`)
  - short-term: OpenClaw daily notes (`memory/YYYY-MM-DD.md`, written by the pre-compaction flush), Claude Code prompt history
  - transcripts: OpenClaw session `.jsonl` + `.sqlite`, Claude Code session `.jsonl` + tool results
  - logs: OpenClaw `logs/*.jsonl` — on OpenClaw ≤ 2026.6, `config-audit.jsonl` recorded `openclaw config set` arguments, including tokens
- **Value-based detectors** for Anthropic, OpenAI, GitHub, Slack, AWS, Stripe, Discord, Telegram, Google, Hugging Face, JWT, private keys, bearer tokens, URL credentials and high-entropy assignments — with placeholder filtering
- **Live-secret matching** — flags memory hits that equal a secret currently in `openclaw.json` or behind a SecretRef env var (rotate these first)
- **Fingerprints** (`sha256:xxxxxxxx`) to correlate the same secret across files without revealing it; per-provider rotation hints
- **`install-guard` / `uninstall-guard`** — Claude Code `PreToolUse` hook that denies writing secrets into memory / instruction files (`--scope all` for every write); OpenClaw workspace git `pre-commit` hook
- Claude Code plugin + marketplace (`/plugin install tightlip --marketplace maoisdamao/token-safety-checker`), claude.ai upload bundle (`tightlip.zip` on each GitHub release)
- Config scan also detects provider-shaped values under any key, plus `Authorization` / `bearer` keys and current OpenClaw keys (`channels.telegram.botToken`, Slack `botToken` / `appToken` / `signingSecret`, multi-account `channels.*.accounts.*`)
- `migrate --secure-profile`, `migrate --list-backups`, `migrate --restore --backup FILE`
- Test suite (unit + real OpenClaw / Claude Code CLI integration) and CI on every push; publishing runs only after tests pass

### Fixed
- `migrate` wrote list paths (`providers[0].apiKey`) to a wrong key named `"providers[0]"`
- Two different secrets sharing an env var hint (e.g. `gateway.auth.token` / `gateway.remote.token`) silently lost one value — scan now assigns unique names and migrate refuses collisions
- Re-running `migrate` overwrote the original `.bak` — backups are now timestamped, `chmod 600`, never overwritten; `--restore` picks the newest of ours (falls back to the v2 `.bak`) and ignores OpenClaw's own rotating backups
- Profile duplicate check was a substring match (`FOO_TOKEN` matched `FOO_TOKEN_2`) and skipped vars that held a *different* (stale) value — now exact-name and value-aware
- JSON5 configs (comments / trailing commas) crashed `scan`; now scanned, and `migrate` refuses to rewrite them instead of deleting comments
- `migrate` reformatted the config with 4-space indents — now keeps the original indentation, file mode, and writes atomically
- `verify` treated `file` / `exec` SecretRef ids as env var names; `file` refs are now checked for existence and permissions
- `${VAR}` env templates and `tokenFile` / `*Path` pointer keys are no longer reported as secrets

### Changed
- `verify` now flags any backup that still holds plaintext — including OpenClaw's own `openclaw.json.bak*` — and `--clean-backup` removes those
- `verify` warns when the shell profile holding exports is readable by others
- SKILL.md frontmatter is valid for both ClawHub and claude.ai (`homepage` / `author` moved into `metadata`)
- Scan findings include a `fingerprint`; output JSON includes `version`

---

## [2.0.0] - 2026-04-02

### Added
- **Risk classification** — every finding now includes a risk level (🔴 HIGH / 🟡 MEDIUM / 🟢 LOW) based on token type, so users know what to fix first
- **Git history scan** (`scan --deep`) — detects past commits where `openclaw.json` contained plaintext secrets; returns paths + risk only, never values; reminds users to rotate tokens since git history is permanent
- **File permission check** — `scan` now warns if `openclaw.json` is not `chmod 600`
- **`verify` subcommand** — post-migration health check: confirms no plaintext remains, checks file permissions, verifies all SecretRef env vars are actually set in the current environment, and offers `--clean-backup` to delete the `.bak` file
- **Auto-verify after migrate** — `migrate` automatically runs `verify` on completion

### Changed
- `scan` output now includes a `checks` block with file permission status
- `scan` findings now include a `risk` field

---

## [1.0.9] - 2026-04-01

### Changed
- Restored standard MIT license on GitHub (clawhub displays MIT-0 per platform policy)

---

## [1.0.8] - 2026-04-01

> Reverted in v1.0.9

---

## [1.0.7] - 2026-04-01

### Fixed
- Renamed `LICENSE` → `LICENSE.md` so it gets included in clawhub packages (clawhub excludes files without extensions)

---

## [1.0.6] - 2026-04-01

### Security
- Fixed shell injection vulnerability in `migrate`: env var names are now validated against `^[A-Z_][A-Z0-9_]*$`
- Fixed shell injection in profile writes: values are now wrapped in single quotes with proper `'` escaping instead of double quotes (prevents `$()` and backtick expansion when the profile is sourced)
- Added `license: MIT` field to `SKILL.md` (later removed in v1.0.8 as clawhub ignores this field)

---

## [1.0.5] - 2026-03-31

### Changed
- README: improved wording, added Security trade-offs section

---

## [1.0.4] - 2026-03-31

### Changed
- Merged scan + migrate into a single `safeclaw.py` entry point
- Secret values no longer passed through CLI arguments at any point

---

## [1.0.3] - 2026-03-31

### Added
- `homepage` and `author` fields in SKILL.md
- MIT License
- SafeClaw crab logo (`assets/safeclaw.png`)

---

## [1.0.2] - 2026-03-31

### Changed
- README rewritten in English + Chinese (bilingual)
- Added slogan: *Safe claws don't leak. 🦀*

---

## [1.0.1] - 2026-03-31

### Fixed
- Security: added config backup before modification
- Added systemd warning in post-migrate instructions

---

## [1.0.0] - 2026-03-30

### Added
- Initial release
- `scan`: detect plaintext secrets in `openclaw.json`, return paths + lengths only
- `migrate`: write secrets to shell profile as env vars, update config to SecretRef
- `migrate --restore`: roll back to `.bak`
- `migrate --dry-run`: preview changes without writing
- Supports zsh, bash, fish, sh/dash
