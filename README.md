# 🎬 OpusCut AI Studio

AI-powered YouTube podcast clipper: full-length transcript alignment,
Gemini-driven viral clip selection, in-app MP4 slicing, and CapCut hand-off.

## Features

- **Multi-backend transcript cascade** — works on cloud IPs without a proxy:
  1. `yt-transcript-pro` (watch-page scrape → yt-dlp player API → legacy API)
  2. `youtube-transcript-api` via `GenericProxyConfig` (if configured)
  3. `youtube-transcript-api` direct
  4. `yt-dlp --impersonate chrome` (TLS fingerprint mimicry)
- Supports 3+ hour podcasts with exact timestamp alignment
- Gemini AI clip analysis with virality scoring, hooks, and captions
- One-click MP4 rendering via `yt-dlp` + `ffmpeg`
- Jump-to-timestamp preview and CapCut editor link

## Quick start

```bash
git clone <your-repo-url>
cd opuscut-ai-studio
pip install -r requirements.txt
# system dependency
sudo apt install ffmpeg          # Debian / Ubuntu
# or: brew install ffmpeg         # macOS

mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# add your GEMINI_API_KEY

streamlit run app.py
