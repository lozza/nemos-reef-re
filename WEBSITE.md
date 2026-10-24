# Project website

[All guides](README.md) · [Open the website](https://nemos-reef-revival.pages.dev/)

The public homepage is a static website deployed from the `main` branch
through Cloudflare Pages.

## Edit the website

- `public/index.html`: homepage content, guide links and community invite.
- `public/styles.css`: layout, typography, responsive rules and wave buttons.
- `public/reef-hero-hd.jpg`: the 2048 × 768 desktop hero artwork, exported at high JPEG quality.
- `public/reef-world.jpg`: the tall illustrated reef used behind the page and community panel.
- `public/discord-mascot.png`: the existing Discord artwork and browser-tab icon.
- `public/logo.png`: the approved white and orange project wordmark used in the header and footer.
- `public/server-illustration.svg`, `public/pc-illustration.svg` and
  `public/phone-illustration.svg`: setup illustrations.
- `public/fonts/fredoka.woff2`: locally hosted display font. Its SIL Open
  Font License is included in `public/fonts/OFL.txt`.

The design follows the approved mockup based on the original game screenshots:
blue popup frames, parchment panels, cyan setup cards and glossy green buttons.
The reef artwork was generated separately; text, controls and responsive layouts
are real HTML and CSS. The community panel uses the existing Discord mascot.

Only the `public` folder is published as the website. The homepage links to
the setup guides on GitHub; edit those Markdown files to update the guides.

Wave buttons also respond to keyboard focus. Waves and hover movement are
disabled when reduced motion is requested.

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

## Discord invite

The website uses [this community invite](https://discord.gg/mseaKJb5G).
It never expires, has no use limit and sends new members to the welcome channel.

To replace it, update the four Discord links in `public/index.html`.
Existing invites can be managed in Discord under **Server Settings → Invites**.
