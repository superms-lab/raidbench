# RaidBench Deployment Notes

## Fastest Deployment

Use Cloudflare Pages or GitHub Pages as a static site.

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

## Before Public Launch

Current expected GitHub Pages URL:

```text
https://raidbench.com/
```

Then update:

- `robots.txt`
- `sitemap.xml`
- Open Graph URL metadata if added later

Current GitHub Pages deployment:

```text
https://raidbench.com/
```

Repository:

```text
https://github.com/supermszhanghao-eng/raidbench
```

## Stage 2 Checklist

- Deploy static site. Done on GitHub Pages.
- Confirm `/`, `/robots.txt`, and `/sitemap.xml` are reachable. Done.
- Add the site to Google Search Console.
- Submit sitemap.
- Add analytics.
- Record the public URL in `RUST_FAST_LAUNCH_WORKFLOW.md`.
