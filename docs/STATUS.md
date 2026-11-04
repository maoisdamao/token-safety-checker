# Status — token-safety-checker · tightlip

Short-term memory: where the project stands and what to do next. Update the status block and add a log entry at the
end of every work session (newest first). Long-term knowledge belongs in `/CLAUDE.md`.

## Current status (2026-11-02)

| | |
|---|---|
| Latest release | **v3.0.2** (2026-10-28): GitHub release ✅ · ClawHub ✅ published after its safety-check queue · Claude marketplace ✅ |
| Claude directory | `tightlip` listing submitted; new robot-head icon awaiting Anthropic review (nothing to do on our side) |
| Open branches | `claude/affectionate-darwin-uqq34p` — scan-report diagnostics (version list + publish-attempt probes) and this memory setup; merge to `main` |
| Tests | 78 passing |

## Next up: v3.1 — start from [`docs/prd/v3.1-prd.md`](prd/v3.1-prd.md)

Order (from the PRD's release plan), one PR each with tests:
1. **P0-1 `redact`** — in-place redaction of memory / transcripts / logs, dry-run first, backups + manifest, `--restore`
2. **P0-2 Claude Code config secrets** — `~/.claude.json` MCP env/headers, settings `env`, `.mcp.json`; `migrate --claude`
3. P1-1 memory poisoning heuristics · P1-2 installed-skill audit · P1-3 gateway exposure check
4. P2 items as time allows; unfinished items move to v3.2

Carry-overs into v3.1 (decided after the PRD was drafted):
- P0-2 must reuse the **3.0.2 private secrets file** (`~/.openclaw/tightlip.env`, private-before-write), not profile
  exports as the PRD's original wording says.
- All new write paths (redact backups, manifest) use `atomic_write_bytes` / `private_copy` — ClawScan checks this.
- P2-6 is partly done: `tightlip` is already submitted to the Claude directory; Codex / Cursor packaging remains.
- Open questions in PRD §5 (delete-whole-transcript option, separate `tightlip-audit` skill?, weekly reminder) —
  ask the owner before building.

## Log

### 2026-11-02
- ClawHub 3.0.2 "release failure" was the safety-check queue, not a failure; owner confirmed 3.0.2 is live via
  `clawhub inspect`. Session moved to the owner's machine (`claude --teleport`); added `CLAUDE.md` + this file.

### 2026-10-28 — v3.0.1, v3.0.2
- 3.0.1: new logo (scanner-eye robot with zipped mouth on Graphite), skill moved to `plugins/tightlip/`, URLs removed
  from the script. ClawScan flagged "migration can leave tokens readable by other users"; SkillSpector CRITICAL → never promoted.
- 3.0.2: private secrets file instead of profile exports, exclusive private temp files, explicit `--platform` for
  `install-guard`, `allowed-tools` in SKILL.md. Renamed `secrets.env` → `tightlip.env` and shortened separator lines
  after scanner hits.

### 2026-10-25 — v3.0.0
- Memory + transcript scan, value detectors, live-secret matching, fingerprints, `install-guard`, many `migrate` fixes,
  Claude plugin packaging (`tightlip`), CI with real OpenClaw / Claude Code. Redact + red-team features deferred to v3.1
  (PRD written). LinkedIn copy in `docs/launch/linkedin-v3.0.md`.
