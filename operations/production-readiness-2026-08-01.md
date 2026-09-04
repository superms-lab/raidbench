# RaidBench 上线就绪记录（更新于 2026-08-02）

## 一句话状态

技术系统、商户身份、PayPal Live 与 Webhook 已完成生产配置，公开购买入口已经打开。
访客现在可以注册账户并购买点数；首笔真实买家交易尚未发生，因此首单仍需重点核对
Capture、Webhook、120 点入账和站内答案交付。

## 已完成

- Cloudflare Pages 承载公开内容与客户界面。
- Cloudflare Worker 将同源 `/api/*` 安全转发到 VPS。
- RaidBench 在 VPS 使用独立目录、容器、SQLite 数据库与密钥。
- 注册、登录、点数余额、订单历史和站内答案交付已实现。
- 自动密码重置的数据库、API、前端和安全测试已完成；SMTP2GO 生产发信已启用。
- 当前 VPS 应用版本为 `/opt/raidbench/releases/20260802T160057Z`；Cloudflare Pages 公开版本为
  `https://d747b22c.raidbench.pages.dev`。
- `notify.raidbench.com` 的 SMTP2GO 发件域名、三条 DNS-only CNAME 和跟踪域名 SSL 已验证。
- 生产 API 密钥仅允许 `/email/send`；打开/点击跟踪、退订页脚、审计抄送均关闭，旧 Resend
  密钥保留为未启用后备，没有影响 LeadAuditLab。
- 真实恢复邮件已由 SMTP2GO 投递到 `support@raidbench.com`，并经 Cloudflare Email Routing
  转发至 Gmail；邮件按钮已成功打开生产密码重置表单，测试令牌随后已作废。
- 公网 `/api/config` 已确认 `passwordResetEnabled=true` 和
  `liveReadiness.passwordResetEmailReady=true`。
- SMTP2GO 登录密码已由站长本人完成轮换；轮换后复核确认生产 API 密钥仍为 Online，
  `notify.raidbench.com` 仍为 Verified / Enabled。
- PayPal Live REST App `RaidBench Live` 已创建，Live Client ID、Client Secret 和 Webhook ID
  已写入 VPS 私密环境文件。
- PayPal 企业后台登记主体已核实为 `少年有为（上海）科技有限公司`，注册国家为中国大陆；
  生产配置使用精确法定名称和 `CN`，没有把品牌名冒充为法定主体。
- Live Webhook 已绑定 `https://raidbench.com/api/payments/paypal/webhook`，订阅 13 类支付、
  退款与争议事件；PayPal API 二次查询确认配置存在。
- 站长已授权按现有北美首发政策开启收款；税费继续作为内部留存项处理，不把规划留存比例
  表述为最终税务结论，正式申报口径仍由公司会计确认。
- 支付与退款事件具备签名验证、重复事件幂等和异常人工复核状态。
- 答案无把握、数据过期或不支持时不扣点。
- 付费 Rust 数据每 6 小时自动复核，SQLite 每日自动备份。
- 隐私政策、服务条款、退款政策和购买确认已上线。
- 免费 SEO 页面、站点地图和 D1 浏览量统计已上线。
- Cloudflare 到 VPS 的 RaidBench 私有 Caddy 路由已恢复并验证，LeadAuditLab 公网页面未受影响。
- 首页付费入口已通过 Live 自动闸门并公开显示；任一商户、PayPal 或 Webhook 条件失效时会
  自动重新隐藏。
- 公网非支付冒烟测试已完成：注册返回 201、认证会话可读取、退出成功；测试账户已从生产库删除。
- 公网 Live 无资金探测已完成：正式 PayPal 创建了 `$19.00 USD` 订单并返回 `paypal.com`
  审批链接；订单保持 `CREATED / pending_approval`，客户点数保持 0。测试账户和本地待付款
  记录随后已清理，清理前已创建 SQLite 一致性备份。
- 生产数据库升级后 `PRAGMA integrity_check=ok`，容器状态为 `running healthy`。

## 尚未完成

- 首笔真实买家尚未付款；真实 Capture、签名 Webhook、120 点入账、消费答案、退款和 PayPal
  对账仍需在首单发生后逐项留证。
- 不使用站长自买、自付或虚构订单制造交易记录；第一笔资金验证应来自真实客户购买。
- 北美税务留存是保守经营缓冲，不是税务鉴证；达到显著销售额、扩展新地区或申请提现前，
  需要由公司会计复核中国申报和买方所在地税务处理。
- R2 加密异地备份代码与定时器已准备；R2 桶、桶级密钥、首次上传和恢复演练尚未完成。

## 赚钱闭环

```text
Google / AI 搜索 / 合规社区回复
  -> 免费攻略或计算器
  -> 明确问题与专业证据
  -> 注册账户
  -> PayPal 购买点数
  -> 网站内立即获取答案
  -> 纠错、退款与内容更新
  -> 再次购买或推荐
```

VPS 解决“系统持续在线”，PayPal 解决“付款”，攻略与分发解决“为什么有人来并愿意买”。
只有三部分同时工作，项目才是商业闭环。

## 首笔真实订单的准确处理方式

真实收款入口已经开放。首笔客户支付后，立即核对 PayPal Capture、签名 Webhook、订单状态、
120 点一次性入账和客户账户内的答案交付；若任一步异常，先关闭 `RAIDBENCH_CHECKOUT_ENABLED`
并处理退款或人工补发，不继续扩大流量。首单完成并对账后，再逐步增加社区发布或付费获客。
