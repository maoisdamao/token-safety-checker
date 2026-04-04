<p align="center">
  <img src="assets/safeclaw.png" width="120" alt="SafeClaw logo" />
</p>

# 🔐 Token Safety Checker

**Safe claws don't leak.** 🦀

Most OpenClaw users don't realize their API keys and bot tokens are sitting in plain text inside `openclaw.json`. This skill finds them and locks them down — automatically, locally, with zero data sent anywhere. 🛡️

- 🙈 **Tokens never appear in output or CLI args** — scan returns field names only; migration reads values from disk internally
- 🏠 **Runs 100% on your local machine** — no network calls, no telemetry, no cloud
- 💾 **Non-destructive** — backs up your config before touching anything
- ↩️ **Reversible** — one command to roll back if something goes wrong

---

## 📦 Install

```bash
clawhub install token-safety-checker
```

## 💬 Usage

Just ask your OpenClaw agent:

> "Check token safety"
> "Scan my openclaw config for plaintext secrets"
> "Move my tokens to env vars"

The agent will scan, show you exactly what it found, ask for confirmation, then migrate everything safely. ✨

---

## 🆕 What's new in v2.0

### 🔴🟡🟢 Risk classification

Every finding now comes with a risk level so you know what to fix first:

| Level | What it means |
|-------|---------------|
| 🔴 HIGH | Controls the agent directly — Discord token, Telegram token, gateway auth |
| 🟡 MEDIUM | Third-party service keys — OpenAI, Gemini, Brave |
| 🟢 LOW | Other credentials |

### 🕵️ Git history scan (`--deep`)

Even after migrating, your old commits may still contain plaintext tokens. Run a deep scan to find out:

```
safeclaw scan --deep
```

Output shows which commits exposed which secrets (paths + risk only, never values), and reminds you to rotate any affected tokens since git history is permanent.

### 🔒 File permission check

`scan` now automatically checks whether `openclaw.json` has safe permissions (`600`). If not, it tells you the exact command to fix it.

### ✅ Post-migration verify (`verify`)

After `migrate` completes, a health check runs automatically. You can also run it standalone at any time:

```
safeclaw verify
safeclaw verify --clean-backup   # also deletes the .bak file
```

Checks:
- No plaintext secrets remain in config
- `openclaw.json` permissions are `600`
- All SecretRef env vars are actually set in the current environment
- Backup `.bak` file cleanup status

---

## 🔍 Full workflow

1. 🔎 **Scan** `openclaw.json` for plaintext credentials — returns paths + risk levels, never values
2. 👀 **Review** what's exposed and at what risk level
3. 💾 **Backup** created automatically before any changes
4. 🚚 **Migrate** secrets to environment variables in your shell profile
5. ✏️ **Update** `openclaw.json` to use SecretRef pointers
6. ✅ **Verify** migration succeeded — env vars set, permissions correct, nothing left exposed
7. 🕵️ **Deep scan** git history to catch past exposures and decide if rotation is needed

## 🐚 Supported shells

| Shell | Profile file |
|-------|-------------|
| zsh   | `~/.zshrc` |
| bash  | `~/.bashrc` / `~/.bash_profile` |
| fish  | `~/.config/fish/config.fish` |
| sh / dash | `~/.profile` |

## ⚖️ Security trade-offs

This tool moves secrets **out of `openclaw.json`** (which may be shared or committed) **into shell profile files** (local, user-owned). That's a meaningful improvement, but shell profiles are still plaintext on disk.

For higher-security setups, consider:
- `file`-based SecretRef pointing to a file with `chmod 600`
- `exec`-based SecretRef using a password manager (e.g. `op read`)
- systemd `EnvironmentFile=` with restricted permissions

Always run `--dry-run` first and review the exact lines before applying.

## 🤝 Contributing

PRs welcome! See [SKILL.md](SKILL.md) for the full workflow spec.

## 📄 License

MIT

---

⭐ If this saves your tokens, a star goes a long way — it helps other OpenClaw users find the tool. 🦀🤝

---

# 🔐 Token 安全检查器

**Safe claws don't leak. 🦀 安全的爪子不会泄漏。**

大多数 OpenClaw 用户不知道，自己的 API Key 和 Bot Token 正以明文形式躺在 `openclaw.json` 里。这个 skill 会自动找到它们，并在本地完成保护——零数据上传，全程不联网。🛡️

- 🙈 **Token 值不会出现在输出或命令行参数中**
- 🏠 **100% 本地运行** — 无网络请求、无遥测
- 💾 **无损操作** — 修改前自动备份
- ↩️ **可回滚** — 一条命令恢复到操作前状态

---

## 📦 安装

```bash
clawhub install token-safety-checker
```

## 💬 使用方式

直接告诉你的 OpenClaw agent：

> "检查一下 token 安全"
> "扫描 openclaw 配置里的明文 secret"
> "把我的 token 移到环境变量里"

---

## 🆕 v2.0 新功能

### 🔴🟡🟢 风险分级

每条发现都附带风险等级，让你知道优先修哪个：

| 等级 | 含义 |
|------|------|
| 🔴 HIGH | 直接控制 agent — Discord token、Telegram token、gateway auth |
| 🟡 MEDIUM | 第三方服务 key — OpenAI、Gemini、Brave |
| 🟢 LOW | 其他凭据 |

### 🕵️ Git 历史扫描（`--deep`）

迁移完成后，旧 commit 里可能仍保留着明文 token。用深度扫描查清楚：

```
safeclaw scan --deep
```

只返回字段名和风险等级，不输出任何值。发现问题时会提醒你轮换相关 token——git 历史是永久的。

### 🔒 文件权限检查

`scan` 现在默认检查 `openclaw.json` 的文件权限是否为 `600`，不对就告诉你修复命令。

### ✅ 迁移后验证（`verify`）

`migrate` 完成后自动执行健康检查，也可以随时手动运行：

```
safeclaw verify
safeclaw verify --clean-backup   # 同时删除 .bak 备份文件
```

检查项：
- 配置中是否仍有明文 secret
- `openclaw.json` 权限是否为 `600`
- SecretRef 引用的环境变量是否真的已设置
- 备份文件清理状态

---

## 🔍 完整工作流程

1. 🔎 **扫描** — 返回字段名 + 风险等级，不输出任何值
2. 👀 **确认** — 查看暴露的字段及风险等级
3. 💾 **备份** — 自动生成 `openclaw.json.bak`
4. 🚚 **迁移** — 写入 shell profile 环境变量 + SecretRef
5. ✅ **验证** — 确认 env var 已设置、权限正确、无残留明文
6. 🕵️ **深度扫描** — 检查 git 历史，决定是否需要轮换 token

## ⚖️ 安全权衡

更高安全要求的场景可参考：
- `file` 类型 SecretRef，指向 `chmod 600` 的文件
- `exec` 类型 SecretRef，调用密码管理器（如 `op read`）
- systemd `EnvironmentFile=`，配合严格的文件权限

## 📄 许可证

MIT

---

⭐ 如果这个工具帮你保住了 token，欢迎 Star——让更多 OpenClaw 用户发现它。🦀🤝
