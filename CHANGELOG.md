# Changelog

All notable changes to token-safety-checker are documented here.

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
