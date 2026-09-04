# Support Email Routing

Last updated: 2026-08-30

## Current Setup

`support@raidbench.com` is configured with direct Cloudflare Email Routing.

Incoming mail is forwarded to:

```text
superms123@gmail.com
```

## Cloudflare State Checked

- Domain: `raidbench.com`
- Email Routing status: `ready`
- Destination address: `superms123@gmail.com`
- Destination verification: verified
- Route rule: `support@raidbench.com` forwards directly to `superms123@gmail.com`
- Automatic Feishu alerts for incoming email are disabled.

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

## Notification Disabled

On 2026-08-30, the owner asked to remove the Feishu email-reminder card. The production routing rule was
restored to direct Gmail forwarding. The `raidbench-email-reply-monitor` Worker remains deployed but has no
Email Routing rule and therefore receives no `support@raidbench.com` mail. It must not be reattached unless
the owner explicitly requests email-to-Feishu alerts again.

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
