# RaidBench Deployment Notes

## Current Deployment

Production is deployed through Cloudflare Pages.

Current production URL:

```text
https://raidbench.com/
```

Current Cloudflare Pages project:

```text
raidbench
```

Latest manual deploy command:

```bash
npx wrangler pages deploy /tmp/raidbench-pages --project-name raidbench --branch main
```

Create `/tmp/raidbench-pages` from the public static files only. Do not upload the whole repository
because it contains operations docs, scripts, source snapshots, and monetization drafts that are not
needed on the public site.

Current public-file copy list:

```bash
rm -rf /tmp/raidbench-pages
mkdir -p /tmp/raidbench-pages
cp -R assets pages /tmp/raidbench-pages/
cp _headers _redirects favicon.svg site.webmanifest index.html poe2.html palworld.html premium.html privacy.html terms.html refund-policy.html styles.css app.js config.js analytics.js robots.txt sitemap.xml /tmp/raidbench-pages/
```

## Static Site Settings

Build command:

```text
none
```

Output directory:

```text
/
```

If deploying from this repository root, set the project/root directory to:

```text
rust-raidbench
```

## Local Port

This project uses:

```text
PORT=4289
```

Do not use port `4173` for this project.

Before public launch updates:

- `robots.txt`
- `sitemap.xml`
- Open Graph URL metadata if added later

Repository:

```text
https://github.com/superms-lab/raidbench
```

## Stage 2 Checklist

- Deploy static site. Done on Cloudflare Pages.
- Confirm `/`, `/robots.txt`, and `/sitemap.xml` are reachable. Done.
- Add the site to Google Search Console.
- Submit sitemap.
- Add analytics.
- Record the public URL in `RUST_FAST_LAUNCH_WORKFLOW.md`.
