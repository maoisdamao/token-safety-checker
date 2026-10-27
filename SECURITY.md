# Security Policy

## Purpose

`token-safety-checker` (tightlip) is a **defensive security tool**. It exists to *find and remove* plaintext
secrets from AI agent configuration and memory, not to extract or exfiltrate them.

## What this skill reads

- `openclaw.json` (and, with `--deep`, its git history)
- Agent memory and transcripts, read-only (`memory` / `scan --memory`):
  - OpenClaw: workspace memory files, `memory/`, `agents/*/sessions`, `agents/*/agent/*.sqlite` (opened read-only), `logs/`
  - Claude Code: `CLAUDE.md` files, `.claude/rules`, auto memory, `history.jsonl`, session transcripts
- It does **not** read `~/.openclaw/credentials/` or other credential stores

## What this skill writes (only when you run these commands)

- `migrate`: a timestamped backup of `openclaw.json` (created with mode 600), env exports in a private secrets file (`~/.openclaw/tightlip.env`, mode 600 before any value is written), one non-secret line in your shell profile that loads it, SecretRefs in `openclaw.json`. All rewrites use exclusive, private temp files.
- `verify --clean-backup`: deletes backups that still contain plaintext secrets
- `install-guard --platform …` (platform must be named explicitly): a `PreToolUse` hook in `~/.claude/settings.json` (backup written first) + a copy of the script in `~/.claude/hooks/`; a git `pre-commit` hook in OpenClaw workspaces (never overwrites a hook it did not create)

## Guarantees

- Secret values are **never printed, logged, passed as CLI arguments, or transmitted**. Output contains paths,
  line numbers, detector names, lengths and truncated SHA-256 fingerprints only. The test suite asserts this for every command.
- No network requests. Python standard library only.
- The Claude Code guard fails open: if the hook itself errors, your session is not blocked.

## Reporting a vulnerability

Please open a GitHub issue (without including any real secret) or contact the maintainer directly.
