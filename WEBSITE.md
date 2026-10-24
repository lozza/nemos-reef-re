# Project website

[All guides](README.md) · [Open the website](https://nemos-reef-revival.pages.dev/)

The public homepage is a static website deployed from the `main` branch
through Cloudflare Pages.

## Edit the website

- `public/index.html`: homepage text, illustration and guide links.
- `public/styles.css`: colours, spacing and responsive layouts.
- `public/favicon.svg`: browser-tab icon.

Only the `public` folder is published as the website. The homepage links to
the setup guides on GitHub; edit those Markdown files to update the guides.

## Cloudflare Pages build settings

For the Pages project named `nemos-reef-revival`, use:

| Setting | Value |
|---|---|
| Production branch | `main` |
| Framework preset | None |
| Root directory | Repository root |
| Build command | Leave empty; no build step is needed |
| Build output directory | `public` |

Commits to `main` trigger the connected deployment. Check the Cloudflare
Pages build result on the commit before sharing a new version.

The existing `wrangler.jsonc` is for the earlier Workers deployment.
The Pages website uses the dashboard settings above.

## Local preview

From the repository root:

```sh
python -m http.server 8000 --directory public
```

Open `http://localhost:8000`. Stop the preview with Ctrl+C.
