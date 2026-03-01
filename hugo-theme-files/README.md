# Hugo Theme Files for BlogPusher

Drop these files into your Hugo site repo to make it work with BlogPusher. Designed for the **[hugo-mana-theme](https://github.com/Livour/hugo-mana-theme)** but the gallery layouts will work with any theme that uses standard Hugo single/list templates.

---

## What's in here

```
layouts/
  gallery/
    single.html     — renders a gallery post (image slider + lightbox + body text)
    list.html       — renders the /gallery/ section index
  posts/
    gallery.html    — same as gallery/single.html, alternate path for posts section
  partials/
    toc.html        — table of contents sidebar (shown when post has headings)
static/
  css/
    gallery.css     — slider + lightbox styles (uses theme CSS variables automatically)
  js/
    gallery.js      — slider + lightbox behaviour (drag, swipe, keyboard, focus trap)
```

---

## Setup (5 minutes)

### 1. Copy the files

Copy the `layouts/` and `static/` folders from this directory into the **root of your Hugo site repo** (not inside `themes/`). Your site root layout overrides always take priority over the theme.

```
your-blog/
├── layouts/          ← copy here
├── static/           ← copy here
├── content/
├── themes/
└── hugo.toml
```

### 2. Add the gallery CSS to your `<head>`

The gallery needs one CSS line loaded on every page. Find (or create) a head partial override in your site root:

- **Mana theme**: create `layouts/partials/head.html` by copying `themes/mana/layouts/partials/head.html`, then add this line at the bottom, just before `</head>` or wherever scripts/styles are included:

```html
<link rel="stylesheet" href="/css/gallery.css">
```

- **Other themes**: find whatever partial renders your `<head>` tag and add the same line.

### 3. Add the `images/` directories

BlogPusher pushes cover images to two locations. Create them so git tracks them:

```bash
mkdir -p assets/images static/images
touch assets/images/.gitkeep static/images/.gitkeep
```

Commit the `.gitkeep` files so the directories exist in the repo before your first post.

### 4. (Optional) Add a GitHub Actions workflow

If you don't already have one, copy this into `.github/workflows/hugo.yml` in your repo:

```yaml
name: Deploy Hugo site

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive
      - uses: peaceiris/actions-hugo@v3
        with:
          hugo-version: latest
          extended: true
      - run: hugo --gc --minify
      - uses: actions/upload-pages-artifact@v3
        with:
          path: ./public
      - uses: actions/deploy-pages@v4
        id: deployment
```

Enable GitHub Pages in your repo settings → Pages → Source: **GitHub Actions**.

---

## How posts work

BlogPusher creates posts as [Hugo page bundles](https://gohugo.io/content-management/page-bundles/) with `type: gallery`. The directory layout it creates:

```
content/posts/my-post-title/
├── index.md          ← front matter + body text
├── 1-image.jpg       ← gallery slider image 1
├── 2-image.jpg       ← gallery slider image 2
└── _3-image.jpg      ← hidden from slider (underscore prefix), inline-only
```

Cover image (for the post listing card):
```
assets/images/my-post-title.jpg    ← for Hugo pipes
static/images/my-post-title.jpg    ← for direct URL in front matter
```

The `gallery/single.html` layout picks up all image files in the bundle automatically — no config needed. Images prefixed with `_` are excluded from the slider but still uploaded and referenceable inline.

---

## Compatibility notes

- **Theme**: Built for hugo-mana-theme. The gallery CSS uses CSS variables (`--bg-secondary`, `--accent-primary`, etc.) defined by Mana. If you use a different theme, the gallery will still work but you may need to tweak colours in `static/css/gallery.css`.
- **Hugo version**: Tested with Hugo extended ≥ 0.120. The layouts use no deprecated features.
- **No Hugo image processing**: The layouts intentionally avoid `.Fill`/`.Resize` to prevent file-lock errors on Windows during local development.
