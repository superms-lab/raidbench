# RaidBench Account Recovery Email

Last updated: 2026-08-02

## Current State

The application-side account recovery flow is complete and covered by automated tests:

- the request response does not reveal whether an email is registered;
- requests are rate-limited by a one-way email identifier hash;
- reset tokens expire after 30 minutes and are stored only as SHA-256 hashes;
- reset links carry the token in a URL fragment so it is not sent in HTTP access logs;
- successful resets invalidate every existing account session;
- a reset token can be used only once;
- email sending runs through a bounded background executor;
- failed delivery invalidates the unsent token;
- the public UI shows the support address when automatic delivery is disabled.

The application supports both Resend and SMTP2GO. SMTP2GO is the active production path because its
free plan can verify multiple sender domains without changing or deleting the existing
`notify.leadauditlab.com` Resend domain. `notify.raidbench.com` is verified, the production API key is
restricted to `/email/send`, and automatic account-recovery delivery is active. The previous RaidBench
Resend key remains on the VPS as an unused fallback and was not revoked.

## SMTP2GO Production Activation

Use `notify.raidbench.com` as a sending-only subdomain. Keep inbound mail for
`support@raidbench.com` on the existing Cloudflare Email Routing configuration.

Completed on 2026-08-02:

1. Owner phone and SMS verification completed.
2. `notify.raidbench.com` added and verified as the SMTP2GO sender domain.
3. The generated return-path, DKIM, and tracking CNAME records were added to Cloudflare as DNS-only
   records without changing inbound routing for `support@raidbench.com`.
4. SMTP2GO reports the sender domain as verified and the tracking-domain SSL certificate as enabled.
5. A production API key was created with only `/email/send`; open tracking, click tracking, the
   unsubscribe footer, bounce notifications, and audit BCC remain disabled.
6. These values were added only to `/opt/raidbench/secrets/runtime.env`:

```text
RAIDBENCH_EMAIL_PROVIDER=smtp2go
SMTP2GO_API_KEY=<secret key restricted to /email/send>
RAIDBENCH_EMAIL_FROM=RaidBench <account@notify.raidbench.com>
```

7. Only the `raidbench-app` container was rebuilt and recreated from release
   `/opt/raidbench/releases/20260802T141754Z`. `raidbench-sandbox` and LeadAuditLab remained healthy.
8. The public `/api/config` endpoint reports both values below:

```text
passwordResetEnabled=true
liveReadiness.passwordResetEmailReady=true
```

9. A production account for `support@raidbench.com` requested a real reset email. SMTP2GO reported
   `Delivered`, Gmail received the message, and the message button opened the production password form.
   No new password was submitted during automation. The test token was invalidated afterward; token
   consumption, password replacement, old-session invalidation, and single-use behavior remain covered
   by the automated backend tests.

Current checkpoint: production delivery is active and publicly reports
`liveReadiness.passwordResetEmailReady=true`. The owner completed the SMTP2GO login-password rotation
on 2026-08-02. A read-only follow-up confirmed the account remained signed in, the production API key
remained present and Online, and `notify.raidbench.com` remained Verified and Enabled.

Never place an email provider key in Git, browser JavaScript, Cloudflare Pages variables, screenshots, or
operations reports.

## Runtime Variables

| Variable | Purpose | Public |
| --- | --- | --- |
| `RAIDBENCH_EMAIL_PROVIDER` | Selects `smtp2go` or the legacy `resend` adapter | Yes |
| `SMTP2GO_API_KEY` | Authorizes only the SMTP2GO `/email/send` endpoint | No |
| `RESEND_API_KEY` | Optional legacy Resend credential; currently unused by RaidBench | No |
| `RAIDBENCH_EMAIL_FROM` | Verified sender identity | Yes |
| `PUBLIC_BASE_URL` | Builds the account recovery URL | Yes |
| `RAIDBENCH_SUPPORT_EMAIL` | Reply-to and manual recovery address | Yes |

## Failure Behavior

When the provider is not configured, the API returns `password_reset_unavailable` and the page directs
the player to `support@raidbench.com`. When a configured provider has a temporary delivery failure, the
public response remains generic, the token is invalidated, and the provider failure is written to the
server log without the account email, API key, or reset token.
