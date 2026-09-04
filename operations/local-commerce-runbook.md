# RaidBench 本地实战闭环

## 当前结论

首发市场为美国和加拿大，结账统一使用 USD。欧洲 VAT、多币种展示和欧洲营销暂不进入首发关键路径。

本地系统已经采用混合交付模式，但首发只销售能够通过结构化 QA 的 Rust 产品：

| 产品 | 用户动作 | 目标速度 | 扣点 | 交付位置 |
|---|---|---:|---:|---|
| Verified Rust Raid Cost Answer | 选择目标、数量和爆破方式 | 5 秒内 | 12 | 客户账户内直接显示 |
| Verified Rust Raid Plan | 组合最多 12 层路线并设置缓冲 | 10 秒内 | 120 | 客户账户内直接显示 |
| 自定义服或证据过期请求 | 保存请求并等待新证据 | 不承诺 | 0 | 客户账户显示暂缓原因 |

邮件不承担主要交付。未来只用于付款回执、答案完成通知、密码或安全通知。

## 为什么不首发开放任意提问

任意自由文本问题需要实时检索、版本判断、证据归因和独立复核。如果在这条链路未完成前先收款，最容易产生错误答案、退款和口碑损失。

因此首发边界是：

1. 能由已验证数据和确定性计算解决的问题，付款后立即交付。
2. 数据超过 72 小时、用户选择自定义服、或输入超出支持范围时，系统保存请求但不扣点。
3. 未来接入研究 Agent 后，自由文本问题才进入 2 至 10 分钟目标队列；只有 QA 通过时才完成扣点。

## 本地数据库

正式交易数据使用 `local/raidbench.local.db`。核心表包括：

- `customers`：客户账户和地区。
- `sessions`：哈希后的登录会话。
- `orders`：PayPal 或本地 sandbox 订单。
- `credit_ledger`：不可变的购点、扣点和恢复点数记录。
- `questions`：请求、状态、输入和最终答案。
- `question_events`：收件、证据检查、复算和发布轨迹。
- `answer_evidence`：答案对应的来源与支持范围。
- `delivery_records`：站内交付记录。

## 本地启动

固定端口为 `4289`，不得使用 `4173`。

```bash
PYTHONDONTWRITEBYTECODE=1 python3 backend/server.py --host 127.0.0.1 --port 4289 --mode demo
```

打开：

```text
http://127.0.0.1:4289/customer.html
```

本地 demo 的“Simulate PayPal”会写入真实订单和点数账本，但不会连接 PayPal 或产生真实资金。`production` 模式没有这个接口。

## PayPal 接入边界

后端已实现 PayPal OAuth、创建订单、跳转审批、回跳后 capture、金额核对、幂等入账和点数发放。正式开启需要：

1. PayPal 商户账户审核通过。
2. 创建 sandbox 应用并完成一笔端到端测试。
3. 完成一次 sandbox 退款和账务核对演练。
4. 在 VPS `.env` 放入 live Client ID 和 Client Secret。
5. 将 `PAYPAL_ENV=live`、`RAIDBENCH_CHECKOUT_ENABLED=1` 后重启服务。

未设置凭据或总开关为 0 时，公开结账保持关闭。
