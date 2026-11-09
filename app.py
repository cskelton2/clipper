import streamlit as st
import google.generativeai as genai
import re
import json
import urllib.request
import os
import subprocess
import glob
import shutil
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

def get_cookie_file_path():
    """Checks if a exported YouTube cookies file exists in the directory."""
    for cookie_name in ["cookies.txt", "youtube_cookies.txt", "yt_cookies.txt"]:
        if os.path.exists(cookie_name):
            return cookie_name
    return None

def get_js_runtime_config():
    """Finds available JS runtimes (deno/node) to pass to yt-dlp to bypass YouTube 403 errors."""
    runtimes = []
    if shutil.which("deno"):
        runtimes.append("deno")
    if shutil.which("node"):
        runtimes.append("node")
    return runtimes

st.set_page_config(
    page_title="OpusCut AI Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp {
        background-color: #0d0f17;
        color: #f1f5f9;
    }
    .main-header {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #a855f7 0%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .stCard {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
    }
    .score-badge {
        background: linear-gradient(135deg, #a855f7, #ec4899);
        color: white;
        padding: 4px 10px;
        border-radius: 20px;
        font-weight: bold;
        font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)

def get_api_key():
    try:
        if "GEMINI_API_KEY" in st.secrets:
            return st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    return None

api_key = get_api_key()

with st.sidebar:
    st.title("⚡ OpusCut AI")
    st.caption("Real AI Video Clipper & 3-Hour Podcast Analyzer")
    
    if not api_key:
        user_key = st.text_input("Gemini API Key", type="password", help="Enter key or set GEMINI_API_KEY in Streamlit Secrets")
        if user_key:
            api_key = user_key
            
    st.divider()
    aspect_ratio = st.selectbox("Framing / Aspect Ratio", ["9:16 Vertical (TikTok/Reels)", "1:1 Square (Instagram)", "16:9 Widescreen (YouTube)"])
    max_clips = st.slider("Max Clips to Extract", 3, 20, 8)

    st.divider()
    st.subheader("🔑 YouTube Authentication")
    
    use_oauth = st.checkbox("Enable Google / YouTube Account Sign-In (OAuth)", value=True, help="Automatically prompts a Google Device Sign-In link when YouTube requests human verification.")

    # Optional Cookie Uploader (Backup fallback)
    uploaded_cookie = st.file_uploader("Or Upload cookies.txt (Optional)", type=["txt"])
    if uploaded_cookie:
        with open("cookies.txt", "wb") as f:
            f.write(uploaded_cookie.getbuffer())
        st.success("✅ Cookies loaded successfully!")

    browser_cookie = st.selectbox("Auto-Extract Browser Cookies", ["None", "chrome", "firefox", "edge", "safari", "brave"])
    if browser_cookie != "None":
        st.session_state['browser_cookie'] = browser_cookie

if api_key:
    genai.configure(api_key=api_key)

st.markdown('<p class="main-header">🎬 OpusCut AI Studio</p>', unsafe_allow_html=True)
st.caption("Supports full-length podcasts up to 3+ hours with robust YouTube caption scraping and direct MP4 clipping.")
st.write("")

video_url = st.text_input("🔗 Paste YouTube Video or Podcast Link:", placeholder="https://www.youtube.com/watch?v=...")

def parse_youtube_id(url):
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

def fetch_youtube_metadata(yt_id):
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={yt_id}&format=json"
        req = urllib.request.urlopen(oembed_url)
        data = json.loads(req.read().decode())
        return data.get("title", "")
    except Exception:
        return ""

def parse_vtt_subtitles(vtt_path):
    """Parses VTT subtitle files into clean timestamped transcript lines"""
    formatted_lines = []
    try:
        with open(vtt_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        time_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.,](\d{3})|(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{2}):(\d{2})[.,](\d{3})')
        current_time_str = None
        seen_texts = set()
        
        for line in lines:
            line_str = line.strip()
            match = time_pattern.search(line_str)
            if match:
                groups = [g for g in match.groups() if g is not None]
                if len(groups) >= 8:
                    hours, minutes, seconds = int(groups[0]), int(groups[1]), int(groups[2])
                    current_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"
                elif len(groups) >= 4:
                    minutes, seconds = int(groups[0]), int(groups[1])
                    current_time_str = f"{minutes:02d}:{seconds:02d}"
            elif current_time_str and line_str and not '-->' in line_str and not line_str.isdigit() and not line_str.startswith('WEBVTT') and not line_str.startswith('Kind:') and not line_str.startswith('Language:'):
                clean_text = re.sub(r'<[^>]*>', '', line_str).strip()
                if clean_text and clean_text not in seen_texts:
                    seen_texts.add(clean_text)
                    formatted_lines.append(f"[{current_time_str}] {clean_text}")
                    current_time_str = None
    except Exception:
        pass
    return "\n".join(formatted_lines) if formatted_lines else None

def fetch_auto_transcript(yt_id, full_url):
    """Multi-tiered caption extraction engine bypassing cloud server blocks"""
    
    js_runtimes = get_js_runtime_config()
    js_args = ["--js-runtimes", ",".join(js_runtimes)] if js_runtimes else []

    # Non-interactive client configurations optimized for subtitle extraction without triggering bot checks
    client_configs = [
        ["--extractor-args", "youtube:player_client=tvhtml5,web"],
        ["--extractor-args", "youtube:player_client=mweb,web"],
        ["--extractor-args", "youtube:player_client=android_vr,ios"]
    ]

    vtt_prefix = f"caption_{yt_id}"

    for client_args in client_configs:
        try:
            # Clean up previous caption files
            for old_file in glob.glob(f"{vtt_prefix}*"):
                try: os.remove(old_file)
                except: pass

            cmd = [
                "yt-dlp",
                *js_args,
                *client_args,
                "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "--skip-download",
                "--write-auto-subs",
                "--write-subs",
                "--sub-langs", "en.*,en,en-US,en-GB",
                "--sub-format", "vtt",
                "-o", f"{vtt_prefix}.%(ext)s",
                full_url
            ]
            subprocess.run(cmd, capture_output=True, text=True, timeout=12)
            
            sub_files = glob.glob(f"{vtt_prefix}*.vtt")
            if sub_files:
                parsed_text = parse_vtt_subtitles(sub_files[0])
                for sf in sub_files:
                    try: os.remove(sf)
                    except: pass
                if parsed_text and len(parsed_text) > 50:
                    return parsed_text
        except Exception:
            continue

    # Tier 2: youtube-transcript-api fallback with fallback language handling
    try:
        try:
            transcript_list = YouTubeTranscriptApi.get_transcript(yt_id, languages=['en', 'en-US', 'en-GB', 'en-CA'])
        except (NoTranscriptFound, TranscriptsDisabled):
            # Try fetching any transcript listing available (including generated or translated)
            transcript_list = YouTubeTranscriptApi.list_transcripts(yt_id).find_transcript(['en']).fetch()

        if transcript_list:
            formatted_lines = []
            for line in transcript_list:
                start_sec = int(line['start'])
                hours = start_sec // 3600
                minutes = (start_sec % 3600) // 60
                seconds = start_sec % 60
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}" if hours > 0 else f"{minutes:02d}:{seconds:02d}"
                formatted_lines.append(f"[{time_str}] {line['text']}")
            return "\n".join(formatted_lines)
    except Exception:
        pass

    return None

def timestamp_to_seconds(ts_str):
    try:
        parts = str(ts_str).strip().split(':')
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(float(ts_str))
    except Exception:
        return 0

def download_and_crop_clip(video_url, start_sec, end_sec, output_filename="clip.mp4"):
    """Render and download video clip segment using yt-dlp + Google OAuth Device Login"""
    try:
        if os.path.exists(output_filename):
            os.remove(output_filename)

        js_runtimes = get_js_runtime_config()
        js_args = ["--js-runtimes", ",".join(js_runtimes)] if js_runtimes else []

        cookie_args = []
        cookie_file = get_cookie_file_path()
        browser = st.session_state.get('browser_cookie', 'None')
        
        # Validate browser cookie availability on host system
        browser_valid = False
        if browser and browser != "None":
            # Check if browser config path exists on Linux/Cloud hosts
            user_home = os.path.expanduser("~")
            browser_paths = {
                "chrome": os.path.join(user_home, ".config/google-chrome"),
                "firefox": os.path.join(user_home, ".mozilla/firefox"),
                "edge": os.path.join(user_home, ".config/microsoft-edge"),
                "brave": os.path.join(user_home, ".config/BraveSoftware")
            }
            if browser in browser_paths and os.path.exists(browser_paths[browser]):
                browser_valid = True

        if cookie_file:
            cookie_args = ["--cookies", cookie_file]
        elif browser_valid:
            cookie_args = ["--cookies-from-browser", browser]
        else:
            # Enable OAuth2 Google Sign-in flow natively in yt-dlp for cloud environments
            cookie_args = ["--username", "oauth2", "--password", ""]

        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"

        client_configs = [
            "youtube:player_client=tvhtml5,web",
            "youtube:player_client=android_vr,ios",
            "youtube:player_client=web_creator"
        ]

        stream_url = None
        last_error = ""

        # Step 1: Extract direct stream URL via yt-dlp -g with OAuth authentication support
        for client_opt in client_configs:
            cmd_get_url = [
                "yt-dlp",
                *js_args,
                *cookie_args,
                "--extractor-args", client_opt,
                "--user-agent", user_agent,
                "-g",
                "-f", "b[ext=mp4]/best[ext=mp4]/best",
                video_url
            ]
            res = subprocess.run(cmd_get_url, capture_output=True, text=True, timeout=35)
            if res.returncode == 0 and res.stdout.strip():
                stream_url = res.stdout.strip().split('\n')[0]
                break
            else:
                last_error = res.stderr

        # Step 2: Stream cut via FFmpeg
        if stream_url:
            duration = max(1, end_sec - start_sec)
            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-headers", f"User-Agent: {user_agent}\r\n",
                "-ss", str(start_sec),
                "-i", stream_url,
                "-t", str(duration),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                output_filename
            ]
            ffmpeg_res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)
            
            if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
                return True, output_filename
            else:
                last_error = ffmpeg_res.stderr

        # Step 3: Native yt-dlp fallback with OAuth support
        fallback_cmd = [
            "yt-dlp",
            *js_args,
            *cookie_args,
            "--extractor-args", "youtube:player_client=tvhtml5,web",
            "--user-agent", user_agent,
            "--download-sections", f"*{start_sec}-{end_sec}",
            "--force-keyframes-at-cuts",
            "-f", "b[ext=mp4]/best[ext=mp4]/best",
            "-o", output_filename,
            video_url
        ]
        fb_res = subprocess.run(fallback_cmd, capture_output=True, text=True, timeout=90)
        
        if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
            return True, output_filename
        else:
            last_error = fb_res.stderr

        return False, f"Auth Bypass Error: {last_error if last_error else 'Could not retrieve video stream.'}"
    except Exception as e:
        return False, str(e)

if video_url:
    yt_id = parse_youtube_id(video_url)
    video_title = fetch_youtube_metadata(yt_id) if yt_id else ""
    
    if 'seek_start' not in st.session_state:
        st.session_state['seek_start'] = 0

    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.subheader("📹 Video Stream Preview")
        if video_title:
            st.caption(f"📌 **Detected Title:** {video_title}")
        
        seek_sec = st.session_state.get('seek_start', 0)
        if yt_id:
            embed_url = f"https://www.youtube.com/embed/{yt_id}?start={seek_sec}&autoplay=1"
            st.markdown(
                f'<iframe width="100%" height="380" src="{embed_url}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen style="border-radius:12px;"></iframe>', 
                unsafe_allow_html=True
            )
        else:
            try:
                st.video(video_url, start_time=seek_sec)
            except Exception:
                st.info("Direct video preview unavailable.")
    
    with col2:
        st.subheader("📜 CAPTIONS & TRANSCRIPT ENGINE")
        
        # Auto-fetch captions button and status
        if 'transcript_data' not in st.session_state or st.session_state.get('current_yt_id') != yt_id:
            with st.spinner("⚡ Scraping YouTube captions using Android/Web Client..."):
                fetched_transcript = fetch_auto_transcript(yt_id, video_url) if yt_id else None
                st.session_state['transcript_data'] = fetched_transcript
                st.session_state['current_yt_id'] = yt_id
        else:
            fetched_transcript = st.session_state.get('transcript_data')

        if fetched_transcript:
            st.success("✅ Captions automatically scraped and timestamped!")
        else:
            st.warning("⚠️ Auto-caption fetch restricted by YouTube. Paste transcript below or click retry:")

        transcript_input = st.text_area(
            "Video / Podcast Timed Transcript:", 
            value=fetched_transcript if fetched_transcript else "",
            placeholder="[00:01:15] Spoken line 1...\n[01:45:22] Spoken line 2...",
            height=160
        )

        col_fetch, col_scan = st.columns(2)
        with col_fetch:
            if st.button("🔄 Force Re-Fetch Captions", use_container_width=True):
                with st.spinner("Re-extracting captions..."):
                    st.session_state['transcript_data'] = fetch_auto_transcript(yt_id, video_url)
                    st.rerun()

        with col_scan:
            analyze_btn = st.button("🔥 Deep-Scan & Align Clips", type="primary", use_container_width=True)
        
        if analyze_btn:
            if not api_key:
                st.error("⚠️ Gemini API Key missing! Add GEMINI_API_KEY in sidebar or secrets.")
            elif not transcript_input and not video_title:
                st.warning("Please provide transcript text or a valid video link.")
            else:
                with st.spinner("Scanning full timeline for viral highlights..."):
                    models_to_try = ["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-flash-latest"]
                    raw_text = None
                    last_error = None
                    
                    prompt = f"""
                    You are an expert short-form video editor and podcast strategist.
                    VIDEO TITLE: {video_title if video_title else "YouTube Podcast"}
                    
                    TIMED TRANSCRIPT:
                    {transcript_input if transcript_input else "Title: " + video_title}
                    
                    INSTRUCTIONS:
                    1. Read timestamped lines in bracket format like [MM:SS] or [HH:MM:SS] across the entire transcript.
                    2. Extract {max_clips} viral podcast clip highlights.
                    3. The "start" and "end" timestamps MUST match exact timestamps from the transcript.
                    4. The "hook" and "caption" MUST be word-for-word quotes spoken at that exact start timestamp.
                    
                    Return ONLY a JSON array of objects with these exact keys:
                    [
                      {{
                        "title": "Catchy Short Headline",
                        "score": 95,
                        "start": "MM:SS",
                        "end": "MM:SS",
                        "hook": "Exact quote spoken at start",
                        "reason": "Why this specific moment is viral",
                        "caption": "Subtitles spoken at start"
                      }}
                    ]
                    """
                    
                    for model_name in models_to_try:
                        try:
                            model = genai.GenerativeModel(model_name)
                            response = model.generate_content(prompt)
                            raw_text = response.text
                            if raw_text:
                                break
                        except Exception as e:
                            last_error = e

                    if raw_text:
                        json_match = re.search(r'\[.*\]', raw_text, re.DOTALL)
                        if json_match:
                            parsed_clips = json.loads(json_match.group(0))
                            st.session_state['clips'] = parsed_clips
                        else:
                            st.error("Could not parse JSON response from AI.")
                            st.code(raw_text)
                    else:
                        st.error(f"Gemini API Error: {str(last_error)}")

    if 'clips' in st.session_state and st.session_state['clips']:
        st.divider()
        st.subheader(f"✂️ Extracted Shorts for: {video_title if video_title else 'Your Video'}")
        
        for idx, clip in enumerate(st.session_state['clips']):
            with st.container():
                st.markdown(f"""
                <div class="stCard">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin:0; color:#38bdf8;">Clip #{idx+1}: {clip['title']}</h4>
                        <span class="score-badge">🔥 Virality: {clip.get('score', 90)}/100</span>
                    </div>
                    <p style="margin-top:10px; color:#cbd5e1;">⏱️ <b>Timestamp:</b> <span style="color:#facc15; font-weight:bold;">{clip['start']} ➔ {clip['end']}</span> | 💡 <b>Context:</b> {clip.get('reason', '')}</p>
                    <p style="color:#f472b6;"><b>Viral Hook:</b> "{clip.get('hook', '')}"</p>
                    <div style="background:#0f172a; padding:10px; border-radius:6px; font-family:monospace; color:#facc15;">
                        💬 Subtitles: {clip.get('caption', '')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    start_sec = timestamp_to_seconds(clip['start'])
                    if st.button(f"▶️ Play Segment ({clip['start']})", key=f"play_{idx}", use_container_width=True):
                        st.session_state['seek_start'] = start_sec
                        st.rerun()

                with c2:
                    if st.button(f"📥 Render & Download MP4", key=f"render_{idx}", use_container_width=True):
                        s_sec = timestamp_to_seconds(clip['start'])
                        e_sec = timestamp_to_seconds(clip['end'])
                        if e_sec <= s_sec:
                            e_sec = s_sec + 30
                        
                        with st.spinner(f"Rendering clip ({clip['start']} to {clip['end']})..."):
                            success, res = download_and_crop_clip(video_url, s_sec, e_sec, f"clip_{idx}.mp4")
                            if success:
                                st.success("✅ Clip rendered!")
                                with open(res, "rb") as file:
                                    st.download_button(
                                        label=f"💾 Save MP4 File ({clip['start']})",
                                        data=file,
                                        file_name=f"podcast_clip_{idx+1}_{clip['start'].replace(':','-')}.mp4",
                                        mime="video/mp4",
                                        key=f"dl_btn_{idx}"
                                    )
                            else:
                                st.error(f"Render Error: {res}")

                with c3:
                    st.markdown(f'''
                        <a href="https://www.capcut.com/editor" target="_blank" style="text-decoration:none;">
                            <button style="width:100%; background-color:#2563eb; color:white; border:none; padding:8px; border-radius:6px; font-weight:bold; cursor:pointer;">
                                🎬 Open in CapCut
                            </button>
                        </a>
                    ''', unsafe_allow_html=True)

else:
    st.info("👈 Paste a YouTube link or podcast URL above to begin scanning.")
