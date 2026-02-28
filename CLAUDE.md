# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## What This Project Does

BlogPusher is a Flask server (Docker container) that bridges a mobile publishing workflow:

**Phone → Claude → JSON → HTTP Shortcuts → /publish (NAS:5000) → GitHub API → GitHub Actions → Hugo Build → GitHub Pages (~60s)**

The user drafts blog posts with Claude on mobile, copies the JSON payload, and sends it via the HTTP Shortcuts Android app. The server pushes all files directly to GitHub via API (no git CLI); GitHub Actions builds and deploys the Hugo site automatically.

## Repo Structure

```
blogpusher/
├── server.py                          # Flask app (~726 lines) — all logic here
├── requirements.txt                   # flask, requests, gunicorn, pyyaml
├── Dockerfile                         # python:3.12-slim, exposes 5000
├── docker-compose.yml                 # pulls ghcr.io/emenblade/blogpusher:latest
├── config.example.yaml                # template — copy to config.yaml and fill in
├── .gitignore                         # excludes config.yaml, .env, __pycache__
├── .github/
│   └── workflows/
│       └── docker-publish.yml         # builds + pushes to GHCR on push to main
└── CLAUDE.md
```

## Configuration

Copy `config.example.yaml` → `config.yaml` (gitignored) and fill in:

```yaml
github_token: ghp_...               # PAT with contents R/W
github_repo: emenblade/Blog         # target repo (case-sensitive)
github_branch: main
site_url: https://blog.emen.win
```

The server also accepts env vars as a fallback (for backwards compatibility with `.env`-based deployments).

## Running Locally (dev)

```bash
# With config.yaml in repo root:
CONFIG_FILE=./config.yaml python server.py

# Or via Docker:
docker compose up -d
docker compose logs -f
docker compose up -d --build    # rebuild after code changes
```

**Health check:**
```bash
curl http://localhost:5000/health
# {"configured": true, "repo": "emenblade/Blog", "status": "ok"}
```

## Deploying (NAS / Unraid)

1. Pull image: `docker pull ghcr.io/emenblade/blogpusher:latest`
2. Copy `config.example.yaml` → `config.yaml`, fill in values
3. `docker compose up -d`

**Second instance (second blog):**
- Copy the folder, change `container_name` and left port in `docker-compose.yml` (e.g. `5001:5000`)
- Drop in a new `config.yaml` pointing at the other repo

## GHCR Publishing

Pushing to `main` triggers `.github/workflows/docker-publish.yml`, which:
- Builds the image
- Pushes `ghcr.io/emenblade/blogpusher:latest` and `ghcr.io/emenblade/blogpusher:<sha>`

No secrets to configure — uses the built-in `GITHUB_TOKEN`.

## Architecture

### server.py

All server logic in one file. Routes:

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Web form for publishing posts (HTML + embedded JS) |
| `/health` | GET | Health check |
| `/manage` | GET | List/delete published posts |
| `/api/posts` | GET | JSON list of posts from GitHub |
| `/publish` | POST | Core endpoint: receive JSON payload, push to GitHub |
| `/delete` | POST | Delete a post and its images from GitHub |

Key internal functions:
- `gh_headers()` — GitHub API auth headers from config
- `get_sha(path)` — get existing file SHA (required for GitHub API updates)
- `push_file(path, data, message, is_binary)` — upsert file via GitHub Contents API
- `slugify(title)` — URL-safe slug from title

The `/publish` endpoint:
1. Accepts JSON with `title`, `body`, `description`, `tags`, `date`, and base64-encoded images
2. Slugifies the title
3. Pushes cover image to both `assets/images/slug.jpg` and `static/images/slug.jpg`
4. Pushes gallery images to `content/posts/slug/1-image.jpg`, `2-image.jpg`, etc.
5. Generates front matter YAML and pushes `content/posts/slug/index.md`

## Blog Writing Voice

Alex's voice: casual, dry humor, first person, short punchy sentences. No corporate language. Draft first, get approval, then commit/publish.
