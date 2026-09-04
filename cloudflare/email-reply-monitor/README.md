# RaidBench Email Reply Monitor

Status: disabled by owner request on 2026-08-30. No Email Routing rule currently targets this Worker.

This Cloudflare Email Worker preserves the existing `support@raidbench.com` forwarding route and sends a
signed Feishu card when new mail arrives. The card includes the sender, subject, and a bounded plain-text
excerpt. Attachments are not copied to Feishu.

Secrets are configured only in Cloudflare:

- `FORWARD_TO_EMAIL`
- `FEISHU_WEBHOOK_URL`
- `FEISHU_WEBHOOK_SECRET`

The `support@raidbench.com` Email Routing rule points to this Worker. The Worker calls
`message.forward(FORWARD_TO_EMAIL)` before scheduling the Feishu notification, so a Feishu outage does not
block Gmail delivery.

The Worker writes only a timestamp, delivery flags, and truncated SHA-256 hashes to the existing analytics
D1 database. It does not store sender addresses, subjects, message bodies, or attachments.
