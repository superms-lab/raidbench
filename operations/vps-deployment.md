# RaidBench VPS 部署手册

## 当前结论

RaidBench 已于 2026-08-01 独立部署到 VPS，并通过 Cloudflare Pages 的同源 `/api/*`
接口对外服务。PayPal Live 凭据、Webhook、精确商户身份和税务经营策略均已配置，
公开购买入口已经打开。

当前应用版本：`/opt/raidbench/releases/20260904T013111Z-phase8-palworld-live-v11`，运行镜像为
`local/raidbench-runtime:2026-09-04-phase8-palworld-live-v11`。该版本已启用 SMTP2GO 安全密码
重置、PayPal Live 独立 Webhook、飞书收款/退款提醒，以及付费 Raid Plan 的制作队列；
购买入口仍由独立的商户身份、税务、PayPal 凭据和 Webhook 闸门动态控制。

多游戏付费目录已进入生产数据库。Palworld 的 80 点基地与进度复核已处于 `ready_live`，并有
正好 80 点、13 美元的单次点数包；其余十项非 Rust 服务仍为 `hidden_pending_qa`。资料不足、
范围不支持、独立 QA 未通过或 30 分钟超时的 Palworld 请求统一不扣点。

多游戏影子答案 QA 使用独立镜像 `local/raidbench-content-agent:2026-09-04-shadow-qa-v2`、独立数据库
`/opt/raidbench-agent/data/raidbench.shadow.db` 和 `raidbench-shadow-qa.timer`。它不挂载客户订单库或
PayPal 密钥。第 6 阶段首批 33 个案例中有 6 个完整答案通过、5 个完整请求因证据不足不收费、
22 个缺资料或违规请求正确拒绝；当时没有任何非 Rust 产品达到准入线。

第 7 阶段已把套件扩展为 67 个不同案例，并增加复杂对局第二盲审、临时商城交付验收和私有
激活清单。第 8 阶段已完成签名生产队列、客户输入页、按单独立 QA、幂等扣点、站内交付和
无收费超时处理。上线后强制复核仍判定 Palworld 为 `ready_live` / `live_monitored`。

## 实际架构

```text
玩家
  -> Cloudflare Pages：公开页面、攻略、客户界面
  -> Pages Worker：D1 浏览量统计、/api/* 转发
  -> 带签名的 HTTPS 私有入口
  -> VPS Caddy
  -> 127.0.0.1:8080 的 raidbench-app 容器
  -> /opt/raidbench/data/raidbench.db
  -> PayPal API 与签名 Webhook
```

VPS 上已有的其他项目保持独立，RaidBench 不复用其应用目录、数据库或容器。

## VPS 目录与服务

```text
/opt/raidbench/app                         当前版本软链接
/opt/raidbench/releases/<timestamp>        不可变代码版本
/opt/raidbench/stacks/platform/compose.yaml
/opt/raidbench/secrets/runtime.env         600 权限，不得输出
/opt/raidbench/secrets/offsite-backup.env  R2 桶级凭据，600 权限
/opt/raidbench/secrets/restic-password     加密恢复口令，600 权限
/opt/raidbench/data/raidbench.db
/opt/raidbench/data/rust-raid-data.json
/opt/raidbench/data/backups/
/opt/raidbench/jobs/inbox                 生产应用写入；Agent 只读
/opt/raidbench/jobs/outbox                Agent 写入；生产导入器读取
/opt/raidbench/jobs/archive               已导入的签名任务与结果
/opt/raidbench/jobs/rejected              未通过生产校验的结果
```

容器名为 `raidbench-app`，只监听 `127.0.0.1:8080`。公网不能直接访问该端口；
Cloudflare Worker 与 Caddy 之间使用独立的源站签名密钥，缺少签名的请求返回 404。

## 健康检查

在 VPS 内检查：

```bash
curl -fsS http://127.0.0.1:8080/api/health
docker inspect --format '{{.State.Health.Status}}' raidbench-app
```

从公网检查：

```bash
curl -fsS https://raidbench.com/api/health
curl -fsS https://raidbench.com/api/config
curl -fsS https://raidbench.com/api/session
```

当前预期状态：

```text
mode=production
database=sqlite
delivery=in_account
paypalEnvironment=live
paypalWebhookReady=true
checkoutEnabled=true
passwordResetEnabled=true
paymentNotificationsEnabled=true
multigameQueueReady=true
```

`checkoutEnabled=true` 是当前生产预期值：PayPal Live 凭据、Webhook、精确商户法定名称、
注册国家和税务经营策略均已写入。任一条件失效时，后端会自动回到 `false` 并隐藏购买入口。

`passwordResetEnabled=true` 是当前生产预期值。SMTP2GO 发件域名、最小权限 API 密钥、
公网配置、真实 Gmail 投递和重置落地页均已验证；`support@raidbench.com` 继续作为人工支持
与 Reply-To 地址。

## Palworld 自动答案交付

`raidbench-live-answer.timer` 每分钟检查一次签名任务，每次最多处理一单。生产应用提交时仅预留
80 点，不写扣点流水；Agent 容器读取不含邮箱、付款信息和余额的任务，并用当前官方快照完成
作者与独立审查两阶段。`raidbench-answer-import.timer` 每分钟验证签名、请求一致性、答案指纹、
证据时效、QA 身份与交付合同，全部通过后才扣一次点并把答案写回原账户。

```bash
systemctl status raidbench-live-answer.timer raidbench-answer-import.timer
journalctl -u raidbench-live-answer.service -u raidbench-answer-import.service -n 100 --no-pager
python3 /opt/raidbench-publisher/workspace/scripts/export_multigame_live_status.py
```

任何证据不足、QA 拒绝、导入校验失败或超过 30 分钟的任务都会释放预留并以 0 点关闭。Agent
只读 inbox、只写 outbox，不挂载生产客户数据库或 PayPal 密钥。

## 账户恢复邮件

后端已实现 30 分钟、单次使用的密码重置令牌，令牌只以哈希形式持久化，重置后会注销
该账户的所有旧会话。邮件通过有并发上限的后台任务发送，不能从响应时间或响应正文判断
邮箱是否已经注册。

VPS 激活外部发送需要以下私密变量：

```text
RAIDBENCH_EMAIL_PROVIDER=smtp2go
SMTP2GO_API_KEY=<key restricted to /email/send>
RAIDBENCH_EMAIL_FROM=RaidBench <account@notify.raidbench.com>
```

当前 SMTP2GO 域名和真实邮件验收已完成。若该值以后回落为 `false`，先检查密钥、发件人
变量和容器日志；前端仍应以 `/api/config` 为准，不得硬编码自动重置入口状态。

## 收款与退款提醒

PayPal Capture 完成、付款待处理/拒绝、退款和撤销后，后端会异步发送飞书卡片。通知只包含
本地订单号、SKU、金额、币种、点数和状态，不发送玩家邮箱。买家回跳与 PayPal Webhook
可能同时到达，`owner_notifications` 发件箱会按订单和状态去重；飞书故障不会阻断付款或加点。

VPS 私密变量：

```text
RAIDBENCH_PAYMENT_FEISHU_WEBHOOK_URL=<飞书群自定义机器人 Webhook>
RAIDBENCH_PAYMENT_FEISHU_WEBHOOK_SECRET=<签名校验密钥>
```

公网 `/api/config` 的 `liveReadiness.ownerPaymentNotificationsReady=true` 表示提醒通道已配置。
排查时只查询状态，不输出 Webhook 或密钥：

```bash
sqlite3 /opt/raidbench/data/raidbench.db \
  "select order_id,notification_type,status,attempts,sent_at,last_error from owner_notifications order by created_at desc limit 20;"
docker logs --tail 100 raidbench-app
```

配置测试卡必须清楚标注“不是实际收款”，不得向生产订单表插入虚假成交记录。

## 自动内容校验

`raidbench-content-check.timer` 每小时运行一次：

```bash
systemctl status raidbench-content-check.timer
journalctl -u raidbench-content-check.service -n 50 --no-pager
```

校验脚本对照权威版本来源检查付费 Rust 数据。数据超过 72 小时没有成功复核时，
付费答案自动停止交付并且不扣点，避免用过期结论消耗玩家点数。

验证器同时写入 `/opt/raidbench/data/rust-paid-data-status.json`。状态不是 `verified`、接受版本与
最新版本不一致、文件 SHA-256 不一致或复核超过 72 小时时，后端会立即隐藏 Rust 服务和新点数
购买入口；已批准 PayPal 订单的 capture 与 webhook 仍可完成对账。2026-09-04 已验收 changelist
4045 `Breach and Clear`，当前公开健康接口返回 `paidDataStatus=verified`。

2026-09-04 已完成 changelist 4045 生产数据刷新：候选文件先在 `raidbench-app` 容器内通过校验，
再与匹配的数据状态文件一起原子替换。内容检查服务返回成功，公共 `/api/health` 显示
`paidDataVerifiedAt: 2026-09-03`、`paidDataStatus: verified` 且 `checkoutEnabled: true`。

## 数据备份

`raidbench-backup.timer` 每日创建经过 SQLite 完整性检查的本机滚动备份：

```bash
systemctl status raidbench-backup.timer
journalctl -u raidbench-backup.service -n 50 --no-pager
ls -lh /opt/raidbench/data/backups/
```

本机备份可以处理应用升级失误，但不能处理整台 VPS 丢失。`raidbench-offsite-backup.timer`
会在本机一致性备份完成后，将最新快照通过 restic 加密上传到私有 Cloudflare R2 桶：

```bash
systemctl status raidbench-offsite-backup.timer
journalctl -u raidbench-offsite-backup.service -n 100 --no-pager
```

具体密钥边界、保留策略和恢复演练见 `operations/offsite-backup.md`。只有 R2 凭据已配置、
首次上传成功且从独立目录恢复后 `PRAGMA integrity_check=ok`，才能把异地备份标记为完成。

## 公开来源拓客扫描

Source Scout 使用独立目录、账号和数据库，不读取订单、客户、PayPal 或生产答案数据：

```bash
systemctl status raidbench-source-scout.timer
journalctl -u raidbench-source-scout.service -n 100 --no-pager
sudo -u raidbench-agent sqlite3 /opt/raidbench-agent/data/raidbench.local.db \
  "select id, status, summary_json from agent_runs order by started_at desc limit 5;"
```

定时器每小时唤醒一次，25 个官方、发行商和 Steam 公告源全部使用与 Rust 相同的 1 小时
采集节奏。12 个社区需求配置则全部与 Rust 相同，每个游戏每天最多尝试一次；它只访问公开页面与
公开 JSON/RSS；失败来源会进入日志，不尝试绕过登录、验证码或站点限制。Reddit 来源
仍受单独的商业平台许可开关控制，关闭时不会抓取。扫描结果进入私有内容队列；独立帖子、
带链接内容和私信始终需要业主审核，不能由采集器直接发布。
采集器允许最多 10 分钟的到期容差，用来抵消 systemd 随机延迟，避免相邻两个小时窗口
相差不足 60 分钟时整轮跳过；该容差不会绕过来源访问限制或扩大并发。
定时器启用 `Persistent`，VPS 重启后会补跑；进程异常退出时 15 分钟后自动重试，
每小时最多连续尝试 3 次。

2026-08-11 首轮完整小时窗口已在线验证：8 个当前允许来源全部到期采集，得到 21 条信号和
4 条高价值信号。随后内容 Agent 自动重试并通过五阶段 QA，发布
`https://raidbench.com/pages/palworld-1-0-returning-player-revalidation`，线上返回 200，
IndexNow 返回 200，Sitemap 增至 60 个 URL。
同日将失效的 Palworld 新闻地址迁移到 `https://news.palworldgame.com/` 后，强制复核结果为
8/8 来源成功、22 条信号、4 条高价值信号、0 个失败来源。

## Codex 自动内容发布

2026-08-10 已启用独立的站内内容发布器：

```text
/opt/raidbench-publisher/workspace
/opt/raidbench-publisher/compose.yaml
/opt/raidbench-agent/codex
/opt/raidbench-agent/runtime-home
/opt/raidbench-agent/secrets/content-agent.env
/opt/raidbench-agent/artifacts/content-automation
```

它不在玩家请求链路内运行，也不读取 PayPal、订单或客户数据库。systemd 每小时启动一次
一次性非 root 容器；每日最多发布 1 个新攻略。选择逻辑只接受近期、可追溯的官方来源，
POE2 在同等质量候选中获得 2 分权重。Codex 的五个阶段均使用只读 Landlock 沙箱，最终
发布必须同时通过 JSON 合同、证据引用、内容政策、中文对齐和独立 QA。

```bash
systemctl status raidbench-content-agent.timer
systemctl list-timers raidbench-content-agent.timer --no-pager
journalctl -u raidbench-content-agent.service -n 100 --no-pager
sudo -u raidbench-agent sqlite3 /opt/raidbench-agent/data/raidbench.local.db \
  "select case_id,status,output_slug,published_at,last_error from content_automation_items order by created_at desc;"
```

QA 阻断时不构建、不部署；构建或 Pages 发布失败时恢复本次写入；Pages 已接收但生产核验
失败时保留内容并记录 `deployment_verification_failed`，避免错误地回滚一份可能已上线的
部署。成功后自动核对 `raidbench.com` 的状态、canonical 和品牌标记，并提交 IndexNow。
服务启动前会修正内容、页面、Sitemap 等有限输出路径的所有权。超过 30 分钟仍处于
`case_ready` 或 `agent_running` 的中断记录会自动转为可重试失败状态；异常退出也会落库，
不会继续占用每日发布额度并让后续周期看似正常、实际停滞。普通 Agent 输出失败在 1 小时后
重试，不触发 systemd 连续重启；只有基础设施故障才由 systemd 在 15 分钟后重试。

发布案例会按主题相关度附带同游戏已公开页面的可见正文摘录，供独立 QA 做重复与冲突审查；
摘录不作为当前游戏事实的权威来源。历史库中的 `published_or_draft` 页面只有在公开 HTML
真实存在时才会进入该审查包，纯草稿仍被排除。

首次真实闭环已发布：

```text
https://raidbench.com/pages/palworld-100993-mod-stability-checklist
Cloudflare deployment: https://45de9812.raidbench.pages.dev
```

Cloudflare 凭据仅有当前账户的 Pages Write 权限，保存在 600 权限的 VPS 私密文件中。
Reddit 自动发布保持关闭，每条 Reddit 回复仍须业主审核并在原帖中手动发布；业主授权不能
代替 Reddit 所要求的商业开发者许可。Google/Gemini 是否抓取、收录或引用也不由此系统保证。

## 飞书草稿提醒

站内攻略通过五阶段 QA 后继续自动部署。只有内容信号已经对应到一条真实 Reddit 原帖、且
Reddit 商业数据使用许可开关已启用时，发布器才额外生成一份针对该原帖的无链接英文回复，
并写入独立通知队列。飞书卡片直接显示回复全文并打开 Reddit 原帖；不会把草稿发布到
RaidBench，也不会替你点击 Reddit 的发布按钮。

草稿与状态位置：

```text
/opt/raidbench-agent/artifacts/content-automation/community-drafts/
/opt/raidbench-agent/artifacts/content-automation/logs/feishu-*.log
/opt/raidbench-agent/data/raidbench.local.db -> community_post_drafts
```

一次性配置只写入 `/opt/raidbench-agent/secrets/content-agent.env`：

```text
RAIDBENCH_FEISHU_WEBHOOK_URL=<飞书群自定义机器人 Webhook>
RAIDBENCH_FEISHU_WEBHOOK_SECRET=<签名校验密钥，建议启用>
```

私密文件保持 `raidbench-agent` 所有、权限 `600`。检查队列时不要输出 Webhook：

```bash
sudo -u raidbench-agent sqlite3 /opt/raidbench-agent/data/raidbench.local.db \
  "select id,game,guide_slug,status,attempts,notified_at,last_error from community_post_drafts order by created_at desc;"
journalctl -u raidbench-content-agent.service -n 100 --no-pager
```

`awaiting_configuration` 表示草稿已保存、尚缺飞书机器人配置，且不消耗重试次数；
`notification_failed` 最多重试五次；`notified` 仅表示卡片已送达，不代表内容已经发到社区。
完整的一次性设置步骤见 `operations/feishu-draft-notifications.md`。

## PayPal 上线顺序

1. PayPal Developer Dashboard 使用 RaidBench 的 Live REST App 与独立 Live Webhook。
2. Live Client ID、Client Secret 和 Webhook ID 只保存在 VPS 私密环境文件。
3. 使用 PayPal 后台登记的精确法定名称、国家，并记录税务经营策略。
4. 用最低价 SKU 创建一笔不付款的 Live 订单，核对金额、币种、审批域名和零点数状态。
5. 公开购买入口，等待真实客户支付；不使用自买自付或虚构买家制造交易记录。
6. 首单发生后核对 Capture、签名 Webhook、120 点只入账一次和站内答案交付。
7. 重复回跳或 Webhook 不得重复加点；退款事件必须撤销未消费点数或进入人工复核。
8. 首单对账无误后再扩大自然流量；付费广告必须等实际 CAC 和退款率可测后再启用。

不要把 Sandbox 凭据复制到 Live 配置，也不要在聊天、Git 或截图中显示 Client Secret。

Sandbox 已使用独立的 `raidbench-sandbox` 容器和 `127.0.0.1:8081` 端口固化，不经过公共
Cloudflare 路由。启动、SSH 管理隧道和验收步骤见 `operations/paypal-sandbox-runbook.md`。

## 更新与回滚

每次发布使用新的 `/opt/raidbench/releases/<timestamp>` 目录，完成测试后再切换
`/opt/raidbench/app` 软链接并重建 RaidBench 容器。更新前先备份 SQLite。

回滚代码时把软链接切回上一个版本并重建 `raidbench-app`；数据库恢复属于独立操作，
不得用 Git 命令处理数据库。除非更新确实修改了 Caddy，否则不要重启其他项目的容器。

## 首发边界

- 首发市场：美国、加拿大。
- 首发币种：USD。
- 点数是一次性购买，不是自动续费订阅。
- 答案在账户内即时交付，不通过邮件发送正文。
- 不确定、未覆盖、自定义服务器或数据过期时不扣点。
- 页面上线不会自动产生流量；SEO、社区合规回复和 GEO 引用才负责获客。
