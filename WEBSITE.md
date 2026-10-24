# Project website

[All guides](README.md)

The public homepage is a static website deployed from the `main` branch
through the existing Cloudflare Workers GitHub connection.

## Edit the website

- `public/index.html`: homepage text, illustration and guide links.
- `public/styles.css`: colours, spacing and responsive layouts.
- `public/favicon.svg`: browser-tab icon.
- `wrangler.jsonc`: Cloudflare deployment settings.

Only the `public` folder is published as the website. The homepage links to
the setup guides on GitHub; edit those Markdown files to update the guides.

## Cloudflare build settings

For the Worker named `nemos-reef-revival`, use:

| Setting | Value |
|---|---|
| Production branch | `main` |
| Root directory | Repository root (leave unchanged) |
| Build command | Leave empty; no build step is needed |
| Deploy command | `npx wrangler deploy` |

The Wrangler configuration points to `./public`. Commits to `main` trigger
the connected deployment. Check the Cloudflare build result on the commit
before sharing a new version.

For a local preview from the repository root:

```sh
python -m http.server 8000 --directory public
```

Open `http://localhost:8000`. Stop the preview with Ctrl+C.
