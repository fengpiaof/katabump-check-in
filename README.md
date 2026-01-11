# KataBump 服务器自动续期

[![KataBump Server Renew](https://github.com/YOUR_USERNAME/katabump-renew/actions/workflows/renew.yml/badge.svg)](https://github.com/YOUR_USERNAME/katabump-renew/actions/workflows/renew.yml)

自动续期 KataBump 免费服务器，基于 GitHub Actions 运行，无需自建服务器。

## 特性

- 🚀 **自动续期**: 每天自动执行两次续期任务
- 🔐 **绕过 Cloudflare**: 使用 `curl_cffi` 模拟真实浏览器 TLS 指纹
- 📱 **Telegram 通知**: 支持续期结果推送到 Telegram
- 🔄 **自动保活**: 防止 GitHub 因仓库不活跃而禁用定时任务

## 快速开始

### 1. Fork 本仓库

点击右上角的 `Fork` 按钮，将本仓库 Fork 到你的账号下。

### 2. 配置 Secrets

进入你 Fork 后的仓库，点击 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`，添加以下 Secrets：

| Secret 名称 | 必填 | 说明 |
|------------|------|------|
| `KB_EMAIL` | ✅ | KataBump 账号邮箱 |
| `KB_PASSWORD` | ✅ | KataBump 账号密码 |
| `KB_RENEW_URL` | ✅ | 续期页面 URL，格式: `https://dashboard.katabump.com/servers/edit?id=xxxxx` |
| `TELEGRAM_TOKEN` | ❌ | Telegram Bot Token (可选) |
| `TELEGRAM_USERID` | ❌ | Telegram 用户 ID (可选) |

### 3. 启用 Actions

1. 进入仓库的 `Actions` 页面
2. 点击 `I understand my workflows, go ahead and enable them`
3. 点击左侧的 `KataBump Server Renew`
4. 点击 `Run workflow` 手动触发一次测试

### 4. 获取续期 URL

1. 登录 [KataBump Dashboard](https://dashboard.katabump.com)
2. 点击你要续期的服务器
3. 复制浏览器地址栏中的 URL，格式类似: `https://dashboard.katabump.com/servers/edit?id=197288`

## 定时执行

默认配置为每天 UTC 时间 0:00 和 12:00 执行（北京时间 8:00 和 20:00）。

如需修改执行时间，编辑 `.github/workflows/renew.yml` 中的 `cron` 表达式：

```yaml
schedule:
  - cron: '0 0,12 * * *'  # 每天 UTC 0 点和 12 点
```

## Telegram 通知配置

### 获取 Bot Token

1. 在 Telegram 中搜索 `@BotFather`
2. 发送 `/newbot` 创建新机器人
3. 按提示设置名称，获取 Token

### 获取用户 ID

1. 在 Telegram 中搜索 `@userinfobot`
2. 发送任意消息，获取你的用户 ID

## 多服务器支持

如果你有多个服务器需要续期，可以：

1. 创建多个仓库，每个仓库配置一个服务器
2. 或者修改脚本支持多个 URL（用逗号分隔）

## 常见问题

### Q: 为什么验证码还是过不去？

A: Cloudflare Turnstile 验证有一定的随机性，脚本已经做了多次重试。如果持续失败，可能是：
- IP 被 Cloudflare 标记（GitHub Actions IP 可能被大量使用）
- 账号或服务器状态异常

### Q: 如何查看执行日志？

A: 进入仓库的 `Actions` 页面，点击对应的 workflow run 查看详细日志。

### Q: 定时任务没有执行？

A: GitHub 会在仓库 60 天无活动后禁用定时任务。本项目已配置 `keep-alive` 工作流自动保活。

## 致谢

- [linuxdo-checkin](https://github.com/doveppp/linuxdo-checkin) - CF 验证绕过方案参考
- [DrissionPage](https://github.com/g1879/DrissionPage) - 浏览器自动化框架
- [curl_cffi](https://github.com/yifeikong/curl_cffi) - TLS 指纹模拟库

## 免责声明

本项目仅供学习交流使用，请遵守 KataBump 的服务条款。因使用本项目造成的任何问题，作者不承担任何责任。

## License

MIT License
