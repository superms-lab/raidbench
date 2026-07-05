# RaidBench MVP

Fast static MVP for validating the Rust game-guide/tool website route.

## What It Tests

- Whether a tool-first Rust guide site feels useful.
- Whether raid cost and upkeep searches can become SEO pages.
- Whether a simple calculator can justify later paid packs or credits.

## Files

- `index.html` - static app shell and SEO content
- `styles.css` - visual system and responsive layout
- `app.js` - calculator logic
- `assets/survival-base.png` - generated original artwork, not official Rust art
- `assets/concept-ui.png` - generated concept reference

## Local Preview

Open `index.html` directly in a browser, or serve the directory with any static server.

Fixed local preview port:

```text
4289
```

Start command from the repository root:

```bash
PORT=$(awk -F= '/^PORT=/{print $2}' .env)
python3 -m http.server "$PORT" --directory .
```

## Deployment

This can deploy as-is to Cloudflare Pages, GitHub Pages, Netlify, or Vercel static hosting.

See `DEPLOY.md`.

## Legal Note

RaidBench is an unofficial fan-made planning tool and is not affiliated with or endorsed by Facepunch Studios. All trademarks and game names belong to their respective owners.
