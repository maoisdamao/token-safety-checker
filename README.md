# token-safety-checker

An [OpenClaw](https://openclaw.ai) agent skill that scans `openclaw.json` for plaintext secrets and migrates them to environment variables using SecretRef.

## What it does

1. **Scans** `openclaw.json` for plaintext tokens, API keys, and passwords
2. **Detects** your shell (zsh, bash, fish, dash) and the right profile file
3. **Migrates** secrets to env vars in your shell profile
4. **Updates** `openclaw.json` to use `SecretRef` format
5. **Restarts** the gateway with the correct sourcing order

## Install

```bash
clawhub install token-safety-checker
```

## Usage

Just ask your OpenClaw agent:

> "Check token safety"
> "Scan openclaw config for plaintext secrets"
> "Move my tokens to env vars"

## Supported shells

| Shell | Profile file |
|-------|-------------|
| zsh   | `~/.zshrc` |
| bash  | `~/.bashrc` / `~/.bash_profile` |
| fish  | `~/.config/fish/config.fish` |
| sh / dash | `~/.profile` |

## Contributing

PRs welcome. See [SKILL.md](SKILL.md) for the full workflow spec.

## License

MIT
