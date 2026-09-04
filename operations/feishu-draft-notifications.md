# RaidBench 飞书发帖草稿提醒

Last updated: 2026-08-10

## 作用

这条流程把 Reddit 拓客变成清晰的人机协作：系统在许可边界内完成问题筛选、证据核对、
英文答复编写、草稿归档和飞书提醒；你只在确认原帖语境与社区规则都合适后，进入 Reddit
手动点击发布。RaidBench 站内攻略仍由独立流程全自动更新。

它不会自动登录、自动评论或批量发帖。这样既保留 Agent 的效率，也避免机械化回复、重复
内容和不合时宜的推广损害账号与品牌。

## 一次性设置

1. 在飞书中新建或选择一个仅供 RaidBench 运营使用的群。
2. 打开群设置，进入“机器人”，添加“自定义机器人”。
3. 建议开启“签名校验”，复制 Webhook 地址与签名密钥。
4. 将两个值仅写入 VPS 的 `/opt/raidbench-agent/secrets/content-agent.env`。
5. 启动一次 `raidbench-content-agent.service`，确认飞书收到测试草稿卡片。

官方参考：

- [使用自定义机器人发送消息卡片](https://open.feishu.cn/document/uAjLw4CM/ukzMukzMukzM/feishu-cards/quick-start/send-message-cards-with-custom-bot)
- [自定义机器人与签名校验](https://open.feishu.cn/document/ukTMukTMukTM/ucTM5YjL3ETO24yNxkjN?lang=zh-CN)

Webhook 与签名密钥相当于机器人的发送凭据，不进入 Git、不出现在网页、不粘贴到公开群，
也不写入普通运行日志。

## 每条草稿的处理方式

VPS 每天 19:25（中国时间）通过 Codex 实时网页搜索寻找一条近 7 天、问题明确且从未进入
队列的 `r/playrust` 新帖。它不使用 Reddit Data API、不批量抓取，也不会登录或公开发布。
20:00 的飞书任务只选择当天新生成且从未提醒过的草稿；当天没有合格新帖时会明确报告为空，
不会轮换或重复发送昨日库存。

飞书卡片直接显示真实 Reddit 原帖标题、完整无链接英文回复、当前运营节奏，以及唯一按钮
“打开 Reddit 原帖”。草稿只保存在 VPS 私有目录和飞书私有群，不生成 RaidBench 网页。

Reddit 没有供外部网站创建“预填评论草稿链接”的通用入口，因此最后一步是：在飞书核对并
复制英文回复，点击按钮打开对应原帖，粘贴后由你点击发布。没有精确原帖 URL、只有 Reddit
搜索页或泛主题时，系统不会创建待发布草稿，也不会发送提醒。

发布前只做四项检查：问题是否完全匹配、游戏版本是否匹配、社区是否允许该类回复、同一
答案是否已经发过。默认直接发布无链接版本；只有规则明确允许时才考虑加入网站链接，并
主动披露与 RaidBench 的关系。

## 状态与重试

```text
pending_notification    等待发送
awaiting_configuration  草稿已保存，但尚未配置飞书，不计失败次数
notification_failed     临时失败，最多自动尝试五次
notified                飞书已接收卡片，仍需人工发布
```

通知失败不会阻断站内攻略上线。系统保留草稿和错误摘要，下一次内容定时任务会继续处理符合
重试条件的项目。
