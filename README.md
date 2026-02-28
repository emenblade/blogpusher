# BlogPusher

A self-hosted Flask server that publishes blog posts to GitHub Pages via the GitHub Contents API. No git CLI required on the server.

**Workflow:** Phone → Claude → paste body → fill form → Publish → GitHub Actions builds Hugo site (~60s)

## Quick Start

### 1. Get the image

```bash
docker pull ghcr.io/emenblade/blogpusher:latest
```

### 2. Create your config

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`:

```yaml
github_token: ghp_your_token_here   # PAT with repo contents read/write
github_repo: youruser/your-blog     # case-sensitive
github_branch: main
site_url: https://your-blog.com
```

### 3. Start it

```bash
docker compose up -d
```

Health check: `curl http://localhost:5000/health`

Open `http://localhost:5000` to publish posts.

---

## Running a Second Instance (Second Blog)

```bash
cp -r blogpusher/ blogpusher-travel/
cd blogpusher-travel/
```

In `docker-compose.yml`, change:
- `container_name: blogpusher-travel`
- `ports: "5001:5000"`

Drop in a new `config.yaml` pointing at the second blog repo, then `docker compose up -d`.

---

## Configuration

| Key | Env var fallback | Description |
|---|---|---|
| `github_token` | `GITHUB_TOKEN` | GitHub PAT with contents R/W |
| `github_repo` | `GITHUB_REPO` | `owner/repo` (case-sensitive) |
| `github_branch` | `GITHUB_BRANCH` | Default: `main` |
| `site_url` | `SITE_URL` | Used to build the post URL in the success response |

Config file path defaults to `/app/config.yaml` inside the container. Override with `CONFIG_FILE` env var.

---

## Hugo Blog Requirements

The server assumes the target repo is a Hugo site with:
- `content/posts/<slug>/index.md` — post content
- `assets/images/<slug>.jpg` — cover (for Hugo pipes)
- `static/images/<slug>.jpg` — cover (for direct URL in front matter)

Posts use `type: gallery` front matter for image slider support.
