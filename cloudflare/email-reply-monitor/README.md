# RaidBench Email Reply Monitor

Status: active selective partner-reply monitoring since 2026-09-07.

This Cloudflare Email Worker preserves forwarding from `support@raidbench.com` to the owner's verified Gmail.
It sends a signed Feishu card only when a message matches a known contacted partner, a known non-shared partner
domain, or the required `RaidBench collaboration:` outreach subject marker. Attachments are not copied to Feishu.

Automatic senders, bounces, bulk/list mail, RaidBench's own notification domains, password-reset messages,
Reddit draft notifications, and ordinary support mail are forwarded to Gmail without a Feishu alert.

Secrets are configured only in Cloudflare:

- `FORWARD_TO_EMAIL`
- `FEISHU_WEBHOOK_URL`
- `FEISHU_WEBHOOK_SECRET`

The active `support@raidbench.com` Email Routing rule points to this Worker. The Worker calls
`message.forward(FORWARD_TO_EMAIL)` before scheduling the Feishu notification, so a Feishu outage does not
block Gmail delivery.

The Worker writes only a timestamp, forwarding flag, notification status, and truncated SHA-256 hashes to the
existing analytics D1 database. Status is `accepted`, `failed`, or `skipped_non_partner`; it does not store sender
addresses, subjects, message bodies, or attachments.

The 2026-09-07 production routing test used RaidBench's own notification sender. D1 recorded
`forwarded=1` and `feishu_status=skipped_non_partner`, confirming that Gmail forwarding continued while the
non-partner message did not generate a Feishu card. A real partner reply remains the positive production test;
successful webhook calls must be described as “接口已接收，送达未验证”.
