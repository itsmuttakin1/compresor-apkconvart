# ToolKit Pro — Video Compressor & APK Builder

A powerful web tool with two features:
1. 🎬 **Video Compressor** — FFmpeg-powered video compression
2. 📦 **APK Builder** — Convert URL/HTML/ZIP games into Android APKs

## Features

### Video Compressor
- Supports MP4, AVI, MKV, MOV, WebM, FLV, and more
- Quality control: Low / Medium / High
- Resolution: Original / 1080p / 720p / 480p
- Shows size reduction stats
- Background processing with progress

### APK Builder
- **Website URL** → APK (WebView wrapper)
- **HTML file** → APK (embedded)
- **Game ZIP** → APK (full game bundled)
- Custom app name, package name, app icon
- Resizes icon to all Android densities

## Local Development

```bash
pip install -r requirements.txt
python app.py
# Visit http://localhost:5000
```

> **Note:** FFmpeg must be installed for video compression.
> `winget install ffmpeg` (Windows) or `apt install ffmpeg` (Linux)

## Railway Deployment

### Option A: GitHub (Recommended)
1. Push this folder to a GitHub repo
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select the repo → Railway auto-detects Python + FFmpeg via nixpacks.toml
4. Done! Get your URL from Railway dashboard

### Option B: Railway CLI
```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

## Environment Variables (Railway)
| Variable | Default | Description |
|----------|---------|-------------|
| `PORT`   | 5000    | Auto-set by Railway |

## Tech Stack
- **Backend:** Python / Flask
- **Video:** FFmpeg (via system binary)
- **APK:** Android SDK + Gradle (auto-detected on Railway)
- **Frontend:** Vanilla HTML/CSS/JS (no framework needed)
- **Deploy:** Nixpacks on Railway
