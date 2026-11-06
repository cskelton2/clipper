# 🎬 OpusCut AI Studio (Streamlit Edition)

A full-stack Python & Streamlit video clipping web app powered by Gemini AI.

## 🚀 Quick Setup & Deployment to GitHub / Streamlit Cloud

### 1. Push to GitHub
1. Create a new repository on GitHub named `opuscut-ai`.
2. Commit and push `app.py` and `requirements.txt`:
   ```bash
   git init
   git add app.py requirements.txt README.md
   git commit -m "Initial OpusCut AI Streamlit commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/opuscut-ai.git
   git push -u origin main
   ```

### 2. Deploy to Streamlit Community Cloud (100% Free Hosting)
1. Go to [share.streamlit.io](https://share.streamlit.io) and log in with GitHub.
2. Click **"New app"**.
3. Select your repository `opuscut-ai`, branch `main`, and main file path `app.py`.
4. Click **"Deploy!"**. Your app will be live on a custom `.streamlit.app` URL!

## 🌟 Features
- Direct web video stream ingestion (YouTube, direct MP4, HLS).
- Dynamic framing & aspect ratio selector (9:16 Vertical, 1:1 Square, 16:9 Widescreen).
- Gemini API virality analysis to compute clip scores, hook titles, and karaoke subtitling pre-render tags.
- Zero local storage footprint.
