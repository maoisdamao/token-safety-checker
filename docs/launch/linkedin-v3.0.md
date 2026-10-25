# LinkedIn post — v3.0 launch

🤐 Your AI agent has a great memory. That's the problem.

It remembers your preferences. Your project. Your deadlines.
And sometimes… your API keys. 🔑😬

Paste a token into chat once, and it can quietly end up in MEMORY.md, a daily note, CLAUDE.md or a session transcript. Every one of those gets sent back to the model, again and again.

So I shipped **Token Safety Checker v3.0, a.k.a. tightlip** 🦀✳️
Now for both **OpenClaw** and **Claude Code**.

🆕 What's new:

🧠 **Memory scan.** It checks long-term memory (MEMORY.md, CLAUDE.md, auto memory), short-term memory (daily notes, prompt history), session transcripts and logs.

🎯 **Live-match alerts.** It flags when a leaked value is the exact token your agent is using right now, so you know what to rotate first.

🛡️ **Leak guard.** On Claude Code, a hook blocks secrets from being written into memory files, and Claude writes a ${PLACEHOLDER} instead. On OpenClaw, a pre-commit hook keeps them out of your workspace repo.

🔧 **Safer migrate.** Timestamped backups that never get overwritten, unique env var names, JSON5 support and a one-command rollback.

🙈 **Still zero secrets in output.** You only ever see paths, line numbers and fingerprints like sha256:93be4b37. Everything runs 100% locally, with no network calls.

🕵️ Fun fact from testing: on OpenClaw, setting a token with `openclaw config set` can leave a plaintext copy in the config audit log, and OpenClaw's own config backups keep plaintext tokens after you migrate. v3.0 finds both.

📦 Install:
🦀 OpenClaw → clawhub install token-safety-checker
✳️ Claude Code → /plugin install tightlip --marketplace maoisdamao/token-safety-checker

Then just ask your agent: "Did I leak any API keys into your memory?" 💬

Agents talk. Secrets don't. 🤐

🔗 https://github.com/maoisdamao/token-safety-checker
🔗 https://clawhub.ai/maoisdamao/skills/token-safety-checker

#AIAgents #AISecurity #ClaudeCode #OpenClaw #DevSecOps #LLMSecurity #OpenSource #AppSec
