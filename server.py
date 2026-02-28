#!/usr/bin/env python3
"""
BlogPusher - NAS relay server
"""

import os
import re
import base64
import requests
from datetime import datetime
from flask import Flask, request, jsonify

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

GITHUB_API    = "https://api.github.com"

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50MB max upload


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
    return jsonify({"status": "ok", "repo": GITHUB_REPO, "configured": bool(GITHUB_TOKEN and GITHUB_REPO)})


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
    <a href="/manage" class="nav-link">Manage posts →</a>
  </div>
  <p class="subtitle">Fill in the fields, upload your photos, publish.</p>

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

    const EYE_ON = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;
    const EYE_OFF = `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`;

    document.getElementById("photos").addEventListener("change", function(e) {
      selectedFiles = [...selectedFiles, ...Array.from(e.target.files)];
      renderPreviews();
      this.value = "";
    });

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
      grid.innerHTML = "";
      selectedFiles.forEach((file, i) => {
        const hidden = excludedFromSlider.has(i);
        const item = document.createElement("div");
        item.className = "preview-item" + (hidden ? " slider-hidden" : "");
        const url = URL.createObjectURL(file);
        item.innerHTML = `
          <img src="${url}" alt="">
          <span class="badge">${i === 0 ? "Cover" : i + 1}</span>
          <button class="remove-btn" onclick="removePhoto(${i})" title="Remove">&#x2715;</button>
          <button class="eye-btn" onclick="toggleSlider(${i})" title="${hidden ? "Add to slider" : "Hide from slider"}">${hidden ? EYE_OFF : EYE_ON}</button>
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

      setStatus("Pushing to GitHub...", "loading");

      try {
        const resp = await fetch("/publish", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title, date, description, tags, body, cover_image, images, enable_toc: enableToc }),
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
          selectedFiles = []; excludedFromSlider = new Set(); renderPreviews();
        } else {
          setStatus("Error: " + (result.error || JSON.stringify(result)), "err");
        }
      } catch(e) {
        setStatus("Could not reach server: " + e.message, "err");
      }
      btn.disabled = false;
    }
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
    <a href="/" class="nav-link">← New post</a>
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
        const r = await fetch("/api/posts");
        const data = await r.json();
        if (!r.ok) { list.innerHTML = `<p class="empty">Error: ${data.error}</p>`; return; }
        if (!data.posts.length) { list.innerHTML = `<p class="empty">No posts found.</p>`; return; }
        list.innerHTML = "";
        for (const slug of data.posts) {
          const row = document.createElement("div");
          row.className = "post-row";
          row.id = "row-" + slug;
          row.innerHTML = `
            <span class="post-slug">${slug}</span>
            <div class="post-actions">
              <a class="view-btn" href="https://blog.emen.win/posts/${slug}/" target="_blank">View</a>
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
    for i, img in enumerate(images_raw, start=1):
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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
