# Support Email Routing

Last updated: 2026-09-07

## Current Setup

`support@raidbench.com` is routed through the `raidbench-email-reply-monitor` Cloudflare Email Worker. The
Worker forwards every message to the existing verified Gmail destination, then independently decides whether
the message is a partnership reply that merits a Feishu alert.

Incoming mail is forwarded to:

```text
superms123@gmail.com
```

## Cloudflare State Checked

- Domain: `raidbench.com`
- Email Routing status: `ready`
- Destination address: `superms123@gmail.com`
- Destination verification: verified
- Route rule: `support@raidbench.com` sends to `raidbench-email-reply-monitor`
- Worker forwarding destination: the existing verified owner Gmail
- Automatic Feishu alerts: enabled only for verified partnership replies

## Reply Notification Verification

Completed on 2026-08-29 China time:

1. A temporary Email Routing address was connected to the Worker.
2. An authorized test message was accepted by SMTP2GO.
3. D1 recorded `forwarded=1` and `feishu_status=accepted`.
4. The production `support@raidbench.com` rule was changed from direct forwarding to the Worker.
5. A second authorized test message through the production address also recorded `forwarded=1` and
   `feishu_status=accepted`.
6. The temporary test rule was deleted.

The D1 audit table stores only timestamps, delivery flags, and truncated SHA-256 hashes. It does not store
sender addresses, subjects, bodies, or attachments. Feishu alerts contain a bounded excerpt and a Gmail
search button; the original message remains in Gmail.

## Selective Notification

The broad “all new mail” Feishu alert was disabled on 2026-08-30 because it surfaced RaidBench's own system
notifications. On 2026-09-07 the owner explicitly requested continuous partnership-reply monitoring, so the
Worker was reattached with a fail-closed filter.

An alert is allowed only when the sender is a previously contacted partner, belongs to a previously contacted
non-shared partner domain, or replies to a future subject beginning `RaidBench collaboration:`. RaidBench-owned
senders, no-reply addresses, bounces, bulk/list messages, password-reset mail, Reddit notifications, and ordinary
support mail remain silent in Feishu while still reaching Gmail.

Production verification sent one internal configuration message through the live routing rule. D1 recorded
`forwarded=1` and `feishu_status=skipped_non_partner`. The Worker keeps no readable sender, subject, body, or
attachment in D1.

## DNS Records Checked

Public DNS resolves the Cloudflare Email Routing records:

- MX: `route1.mx.cloudflare.net`
- MX: `route2.mx.cloudflare.net`
- MX: `route3.mx.cloudflare.net`
- SPF TXT: `v=spf1 include:_spf.mx.cloudflare.net ~all`
- DKIM TXT: `cf2024-1._domainkey.raidbench.com`

## Test Notes

Local direct SMTP delivery from this Mac was rejected by Cloudflare because the residential sender IP
failed reverse lookup. That is a sender-network restriction, not a missing route rule.

Use a normal external inbox such as Gmail, Outlook, or a phone mail app to send a real test message to
`support@raidbench.com`, then confirm it arrives in `superms123@gmail.com`.

## Transactional Account Email

Cloudflare Email Routing handles incoming forwarding only. The RaidBench application now has a tested
SMTP2GO adapter for automatic password recovery. `notify.raidbench.com` is verified, a production key
restricted to `/email/send` is stored only on the VPS, and automatic delivery is active.

On 2026-08-02, a real reset email sent to `support@raidbench.com` was reported as `Delivered` by
SMTP2GO, forwarded by Cloudflare Email Routing, and received in `superms123@gmail.com`. The customer
page now exposes the automatic reset flow and retains `support@raidbench.com` as the manual fallback
and Reply-To address. See `operations/account-recovery-email.md` for the activation record.

## Future Options

- Keep the current forwarding setup for early validation.
- Move to Google Workspace, Zoho Mail, or another mailbox provider if replies should be sent directly
  as `support@raidbench.com`.
- Create aliases such as `billing@raidbench.com` after payments are enabled.
