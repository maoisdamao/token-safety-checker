# token-safety-checker · tightlip — project memory

Long-term memory for Claude sessions in this repo. Current progress and next steps live in
@docs/STATUS.md (imported below) — read it first when asked "where are we" or "what's next".

## What this is
A skill that finds plaintext secrets in AI-agent config **and memory** (OpenClaw + Claude Code), migrates config
secrets to SecretRefs, and installs guards against new leaks. One codebase, two names:
- ClawHub slug **`token-safety-checker`** — https://clawhub.ai/maoisdamao/skills/token-safety-checker
- Claude plugin / skill **`tightlip`** — marketplace `maoisdamao` (this repo), plus `tightlip.zip` on each GitHub release

## Layout
- `plugins/tightlip/` — **the only folder that ships** (to ClawHub and the Claude marketplace). Keep it to the skill:
  `SKILL.md`, `scripts/safeclaw.py`, `README.md`, `LICENSE.md`, `.claude-plugin/plugin.json` + `icon.png`.
- `.claude-plugin/marketplace.json` — marketplace "maoisdamao" → `./plugins/tightlip`
- `tests/` — pytest; `test_integration_platforms.py` runs real `openclaw` / `claude` CLIs when installed (skipped otherwise)
- `tools/build_claude_skill.py` — builds `dist/tightlip.zip` for claude.ai upload
- `docs/prd/` — PRDs (next: `v3.1-prd.md`), `docs/launch/` — announcement copy, `docs/STATUS.md` — progress log
- `.github/workflows/`: `test.yml` (every push), `publish.yml` (tag `v*` or manual dispatch), `clawhub-scan-report.yml`

## Commands
- Tests: `python3 -m pytest -q` (Python 3.10+; CI runs 3.10 and 3.13)
- Run: `python3 plugins/tightlip/scripts/safeclaw.py {scan,memory,migrate,verify,install-guard,uninstall-guard}`
- Validate plugin: `claude plugin validate --strict .`
- Claude bundle: `python3 tools/build_claude_skill.py`

## Hard rules (the product is a security tool — reviewers scan it)
- Secret values never appear in stdout/stderr, CLI args, logs or files we print. Tests assert this (`assert_no_secrets`).
- Python standard library only; **no network calls and no URLs in `safeclaw.py`** (a URL triggered a Claude directory
  credential-policy hold in 3.0.1).
- No secrets in the repo, not even fake-looking ones: tests build fakes at runtime (`tests/conftest.py`, `Fake`, `rand`).
- Files holding secrets are created private *before* writing: `atomic_write_bytes` / `private_copy` / `append_private`
  (mkstemp / O_EXCL, mode 600). Never write secrets to the shell profile — `migrate` uses `~/.openclaw/tightlip.env`.
- No bypass hints (`--no-verify`) in messages; `install-guard` needs an explicit `--platform`.
- SKILL.md frontmatter keys only: name, description, license, allowed-tools, metadata (single-line JSON), compatibility.
  `${CLAUDE_SKILL_DIR}` for Claude, `{baseDir}` for OpenClaw.
- ClawHub scanners (ClawScan, SkillSpector, static analysis, VirusTotal) flag: predictable temp files, secrets in
  profiles, `secrets.env`-style names, deep indentation / long separator lines. Check new code against them.

## Release checklist
1. Bump the version in **three places**: `plugins/tightlip/.claude-plugin/plugin.json`, SKILL.md `metadata.version`,
   `VERSION` in `safeclaw.py` (publish.yml's check-version job enforces this).
2. `CHANGELOG.md` entry `## [x.y.z] - date` (publish extracts it as the ClawHub changelog); README if user-facing.
3. Tests green → PR → merge to `main`.
4. Release: push tag `vX.Y.Z`, or Actions → Publish → Run workflow with the version (cloud sessions can't push tags).
5. ClawHub then queues the version for its safety check (ClawScan + trufflehog). It shows as not-yet-latest until the
   scans finish — about an hour, longer when the queue is busy. That's normal, not a failed release.
   Check: `clawhub inspect @maoisdamao/token-safety-checker --versions --json` or the security-audit page.
6. Claude: the marketplace picks up `main` automatically; the directory listing is re-reviewed by Anthropic.

## Working agreements with the owner (maoisdamao)
- Owner often writes in Chinese; reply in the owner's language. Code, commits and docs in English.
- Propose before big changes; owner picks scope. Red-teaming features were deliberately grouped into v3.1.
- Workflow: branch → tests → PR → merge → owner runs Publish.
- At the end of a work session, update `docs/STATUS.md` (status block + a dated log entry). Durable lessons go here.
