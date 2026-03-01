#!/usr/bin/env python3
"""
BlogPusher - NAS relay server
"""

import os
import re
import base64
import requests
from datetime import datetime
from flask import Flask, request, jsonify, Response

app = Flask(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
import yaml

_config = {}
config_path = os.environ.get("CONFIG_FILE", "/app/config.yaml")
if os.path.exists(config_path):
    with open(config_path) as f:
        _config = yaml.safe_load(f) or {}

def _cfg(key, env_key, default=""):
    return _config.get(key) or os.environ.get(env_key, default)

GITHUB_TOKEN  = _cfg("github_token",  "GITHUB_TOKEN")
GITHUB_REPO   = _cfg("github_repo",   "GITHUB_REPO")
GITHUB_BRANCH = _cfg("github_branch", "GITHUB_BRANCH", "main")
SITE_URL      = _cfg("site_url",      "SITE_URL")
CONFIGURED    = bool(GITHUB_TOKEN and GITHUB_REPO)

GITHUB_API    = "https://api.github.com"

# ── Hugo compat setup ──────────────────────────────────────────────────────────
THEME_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hugo-theme-files")

SETUP_FILES = [
    "layouts/gallery/single.html",
    "layouts/gallery/list.html",
    "layouts/posts/gallery.html",
    "layouts/partials/toc.html",
    "static/css/gallery.css",
    "static/js/gallery.js",
]

SETUP_GITKEEPS = [
    "assets/images/.gitkeep",
    "static/images/.gitkeep",
]

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max upload

_UNCONFIGURED_PASSTHROUGH = {"/health", "/setup-blog", "/api/verify", "/api/setup"}

@app.before_request
def require_config():
    if CONFIGURED:
        return
    if request.path in _UNCONFIGURED_PASSTHROUGH or request.path.startswith("/static"):
        return
    config_path = os.environ.get("CONFIG_FILE", "/app/config.yaml")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
  <title>BlogPusher — Setup required</title>
  <style>
    body{{background:#0f0f0f;color:#e2e2e2;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
      padding:40px 20px;max-width:560px;margin:0 auto;}}
    h1{{color:#a78bfa;font-size:1.3rem;margin-bottom:6px;}}
    p{{color:#777;font-size:0.88rem;line-height:1.7;margin-top:12px;}}
    code{{font-family:"Menlo","Courier New",monospace;font-size:0.8rem;background:#1a1a1a;
      color:#c4b5fd;padding:1px 5px;border-radius:4px;}}
    pre{{background:#141414;border:1px solid #2a2a2a;border-radius:10px;padding:14px 16px;
      margin-top:10px;overflow-x:auto;}}
    pre code{{background:none;padding:0;color:#c4b5fd;font-size:0.82rem;line-height:1.7;}}
    .path{{color:#fbbf24;}}
  </style>
</head>
<body>
  <h1>BlogPusher is not configured</h1>
  <p><strong>Unraid / Docker:</strong> set these environment variables in your container config:</p>
  <pre><code>GITHUB_TOKEN   ghp_your_token_here
GITHUB_REPO    youruser/your-blog-repo
SITE_URL       https://your-blog-url.com
GITHUB_BRANCH  main</code></pre>
  <p>Then restart the container.</p>
  <p style="margin-top:16px"><strong>Docker Compose:</strong> create <code class="path">{config_path}</code>:</p>
  <pre><code>github_token: ghp_your_token_here
github_repo: youruser/your-blog-repo
github_branch: main
site_url: https://your-blog-url.com</code></pre>
  <p>Need a token? Create a fine-grained PAT at <code>github.com/settings/tokens</code>
  with <strong>Contents read/write</strong> on your blog repo.</p>
</body>
</html>""", 200, {{"Content-Type": "text/html; charset=utf-8"}}


# ── GitHub helpers ─────────────────────────────────────────────────────────────
def gh_headers():
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }

def get_sha(path):
    r = requests.get(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}",
        headers=gh_headers()
    )
    return r.json().get("sha") if r.status_code == 200 else None

def push_file(path, data, message, is_binary=False):
    encoded = base64.b64encode(data if is_binary else data.encode()).decode()
    payload = {"message": message, "content": encoded, "branch": GITHUB_BRANCH}
    sha = get_sha(path)
    if sha:
        payload["sha"] = sha
    r = requests.put(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{path}",
        headers=gh_headers(),
        json=payload,
    )
    ok = r.status_code in (200, 201)
    return ok, r.json().get("message", "") if not ok else ""


# ── Utilities ──────────────────────────────────────────────────────────────────
def slugify(title):
    s = title.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "repo": GITHUB_REPO, "configured": CONFIGURED, "site_url": SITE_URL})


@app.route("/", methods=["GET"])
def form():
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BlogPusher</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f0f0f; color: #e2e2e2;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 20px 16px 48px; max-width: 600px; margin: 0 auto;
    }
    .top-bar { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; }
    h1 { font-size: 1.4rem; font-weight: 700; color: #a78bfa; }
    .nav-link { font-size: 0.8rem; color: #7c3aed; text-decoration: none; }
    .nav-link:hover { color: #a78bfa; }
    .subtitle { font-size: 0.8rem; color: #555; margin-bottom: 24px; }
    label {
      display: block; font-size: 0.75rem; font-weight: 600; color: #888;
      text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; margin-top: 18px;
    }
    input[type="text"], input[type="date"], textarea {
      width: 100%; background: #1a1a1a; color: #e2e2e2;
      border: 1px solid #2a2a2a; border-radius: 10px; padding: 12px 14px;
      font-size: 0.95rem; font-family: inherit; outline: none;
      transition: border-color 0.15s; -webkit-appearance: none;
    }
    input[type="text"]:focus, input[type="date"]:focus, textarea:focus { border-color: #7c3aed; }
    textarea {
      height: 220px; resize: vertical;
      font-family: "Menlo", "Courier New", monospace; font-size: 0.85rem; line-height: 1.5;
    }
    .upload-area {
      border: 2px dashed #2a2a2a; border-radius: 10px; padding: 24px 16px;
      text-align: center; cursor: pointer; transition: border-color 0.15s, background 0.15s;
      position: relative;
    }
    .upload-area:hover, .upload-area.dragover { border-color: #7c3aed; background: #1a1430; }
    .upload-area input[type="file"] {
      position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; cursor: pointer;
    }
    .upload-icon { font-size: 2rem; margin-bottom: 8px; }
    .upload-text { font-size: 0.9rem; color: #666; }
    .upload-text strong { color: #a78bfa; }
    #preview-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 12px; }
    .preview-item {
      position: relative; aspect-ratio: 1; border-radius: 8px; overflow: hidden;
      background: #1a1a1a; border: 1px solid transparent; transition: border-color 0.15s;
    }
    .preview-item img { width: 100%; height: 100%; object-fit: cover; transition: opacity 0.15s; }
    .preview-item.slider-hidden { border-color: #ef444466; }
    .preview-item.slider-hidden img { opacity: 0.4; }
    .preview-item .badge {
      position: absolute; top: 4px; left: 4px;
      background: rgba(124,58,237,0.9); color: white;
      font-size: 0.65rem; font-weight: 700; padding: 2px 6px; border-radius: 4px;
      pointer-events: none;
    }
    .preview-item .remove-btn {
      position: absolute; top: 4px; right: 4px;
      background: rgba(0,0,0,0.7); color: white; border: none; border-radius: 50%;
      width: 22px; height: 22px; font-size: 0.8rem; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
    }
    .preview-item .eye-btn {
      position: absolute; bottom: 4px; left: 4px;
      background: rgba(0,0,0,0.6); color: #999; border: none; border-radius: 4px;
      width: 22px; height: 22px; padding: 3px; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: color 0.15s;
    }
    .preview-item.slider-hidden .eye-btn { color: #ef4444; }
    .preview-item .copy-md-btn {
      position: absolute; bottom: 4px; right: 4px;
      background: rgba(0,0,0,0.6); color: #a78bfa; border: none; border-radius: 4px;
      width: 22px; height: 22px; padding: 3px; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: color 0.15s;
    }
    .check-row {
      display: flex; align-items: center; gap: 10px; cursor: pointer; margin-top: 14px;
    }
    .check-row input[type="checkbox"] {
      width: 18px; height: 18px; accent-color: #7c3aed; cursor: pointer; flex-shrink: 0;
    }
    .check-row span { font-size: 0.9rem; color: #aaa; }
    .hint { font-size: 0.75rem; color: #555; margin-top: 5px; }
    #publish-btn {
      width: 100%; margin-top: 28px; padding: 18px; background: #7c3aed; color: white;
      border: none; border-radius: 12px; font-size: 1.05rem; font-weight: 700;
      cursor: pointer; transition: background 0.15s, transform 0.1s;
    }
    #publish-btn:active { background: #5b21b6; transform: scale(0.98); }
    #publish-btn:disabled { background: #3a1f70; color: #888; cursor: not-allowed; }
    #status {
      margin-top: 16px; padding: 14px; border-radius: 10px;
      font-size: 0.9rem; display: none; line-height: 1.6;
    }
    .status-ok      { background: #0d2e1a; color: #4ade80; border: 1px solid #16532d; }
    .status-err     { background: #2e0d0d; color: #f87171; border: 1px solid #7f1d1d; }
    .status-loading { background: #1a1430; color: #a78bfa; border: 1px solid #4c1d95; }
    hr { border: none; border-top: 1px solid #1e1e1e; margin: 22px 0 4px; }

    /* ── Help section ── */
    details { margin-top: 36px; border-top: 1px solid #1e1e1e; padding-top: 14px; }
    summary {
      font-size: 0.75rem; font-weight: 600; color: #555; letter-spacing: 0.05em;
      text-transform: uppercase; cursor: pointer; user-select: none;
      list-style: none; display: flex; align-items: center; gap: 6px;
    }
    summary::-webkit-details-marker { display: none; }
    summary::before { content: "▶"; font-size: 0.6rem; transition: transform 0.15s; }
    details[open] summary::before { transform: rotate(90deg); }
    .help-body { padding-top: 20px; display: flex; flex-direction: column; gap: 22px; }
    .help-section h3 {
      font-size: 0.7rem; font-weight: 700; color: #a78bfa;
      text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 8px;
    }
    .help-section p, .help-section li { font-size: 0.82rem; color: #777; line-height: 1.65; }
    .help-section ul { padding-left: 16px; margin-top: 4px; }
    .help-section p + p { margin-top: 6px; }
    .help-section code {
      font-family: "Menlo", "Courier New", monospace; font-size: 0.78rem;
      background: #1a1a1a; color: #c4b5fd; padding: 1px 5px; border-radius: 4px;
    }
    .help-section pre {
      background: #141414; border: 1px solid #2a2a2a; border-radius: 8px;
      padding: 10px 12px; margin-top: 8px; overflow-x: auto;
    }
    .help-section pre code {
      background: none; padding: 0; color: #c4b5fd; font-size: 0.78rem; line-height: 1.7;
    }
    .md-table { width: 100%; border-collapse: collapse; margin-top: 8px; }
    .md-table td {
      font-size: 0.78rem; padding: 5px 8px; color: #777; vertical-align: top;
    }
    .md-table td:first-child {
      font-family: "Menlo", "Courier New", monospace; color: #c4b5fd;
      white-space: nowrap; padding-left: 0; width: 44%;
    }
    .md-table tr + tr td { border-top: 1px solid #1e1e1e; }
  </style>
</head>
<body>
  <div class="top-bar">
    <h1>BlogPusher</h1>
    <nav style="display:flex;align-items:center;gap:16px">
      <span id="repo-badge" style="font-size:0.72rem;color:#444;font-family:monospace;margin-right:4px"></span>
      <a href="/manage" class="nav-link">Manage</a>
      <a href="/setup-blog" class="nav-link">Setup blog</a>
    </nav>
  </div>
  <p class="subtitle">Fill in the fields, upload your photos, publish.</p>

  <div id="edit-banner" style="display:none; margin-bottom:12px; padding:10px 14px;
    background:#1a1430; border:1px solid #4c1d95; border-radius:8px;
    font-size:0.82rem; color:#a78bfa;">
    Editing: <strong id="edit-banner-slug"></strong><br>
    <span style="color:#555;font-size:0.75rem">
      Existing images are preserved — upload new ones to add or replace them.
    </span>
  </div>

  <label>Post Title</label>
  <input type="text" id="title" placeholder="What happened?">

  <label>Date</label>
  <input type="date" id="date">

  <label>Description</label>
  <input type="text" id="description" placeholder="Short punchy summary for the post listing">

  <label>Tags</label>
  <input type="text" id="tags" placeholder="equipment, alberta, work">
  <p class="hint">Comma separated. "blog" is added automatically.</p>

  <label>Post Body <span style="color:#555;font-weight:400;text-transform:none">(paste from Claude)</span></label>
  <textarea id="body" placeholder="Paste the drafted post text from Claude here..."></textarea>

  <hr>

  <label>Photos</label>
  <div class="upload-area" id="upload-area">
    <input type="file" id="photos" accept="image/*" multiple>
    <div class="upload-icon">🖼️</div>
    <p class="upload-text">Tap to pick photos<br><strong>First photo = cover image</strong></p>
  </div>
  <p class="hint">Photos publish in the order shown. ✕ removes. 👁 toggles slider visibility.</p>

  <label class="check-row">
    <input type="checkbox" id="cover-in-gallery">
    <span>Also include cover photo in the gallery slider</span>
  </label>

  <label class="check-row">
    <input type="checkbox" id="enable-toc">
    <span>Enable Table of Contents</span>
  </label>

  <div id="preview-grid"></div>

  <button id="publish-btn" onclick="publish()">Publish Post</button>
  <div id="status"></div>

  <details>
    <summary>Help &amp; Reference</summary>
    <div class="help-body">

      <div class="help-section">
        <h3>Inline Images</h3>
        <p>Body photos are numbered 1, 2, 3… in grid order (the cover isn't counted unless "include in gallery" is checked). Reference them in the post body like this:</p>
        <pre><code>![optional caption](1-image.jpg)
![optional caption](2-image.jpg)</code></pre>
        <p>If you tapped the 👁 icon to hide a photo from the slider, it still gets uploaded — just with a <code>_</code> prefix. Reference it the same way:</p>
        <pre><code>![](_2-image.jpg)</code></pre>
        <p>Leave the caption empty for a clean image with no label, or add text for a caption below the photo.</p>
      </div>

      <div class="help-section">
        <h3>Table of Contents</h3>
        <p>Check "Enable Table of Contents" above before publishing. The TOC is built automatically from the headings in your post body — no extra steps needed.</p>
        <pre><code>## The First Big Thing
Some text here.

### A smaller detail
More text.

## The Second Big Thing
And so on.</code></pre>
        <p>Use <code>##</code> for main sections and <code>###</code> for sub-sections. The TOC appears alongside the post. Posts with only one or two headings probably don't need it.</p>
      </div>

      <div class="help-section">
        <h3>Markdown Quick Reference</h3>
        <table class="md-table">
          <tr><td>**bold text**</td><td><strong>bold text</strong></td></tr>
          <tr><td>_italic text_</td><td><em>italic text</em></td></tr>
          <tr><td>`inline code`</td><td>monospace snippet</td></tr>
          <tr><td>## Heading 2</td><td>Section heading (large)</td></tr>
          <tr><td>### Heading 3</td><td>Sub-heading (medium)</td></tr>
          <tr><td>- item</td><td>Bullet list item</td></tr>
          <tr><td>1. item</td><td>Numbered list item</td></tr>
          <tr><td>[text](https://url)</td><td>Hyperlink</td></tr>
          <tr><td>&gt; some quote</td><td>Block quote / callout</td></tr>
          <tr><td>---</td><td>Horizontal divider line</td></tr>
        </table>
        <p style="margin-top:10px">Blank line between paragraphs = new paragraph. End a line with two spaces for a line break without a new paragraph.</p>
      </div>

      <div class="help-section">
        <h3>Gallery Slider</h3>
        <p>All body photos appear in the slider by default. To keep a photo out of the slider (e.g. a diagram or a detail shot you only want inline), tap the 👁 icon on its tile — it dims to show it's excluded. It still gets uploaded and you can still reference it in the body with <code>![](_N-image.jpg)</code>.</p>
      </div>

    </div>
  </details>

  <script>
    const dateInput = document.getElementById("date");
    dateInput.value = new Date().toISOString().split("T")[0];

    let selectedFiles = [];
    let excludedFromSlider = new Set();
    let existingEntries = []; // edit mode: [{name, origHidden, hidden, removed, bodyN}]
    let editSlug = null;

    const EYE_ON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
    const EYE_OFF = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`;
    const COPY_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`;
    const CHECK_ICON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`;

    function copyMd(text, btn) {
      navigator.clipboard.writeText(text).then(() => {
        btn.innerHTML = CHECK_ICON;
        setTimeout(() => { btn.innerHTML = COPY_ICON; }, 1200);
      });
    }

    document.getElementById("photos").addEventListener("change", function(e) {
      selectedFiles = [...selectedFiles, ...Array.from(e.target.files)];
      renderPreviews();
      this.value = "";
    });

    document.getElementById("cover-in-gallery").addEventListener("change", renderPreviews);

    const ua = document.getElementById("upload-area");
    ua.addEventListener("dragover", e => { e.preventDefault(); ua.classList.add("dragover"); });
    ua.addEventListener("dragleave", () => ua.classList.remove("dragover"));
    ua.addEventListener("drop", e => {
      e.preventDefault(); ua.classList.remove("dragover");
      selectedFiles = [...selectedFiles, ...Array.from(e.dataTransfer.files).filter(f => f.type.startsWith("image/"))];
      renderPreviews();
    });

    function renderPreviews() {
      const grid = document.getElementById("preview-grid");
      const coverInGallery = document.getElementById("cover-in-gallery").checked;
      grid.innerHTML = "";
      // Use max over ALL existing entries (incl. removed) to safely offset new image numbers
      const maxExistingN = existingEntries.reduce((max, e) => Math.max(max, e.bodyN), 0);

      // Existing images (edit mode only)
      existingEntries.forEach((entry, i) => {
        if (entry.removed) return;
        const item = document.createElement("div");
        item.className = "preview-item" + (entry.hidden ? " slider-hidden" : "");
        const ext = entry.name.split('.').pop().toLowerCase();
        const mdText = entry.hidden ? `![](_${entry.bodyN}-image.${ext})` : null;
        item.innerHTML = `
          <img src="/api/image/${encodeURIComponent(editSlug)}/${encodeURIComponent(entry.name)}" alt="">
          <span class="badge">${entry.bodyN}</span>
          <button class="remove-btn" onclick="removeExisting(${i})" title="Remove">&#x2715;</button>
          <button class="eye-btn" onclick="toggleExistingSlider(${i})" title="${entry.hidden ? "Add to slider" : "Hide from slider"}">${entry.hidden ? EYE_OFF : EYE_ON}</button>
          ${mdText ? `<button class="copy-md-btn" title="Copy markdown" onclick="copyMd(${JSON.stringify(mdText)}, this)">${COPY_ICON}</button>` : ""}
        `;
        grid.appendChild(item);
      });

      // New uploads
      selectedFiles.forEach((file, i) => {
        const hidden = excludedFromSlider.has(i);
        const item = document.createElement("div");
        item.className = "preview-item" + (hidden ? " slider-hidden" : "");
        const url = URL.createObjectURL(file);
        let bodyN;
        if (i === 0 && !coverInGallery) bodyN = null;
        else if (coverInGallery)        bodyN = maxExistingN + i + 1;
        else                            bodyN = maxExistingN + i;
        const ext = file.name.split('.').pop().toLowerCase();
        const mdText = (hidden && bodyN !== null) ? `![](_${bodyN}-image.${ext})` : null;
        item.innerHTML = `
          <img src="${url}" alt="">
          <span class="badge">${i === 0 ? "Cover" : bodyN}</span>
          <button class="remove-btn" onclick="removePhoto(${i})" title="Remove">&#x2715;</button>
          <button class="eye-btn" onclick="toggleSlider(${i})" title="${hidden ? "Add to slider" : "Hide from slider"}">${hidden ? EYE_OFF : EYE_ON}</button>
          ${mdText ? `<button class="copy-md-btn" title="Copy markdown" onclick="copyMd(${JSON.stringify(mdText)}, this)">${COPY_ICON}</button>` : ""}
        `;
        grid.appendChild(item);
      });
    }

    function removePhoto(i) {
      selectedFiles.splice(i, 1);
      const next = new Set();
      for (const idx of excludedFromSlider) {
        if (idx < i) next.add(idx);
        else if (idx > i) next.add(idx - 1);
      }
      excludedFromSlider = next;
      renderPreviews();
    }

    function toggleSlider(i) {
      if (excludedFromSlider.has(i)) excludedFromSlider.delete(i);
      else excludedFromSlider.add(i);
      renderPreviews();
    }

    function removeExisting(i) {
      existingEntries[i].removed = true;
      renderPreviews();
    }

    function toggleExistingSlider(i) {
      existingEntries[i].hidden = !existingEntries[i].hidden;
      renderPreviews();
    }

    async function fileToBase64(file) {
      return new Promise((res, rej) => {
        const r = new FileReader();
        r.onload = () => res(r.result.split(",")[1]);
        r.onerror = rej;
        r.readAsDataURL(file);
      });
    }

    function setStatus(msg, type) {
      const el = document.getElementById("status");
      el.style.display = "block"; el.className = "status-" + type; el.innerHTML = msg;
    }

    async function publish() {
      const title       = document.getElementById("title").value.trim();
      const date        = document.getElementById("date").value;
      const description = document.getElementById("description").value.trim();
      const tagsRaw     = document.getElementById("tags").value.trim();
      const body        = document.getElementById("body").value.trim();
      const enableToc   = document.getElementById("enable-toc").checked;

      if (!title)       { setStatus("Title is required.", "err"); return; }
      if (!description) { setStatus("Description is required.", "err"); return; }
      if (!body)        { setStatus("Post body is required.", "err"); return; }

      const tags = [...new Set([...tagsRaw.split(",").map(t => t.trim().toLowerCase()).filter(Boolean), "blog"])];

      const btn = document.getElementById("publish-btn");
      btn.disabled = true;
      setStatus("Preparing photos...", "loading");

      const coverInGallery = document.getElementById("cover-in-gallery").checked;
      let cover_image = null, images = [];
      for (let i = 0; i < selectedFiles.length; i++) {
        const entry = {
          filename: selectedFiles[i].name,
          data: await fileToBase64(selectedFiles[i]),
          hidden: excludedFromSlider.has(i),
        };
        if (i === 0) {
          cover_image = entry;
          if (coverInGallery) images.push(entry);
        } else {
          images.push(entry);
        }
      }

      const maxExistingN = existingEntries.reduce((max, e) => Math.max(max, e.bodyN), 0);
      const image_start = maxExistingN + 1;
      const existing_edits = existingEntries
        .filter(e => e.removed || e.hidden !== e.origHidden)
        .map(e => ({name: e.name, hidden: e.hidden, remove: e.removed}));

      setStatus("Pushing to GitHub...", "loading");

      try {
        const resp = await fetch("/publish", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title, date, description, tags, body, cover_image, images, enable_toc: enableToc, image_start, existing_edits }),
        });
        const result = await resp.json();
        if (resp.ok) {
          setStatus(`Published! <a href="${result.url}" target="_blank" style="color:#86efac">${result.url}</a><br><small style="color:#555">GitHub Actions will build in ~60 seconds</small>`, "ok");
          document.getElementById("title").value = "";
          document.getElementById("body").value = "";
          document.getElementById("description").value = "";
          document.getElementById("tags").value = "";
          document.getElementById("enable-toc").checked = false;
          dateInput.value = new Date().toISOString().split("T")[0];
          selectedFiles = []; excludedFromSlider = new Set(); existingEntries = []; editSlug = null; renderPreviews();
        } else {
          setStatus("Error: " + (result.error || JSON.stringify(result)), "err");
        }
      } catch(e) {
        setStatus("Could not reach server: " + e.message, "err");
      }
      btn.disabled = false;
    }

    (async function() {
      editSlug = new URLSearchParams(window.location.search).get("edit");
      if (!editSlug) return;
      document.getElementById("publish-btn").textContent = "Update Post";
      document.getElementById("edit-banner-slug").textContent = editSlug;
      document.getElementById("edit-banner").style.display = "block";
      try {
        const r = await fetch(`/api/post/${encodeURIComponent(editSlug)}`);
        if (!r.ok) return;
        const p = await r.json();
        document.getElementById("title").value       = p.title || "";
        document.getElementById("date").value        = p.date  || "";
        document.getElementById("description").value = p.description || "";
        document.getElementById("tags").value        = (p.tags||[]).join(", ");
        document.getElementById("body").value        = p.body  || "";
        document.getElementById("enable-toc").checked = !!p.enable_toc;
        existingEntries = (p.existing_images || []).map(name => {
          const hidden = name.startsWith("_");
          const match = name.match(/^_?(\d+)-image\./);
          const bodyN = match ? parseInt(match[1]) : 0;
          return {name, origHidden: hidden, hidden, removed: false, bodyN};
        });
        renderPreviews();
      } catch(e) { /* silently fail */ }
    })();

    fetch('/health').then(r=>r.json()).then(h=>{
      const el = document.getElementById('repo-badge');
      if (el && h.repo) el.textContent = h.repo;
    });
  </script>
</body>
</html>""", 200, {"Content-Type": "text/html; charset=utf-8"}


# ── Manage page ────────────────────────────────────────────────────────────────
@app.route("/manage", methods=["GET"])
def manage():
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BlogPusher — Manage</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f0f0f; color: #e2e2e2;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 20px 16px 48px; max-width: 600px; margin: 0 auto;
    }
    .top-bar { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; }
    h1 { font-size: 1.4rem; font-weight: 700; color: #a78bfa; }
    .nav-link { font-size: 0.8rem; color: #7c3aed; text-decoration: none; }
    .nav-link:hover { color: #a78bfa; }
    .subtitle { font-size: 0.8rem; color: #555; margin-bottom: 24px; }
    #post-list { display: flex; flex-direction: column; gap: 8px; margin-top: 8px; }
    .post-row {
      display: flex; align-items: center; justify-content: space-between; gap: 12px;
      background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 10px; padding: 12px 14px;
    }
    .post-slug { font-size: 0.9rem; color: #e2e2e2; word-break: break-all; flex: 1; }
    .post-actions { display: flex; gap: 8px; flex-shrink: 0; }
    .view-btn {
      font-size: 0.75rem; padding: 6px 12px; border-radius: 8px;
      background: transparent; color: #7c3aed; border: 1px solid #3b1f70;
      text-decoration: none; transition: background 0.15s;
    }
    .view-btn:hover { background: #1a1430; }
    .del-btn {
      font-size: 0.75rem; padding: 6px 12px; border-radius: 8px;
      background: transparent; color: #ef4444; border: 1px solid #7f1d1d;
      cursor: pointer; transition: background 0.15s;
    }
    .del-btn:hover { background: #2e0d0d; }
    .del-btn:disabled { opacity: 0.35; cursor: not-allowed; }
    #msg {
      margin-top: 16px; padding: 14px; border-radius: 10px;
      font-size: 0.9rem; display: none; line-height: 1.6;
    }
    .msg-ok      { background: #0d2e1a; color: #4ade80; border: 1px solid #16532d; }
    .msg-err     { background: #2e0d0d; color: #f87171; border: 1px solid #7f1d1d; }
    .msg-loading { background: #1a1430; color: #a78bfa; border: 1px solid #4c1d95; }
    .empty { font-size: 0.85rem; color: #555; text-align: center; padding: 40px 0; }
  </style>
</head>
<body>
  <div class="top-bar">
    <h1>BlogPusher</h1>
    <nav style="display:flex;align-items:center;gap:16px">
      <span id="repo-badge" style="font-size:0.72rem;color:#444;font-family:monospace;margin-right:4px"></span>
      <a href="/" class="nav-link">New post</a>
      <a href="/setup-blog" class="nav-link">Setup blog</a>
    </nav>
  </div>
  <p class="subtitle">Delete published posts. This removes the post folder and cover image from the repo.</p>

  <div id="post-list"><p class="empty">Loading…</p></div>
  <div id="msg"></div>

  <script>
    function setMsg(text, type) {
      const el = document.getElementById("msg");
      el.style.display = "block"; el.className = "msg-" + type; el.innerHTML = text;
    }

    async function loadPosts() {
      const list = document.getElementById("post-list");
      try {
        const [healthResp, postsResp] = await Promise.all([fetch("/health"), fetch("/api/posts")]);
        const health = await healthResp.json();
        const data = await postsResp.json();
        const badge = document.getElementById("repo-badge");
        if (badge && health.repo) badge.textContent = health.repo;
        let siteUrl = (health.site_url || "").replace(/\/$/, "");
        if (siteUrl && !siteUrl.startsWith("http://") && !siteUrl.startsWith("https://")) {
          siteUrl = "https://" + siteUrl;
        }
        if (!postsResp.ok) { list.innerHTML = `<p class="empty">Error: ${data.error}</p>`; return; }
        if (!data.posts.length) { list.innerHTML = `<p class="empty">No posts found.</p>`; return; }
        list.innerHTML = "";
        for (const slug of data.posts) {
          const row = document.createElement("div");
          row.className = "post-row";
          row.id = "row-" + slug;
          const viewHref = siteUrl ? `${siteUrl}/posts/${slug.toLowerCase()}/` : "#";
          row.innerHTML = `
            <span class="post-slug">${slug}</span>
            <div class="post-actions">
              <a class="view-btn" href="${viewHref}" target="_blank">View</a>
              <a class="view-btn" href="/?edit=${encodeURIComponent(slug)}">Edit</a>
              <button class="del-btn" onclick="deletePost('${slug}')">Delete</button>
            </div>
          `;
          list.appendChild(row);
        }
      } catch(e) {
        list.innerHTML = `<p class="empty">Could not load posts: ${e.message}</p>`;
      }
    }

    async function deletePost(slug) {
      if (!confirm(`Delete "${slug}" and all its files?\n\nThis cannot be undone.`)) return;
      const btn = document.querySelector(`#row-${CSS.escape(slug)} .del-btn`);
      if (btn) btn.disabled = true;
      setMsg(`Deleting ${slug}…`, "loading");
      try {
        const r = await fetch("/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slug }),
        });
        const data = await r.json();
        if (r.status === 200 || r.status === 207) {
          document.getElementById("row-" + slug)?.remove();
          if (!document.querySelector(".post-row")) {
            document.getElementById("post-list").innerHTML = `<p class="empty">No posts found.</p>`;
          }
          const warn = data.errors?.length ? ` (${data.errors.length} file(s) may need manual cleanup)` : "";
          setMsg(`Deleted <strong>${slug}</strong>.${warn} Site will rebuild in ~60s.`, data.errors?.length ? "err" : "ok");
        } else {
          if (btn) btn.disabled = false;
          setMsg("Delete failed: " + (data.error || JSON.stringify(data)), "err");
        }
      } catch(e) {
        if (btn) btn.disabled = false;
        setMsg("Could not reach server: " + e.message, "err");
      }
    }

    loadPosts();
  </script>
</body>
</html>""", 200, {"Content-Type": "text/html; charset=utf-8"}


# ── API: list posts ────────────────────────────────────────────────────────────
@app.route("/api/posts", methods=["GET"])
def list_posts():
    r = requests.get(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/content/posts",
        headers=gh_headers()
    )
    if r.status_code != 200:
        return jsonify({"error": "Could not fetch posts from GitHub"}), 500
    posts = sorted([item["name"] for item in r.json() if item["type"] == "dir"])
    return jsonify({"posts": posts})


# ── API: delete post ───────────────────────────────────────────────────────────
@app.route("/delete", methods=["POST"])
def delete_post():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400
    slug = (data.get("slug") or "").strip()
    if not slug:
        return jsonify({"error": "slug required"}), 400

    deleted, errors = [], []

    # Delete every file inside content/posts/{slug}/
    r = requests.get(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/content/posts/{slug}",
        headers=gh_headers()
    )
    if r.status_code == 200:
        for item in r.json():
            if item["type"] == "file":
                dr = requests.delete(
                    f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{item['path']}",
                    headers=gh_headers(),
                    json={"message": f"delete: {slug}", "sha": item["sha"], "branch": GITHUB_BRANCH}
                )
                (deleted if dr.status_code in (200, 201) else errors).append(item["path"])
    else:
        errors.append(f"content/posts/{slug}/ — not found or inaccessible")

    # Delete cover images (assets/images/{slug}.* and static/images/{slug}.*)
    for folder in ["assets/images", "static/images"]:
        r = requests.get(
            f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{folder}",
            headers=gh_headers()
        )
        if r.status_code == 200:
            for item in r.json():
                stem = item["name"].rsplit(".", 1)[0]
                if stem == slug:
                    dr = requests.delete(
                        f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{item['path']}",
                        headers=gh_headers(),
                        json={"message": f"delete cover: {slug}", "sha": item["sha"], "branch": GITHUB_BRANCH}
                    )
                    (deleted if dr.status_code in (200, 201) else errors).append(item["path"])

    if errors and not deleted:
        return jsonify({"error": "All deletes failed", "errors": errors}), 500

    return jsonify({
        "status": "success" if not errors else "partial",
        "deleted": deleted,
        "errors": errors,
    }), 200 if not errors else 207


# ── API: publish post ──────────────────────────────────────────────────────────
@app.route("/publish", methods=["POST"])
def publish():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON"}), 400

    title       = (data.get("title") or "").strip()
    body        = (data.get("body") or "").strip()
    description = (data.get("description") or "").strip()
    tags        = data.get("tags") or ["blog"]
    date_str    = data.get("date") or datetime.now().strftime("%Y-%m-%d")
    cover_raw   = data.get("cover_image")
    images_raw  = data.get("images") or []
    enable_toc  = bool(data.get("enable_toc", False))

    if not title or not body:
        return jsonify({"error": "title and body are required"}), 400

    slug = slugify(title)
    results, errors = [], []

    # Process edits to existing images (edit mode)
    existing_edits = data.get("existing_edits") or []
    for edit in existing_edits:
        ename = (edit.get("name") or "").strip()
        if not ename or "/" in ename or ".." in ename:
            continue
        old_path = f"content/posts/{slug}/{ename}"
        if edit.get("remove"):
            sha = get_sha(old_path)
            if sha:
                dr = requests.delete(
                    f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{old_path}",
                    headers=gh_headers(),
                    json={"message": f"edit: remove {ename}", "sha": sha, "branch": GITHUB_BRANCH}
                )
                (results if dr.status_code in (200, 201) else errors).append(
                    ("+ " if dr.status_code in (200, 201) else "- ") + f"del:{old_path}"
                )
        else:
            was_hidden = ename.startswith("_")
            new_hidden = bool(edit.get("hidden", was_hidden))
            if new_hidden != was_hidden:
                base = ename.lstrip("_")
                new_name = ("_" + base) if new_hidden else base
                new_path = f"content/posts/{slug}/{new_name}"
                r_old = requests.get(
                    f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{old_path}", headers=gh_headers()
                )
                if r_old.status_code == 200:
                    content_b64 = r_old.json()["content"].replace("\n", "")
                    old_sha = r_old.json()["sha"]
                    pr = requests.put(
                        f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{new_path}",
                        headers=gh_headers(),
                        json={"message": f"edit: rename {ename} to {new_name}", "content": content_b64, "branch": GITHUB_BRANCH}
                    )
                    if pr.status_code in (200, 201):
                        requests.delete(
                            f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/{old_path}",
                            headers=gh_headers(),
                            json={"message": f"edit: remove old {ename}", "sha": old_sha, "branch": GITHUB_BRANCH}
                        )
                        results.append(f"+ rename:{ename}→{new_name}")
                    else:
                        errors.append(f"rename failed: {ename}")

    image_start = max(int(data.get("image_start", 1)), 1)

    # Cover image → assets/images/ and static/images/
    cover_filename = None
    if cover_raw:
        try:
            img_bytes = base64.b64decode(cover_raw["data"])
            ext = cover_raw["filename"].rsplit(".", 1)[-1].lower()
            cover_filename = f"{slug}.{ext}"
            for dest in [f"assets/images/{cover_filename}", f"static/images/{cover_filename}"]:
                ok, err = push_file(dest, img_bytes, f"cover: {title}", is_binary=True)
                (results if ok else errors).append(("+ " if ok else "- ") + dest + ("" if ok else f": {err}"))
        except Exception as e:
            errors.append(f"Cover error: {e}")

    # Body images — hidden flag adds _ prefix to exclude from slider
    for i, img in enumerate(images_raw, start=image_start):
        try:
            img_bytes = base64.b64decode(img["data"])
            ext = img["filename"].rsplit(".", 1)[-1].lower()
            prefix = "_" if img.get("hidden") else ""
            dest = f"content/posts/{slug}/{prefix}{i}-image.{ext}"
            ok, err = push_file(dest, img_bytes, f"image {i}: {title}", is_binary=True)
            (results if ok else errors).append(("+ " if ok else "- ") + dest + ("" if ok else f": {err}"))
        except Exception as e:
            errors.append(f"Image {i} error: {e}")

    # Front matter — omit no_toc when TOC is enabled
    tags_yaml = "\n".join(f"  - {t}" for t in tags)
    fm_lines  = [
        "---",
        f'title: "{title}"',
        f"date: {date_str}",
        "draft: false",
        f'description: "{description}"',
        f"tags:\n{tags_yaml}",
        "type: gallery",
    ]
    if not enable_toc:
        fm_lines.append("no_toc: true")
    if cover_filename:
        fm_lines.append(f'Image: "/images/{cover_filename}"')
    fm_lines.append("---")
    frontmatter = "\n".join(fm_lines)

    ok, err = push_file(f"content/posts/{slug}/index.md", frontmatter + "\n\n" + body, f"post: {title}")
    (results if ok else errors).append(("+ " if ok else "- ") + f"content/posts/{slug}/index.md" + ("" if ok else f": {err}"))

    if errors and not results:
        return jsonify({"status": "error", "errors": errors}), 500

    return jsonify({
        "status": "success" if not errors else "partial",
        "slug": slug,
        "url": f"{SITE_URL}/posts/{slug}/",
        "pushed": results,
        "errors": errors,
    }), 200 if not errors else 207


# ── API: proxy image from post bundle (for edit preview) ───────────────────────
@app.route("/api/image/<slug>/<filename>", methods=["GET"])
def get_image(slug, filename):
    if "/" in filename or ".." in filename:
        return "", 400
    r = requests.get(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/content/posts/{slug}/{filename}",
        headers=gh_headers()
    )
    if r.status_code != 200:
        return "", 404
    img_bytes = base64.b64decode(r.json()["content"])
    ext = filename.rsplit(".", 1)[-1].lower()
    mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
            "gif": "image/gif", "webp": "image/webp"}.get(ext, "image/octet-stream")
    return Response(img_bytes, mimetype=mime)


# ── API: fetch single post ─────────────────────────────────────────────────────
@app.route("/api/post/<slug>", methods=["GET"])
def get_post(slug):
    r = requests.get(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/content/posts/{slug}/index.md",
        headers=gh_headers()
    )
    if r.status_code != 200:
        return jsonify({"error": "Post not found"}), 404

    content = base64.b64decode(r.json()["content"]).decode()
    parts = content.split("---", 2)   # ["", "\nfm\n", "\nbody"]
    fm = yaml.safe_load(parts[1]) if len(parts) >= 3 else {}
    body = parts[2].strip() if len(parts) >= 3 else content.strip()

    img_r = requests.get(
        f"{GITHUB_API}/repos/{GITHUB_REPO}/contents/content/posts/{slug}",
        headers=gh_headers()
    )
    existing_images = sorted([
        f["name"] for f in (img_r.json() if img_r.status_code == 200 else [])
        if f.get("type") == "file" and f["name"] != "index.md"
    ])

    tags = [t for t in (fm.get("tags") or []) if t != "blog"]

    return jsonify({
        "title": fm.get("title", ""),
        "date": str(fm.get("date", "")),
        "description": fm.get("description", ""),
        "tags": tags,
        "body": body,
        "enable_toc": not fm.get("no_toc", False),
        "existing_images": existing_images,
    })


# ── Setup blog page ────────────────────────────────────────────────────────────
@app.route("/setup-blog", methods=["GET"])
def setup_blog_page():
    return r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>BlogPusher — Setup</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: #0f0f0f; color: #e2e2e2;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      padding: 20px 16px 48px; max-width: 600px; margin: 0 auto;
    }
    .top-bar { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px; }
    h1 { font-size: 1.4rem; font-weight: 700; color: #a78bfa; }
    .nav-link { font-size: 0.8rem; color: #7c3aed; text-decoration: none; }
    .nav-link:hover { color: #a78bfa; }
    .subtitle { font-size: 0.8rem; color: #555; margin-bottom: 24px; }
    label {
      display: block; font-size: 0.75rem; font-weight: 600; color: #888;
      text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; margin-top: 18px;
    }
    input[type="text"], input[type="password"] {
      width: 100%; background: #1a1a1a; color: #e2e2e2;
      border: 1px solid #2a2a2a; border-radius: 10px; padding: 12px 14px;
      font-size: 0.95rem; font-family: inherit; outline: none;
      transition: border-color 0.15s; -webkit-appearance: none;
    }
    input[type="text"]:focus, input[type="password"]:focus { border-color: #7c3aed; }
    .hint { font-size: 0.75rem; color: #555; margin-top: 5px; }
    .btn-row { display: flex; gap: 10px; margin-top: 22px; }
    .btn {
      padding: 14px 20px; border-radius: 10px; font-size: 0.95rem; font-weight: 600;
      cursor: pointer; border: none; transition: background 0.15s, transform 0.1s;
    }
    .btn:active { transform: scale(0.98); }
    .btn:disabled { cursor: not-allowed; opacity: 0.5; }
    #check-btn { background: #2a2a2a; color: #a78bfa; flex: 1; }
    #check-btn:hover:not(:disabled) { background: #3a2a5a; }
    #push-btn { background: #7c3aed; color: white; flex: 2; display: none; }
    #push-btn:hover:not(:disabled) { background: #6d28d9; }
    #checklist { margin-top: 20px; display: none; }
    .check-header {
      font-size: 0.7rem; font-weight: 700; color: #555;
      text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 10px;
    }
    .file-row {
      display: flex; align-items: center; gap: 10px;
      padding: 8px 12px; background: #1a1a1a; border-radius: 8px; margin-bottom: 6px;
      border: 1px solid #2a2a2a;
    }
    .file-status { font-size: 1rem; flex-shrink: 0; width: 20px; text-align: center; }
    .file-path { font-family: "Menlo","Courier New",monospace; font-size: 0.78rem; color: #c4b5fd; }
    .file-note { font-size: 0.72rem; color: #555; margin-left: auto; flex-shrink: 0; }
    #result {
      margin-top: 16px; padding: 14px; border-radius: 10px;
      font-size: 0.88rem; display: none; line-height: 1.7;
    }
    .result-ok      { background: #0d2e1a; color: #4ade80; border: 1px solid #16532d; }
    .result-err     { background: #2e0d0d; color: #f87171; border: 1px solid #7f1d1d; }
    .result-loading { background: #1a1430; color: #a78bfa; border: 1px solid #4c1d95; }
    .result-partial { background: #1a1a0d; color: #fbbf24; border: 1px solid #713f12; }
    #manual-step {
      margin-top: 20px; padding: 16px; border-radius: 10px;
      background: #141414; border: 1px solid #2a2a2a; display: none;
    }
    #manual-step h3 {
      font-size: 0.72rem; font-weight: 700; color: #a78bfa;
      text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 10px;
    }
    #manual-step p { font-size: 0.82rem; color: #777; line-height: 1.65; }
    #manual-step p + p { margin-top: 8px; }
    #manual-step code {
      font-family: "Menlo","Courier New",monospace; font-size: 0.78rem;
      background: #1a1a1a; color: #c4b5fd; padding: 1px 5px; border-radius: 4px;
    }
    #manual-step pre {
      background: #0f0f0f; border: 1px solid #2a2a2a; border-radius: 8px;
      padding: 10px 12px; margin-top: 8px; overflow-x: auto;
    }
    #manual-step pre code { background: none; padding: 0; }
    .overwrite-row { display: flex; align-items: center; gap: 10px; margin-top: 16px; cursor: pointer; }
    .overwrite-row input[type="checkbox"] { width: 16px; height: 16px; accent-color: #7c3aed; }
    .overwrite-row span { font-size: 0.82rem; color: #555; }
  </style>
</head>
<body>
  <div class="top-bar">
    <h1>BlogPusher</h1>
    <nav style="display:flex;align-items:center;gap:16px">
      <span id="repo-badge" style="font-size:0.72rem;color:#444;font-family:monospace;margin-right:4px"></span>
      <a href="/" class="nav-link">New post</a>
      <a href="/manage" class="nav-link">Manage</a>
    </nav>
  </div>
  <p class="subtitle">Check and install the BlogPusher gallery templates into this instance's configured blog repo.</p>

  <label class="overwrite-row">
    <input type="checkbox" id="overwrite" onchange="updatePushBtn()">
    <span>Overwrite files that already exist</span>
  </label>

  <div class="btn-row">
    <button id="check-btn" class="btn" onclick="checkFiles()">Check files</button>
    <button id="push-btn" class="btn" onclick="pushFiles()">Push missing files</button>
  </div>

  <div id="checklist">
    <p class="check-header" style="margin-top:20px">File status</p>
    <div id="file-rows"></div>
  </div>
  <div id="result"></div>

  <div id="manual-step">
    <h3>One manual step remaining</h3>
    <p>Add this line to your site's <code>layouts/partials/head.html</code> (just before <code>&lt;/head&gt;</code> or wherever you include styles):</p>
    <pre><code>&lt;link rel="stylesheet" href="/css/gallery.css"&gt;</code></pre>
    <p>If you don't have a <code>head.html</code> override yet, copy it from <code>themes/mana/layouts/partials/head.html</code> into <code>layouts/partials/head.html</code> first, then add the line.</p>
  </div>

  <script>
    let lastCheckResult = null;

    function getInputs() {
      return { overwrite: document.getElementById("overwrite").checked };
    }

    function setResult(msg, type) {
      const el = document.getElementById("result");
      el.style.display = "block"; el.className = "result-" + type; el.innerHTML = msg;
    }

    function updatePushBtn() {
      if (!lastCheckResult) return;
      const overwrite = document.getElementById("overwrite").checked;
      const missing = Object.values(lastCheckResult).filter(v => !v).length;
      const total = Object.keys(lastCheckResult).length;
      const btn = document.getElementById("push-btn");
      if (overwrite) {
        btn.textContent = `Push all ${total} files`;
        btn.style.display = "block";
      } else if (missing > 0) {
        btn.textContent = `Push ${missing} missing file${missing > 1 ? "s" : ""}`;
        btn.style.display = "block";
      } else {
        btn.style.display = "none";
      }
    }

    function renderChecklist(files) {
      lastCheckResult = files;
      const cl = document.getElementById("checklist");
      const rows = document.getElementById("file-rows");
      cl.style.display = "block";
      rows.innerHTML = "";
      for (const [path, present] of Object.entries(files)) {
        const row = document.createElement("div");
        row.className = "file-row";
        row.style.borderColor = present ? "#16532d" : "#7f1d1d";
        const note = path.endsWith(".gitkeep") ? "directory placeholder" : "";
        row.innerHTML = `
          <span class="file-status">${present ? "✓" : "✗"}</span>
          <span class="file-path">${path}</span>
          ${note ? `<span class="file-note">${note}</span>` : ""}
        `;
        rows.appendChild(row);
      }
      updatePushBtn();
      return Object.values(files).every(Boolean);
    }

    async function checkFiles() {
      const btn = document.getElementById("check-btn");
      btn.disabled = true;
      setResult("Checking…", "loading");
      try {
        const r = await fetch("/api/verify", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
        const data = await r.json();
        if (!r.ok) { setResult("Error: " + (data.error || JSON.stringify(data)), "err"); btn.disabled = false; return; }
        const allPresent = renderChecklist(data.files);
        if (allPresent) {
          setResult("All files are present. This repo is ready for BlogPusher.", "ok");
          document.getElementById("manual-step").style.display = "block";
        } else {
          const missing = Object.values(data.files).filter(v => !v).length;
          setResult(`${missing} file${missing > 1 ? "s" : ""} missing — click the button above to install them.`, "partial");
        }
      } catch(e) {
        setResult("Could not reach server: " + e.message, "err");
      }
      btn.disabled = false;
    }

    async function pushFiles() {
      const { overwrite } = getInputs();
      const btn = document.getElementById("push-btn");
      btn.disabled = true;
      setResult("Pushing files…", "loading");
      try {
        const r = await fetch("/api/setup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ overwrite }),
        });
        const data = await r.json();
        let parts = [];
        if (data.pushed?.length)  parts.push(`Pushed: ${data.pushed.map(f => `<code>${f}</code>`).join(", ")}`);
        if (data.skipped?.length) parts.push(`Already present: ${data.skipped.map(f => `<code>${f}</code>`).join(", ")}`);
        if (data.errors?.length)  parts.push(`Errors: ${data.errors.join(", ")}`);
        const type = data.errors?.length ? (data.pushed?.length ? "partial" : "err") : "ok";
        setResult(parts.join("<br>") || "Done.", type);
        if (!data.errors?.length) {
          document.getElementById("manual-step").style.display = "block";
        }
        await checkFiles();
      } catch(e) {
        setResult("Could not reach server: " + e.message, "err");
        btn.disabled = false;
      }
    }

    fetch('/health').then(r=>r.json()).then(h=>{
      const el = document.getElementById('repo-badge');
      if (el && h.repo) el.textContent = h.repo;
    });
  </script>
</body>
</html>""", 200, {"Content-Type": "text/html; charset=utf-8"}


# ── API: verify blog setup ──────────────────────────────────────────────────────
@app.route("/api/verify", methods=["POST"])
def verify_setup():
    files = {path: get_sha(path) is not None for path in SETUP_FILES + SETUP_GITKEEPS}
    return jsonify({"files": files, "all_present": all(files.values())})


# ── API: push blog setup files ─────────────────────────────────────────────────
@app.route("/api/setup", methods=["POST"])
def setup_blog():
    data = request.get_json(silent=True) or {}
    overwrite = bool(data.get("overwrite", False))

    if not os.path.isdir(THEME_FILES_DIR):
        return jsonify({"error": "hugo-theme-files not found in server image"}), 500

    pushed, skipped, errors = [], [], []

    for rel_path in SETUP_FILES:
        src = os.path.join(THEME_FILES_DIR, rel_path.replace("/", os.sep))
        if not os.path.exists(src):
            errors.append(f"{rel_path}: missing from image")
            continue
        if not overwrite and get_sha(rel_path) is not None:
            skipped.append(rel_path)
            continue
        with open(src, "rb") as f:
            content = f.read()
        ok, err = push_file(rel_path, content, "setup: add BlogPusher theme files", is_binary=True)
        (pushed if ok else errors).append(rel_path if ok else f"{rel_path}: {err}")

    for rel_path in SETUP_GITKEEPS:
        if not overwrite and get_sha(rel_path) is not None:
            skipped.append(rel_path)
            continue
        ok, err = push_file(rel_path, b"", "setup: create image directories", is_binary=True)
        (pushed if ok else errors).append(rel_path if ok else f"{rel_path}: {err}")

    status = 200 if not errors else (207 if pushed else 500)
    return jsonify({"pushed": pushed, "skipped": skipped, "errors": errors}), status


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
