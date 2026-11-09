import streamlit as st
import google.generativeai as genai
import re
import json
import urllib.request
import os
import subprocess
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

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

if api_key:
    genai.configure(api_key=api_key)

st.markdown('<p class="main-header">🎬 OpusCut AI Studio</p>', unsafe_allow_html=True)
st.caption("Supports full-length podcasts up to 3+ hours with exact timed transcript alignment and in-app MP4 clipping.")
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
    """Helper to parse VTT subtitle files downloaded via yt-dlp into timestamped text lines"""
    formatted_lines = []
    try:
        with open(vtt_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        time_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.,](\d{3})')
        current_time_str = None
        
        for line in lines:
            line_str = line.strip()
            match = time_pattern.search(line_str)
            if match:
                hours, minutes, seconds = int(match.group(1)), int(match.group(2)), int(match.group(3))
                if hours > 0:
                    current_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    current_time_str = f"{minutes:02d}:{seconds:02d}"
            elif current_time_str and line_str and not '-->' in line_str and not line_str.isdigit():
                clean_text = re.sub(r'<[^>]*>', '', line_str)
                formatted_lines.append(f"[{current_time_str}] {clean_text}")
                current_time_str = None
    except Exception:
        pass
    return "\n".join(formatted_lines) if formatted_lines else None

def fetch_auto_transcript(yt_id, full_url):
    """Primary: youtube-transcript-api. Fallback: yt-dlp VTT subtitle extraction for cloud bypass"""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(yt_id, languages=['en', 'en-US', 'en-GB'])
        formatted_lines = []
        for line in transcript_list:
            start_sec = int(line['start'])
            hours = start_sec // 3600
            minutes = (start_sec % 3600) // 60
            seconds = start_sec % 60
            if hours > 0:
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                time_str = f"{minutes:02d}:{seconds:02d}"
            formatted_lines.append(f"[{time_str}] {line['text']}")
        return "\n".join(formatted_lines)
    except Exception:
        pass

    try:
        vtt_base = f"sub_{yt_id}"
        cmd = [
            "yt-dlp",
            "--extractor-args", "youtube:player_client=ios,web",
            "--user-agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "--skip-download",
            "--write-auto-subs",
            "--sub-lang", "en",
            "-o", vtt_base,
            full_url
        ]
        subprocess.run(cmd, capture_output=True, text=True)
        
        for ext in ['.en.vtt', '.vtt']:
            target_file = vtt_base + ext
            if os.path.exists(target_file):
                parsed = parse_vtt_subtitles(target_file)
                os.remove(target_file)
                if parsed:
                    return parsed
    except Exception:
        pass

    return None

def timestamp_to_seconds(ts_str):
    try:
        parts = ts_str.strip().split(':')
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(float(ts_str))
    except Exception:
        return 0

def download_and_crop_clip(video_url, start_sec, end_sec, output_filename="clip.mp4"):
    """Uses yt-dlp with iOS/web client emulation flags and ffmpeg to cut exact video segments"""
    try:
        if os.path.exists(output_filename):
            os.remove(output_filename)

        cmd = [
            "yt-dlp",
            "--extractor-args", "youtube:player_client=ios,web",
            "--user-agent", "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            "-f", "b/best",
            "--download-sections", f"*{start_sec}-{end_sec}",
            "--no-check-certificates",
            "-o", output_filename,
            video_url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return False, f"yt-dlp Error: {result.stderr}"
            
        if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
            return True, output_filename
        else:
            return False, "Rendered file is missing or empty."
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
            st.caption(f"📌 **Detected Video Title:** {video_title}")
        
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
                st.info("Direct preview unavailable.")
    
    with col2:
        st.subheader("📜 FULL-SPAN PODCAST TRANSCRIPT")
        
        fetched_transcript = fetch_auto_transcript(yt_id, video_url) if yt_id else None
        
        if fetched_transcript:
            st.success("✅ Real timed transcript auto-detected (Supports up to 3+ hours)!")
        else:
            st.warning("⚠️ Could not auto-grab YouTube captions. Paste transcript below to guarantee exact timestamp matching:")

        transcript_input = st.text_area(
            "Video / Podcast Timed Transcript:", 
            value=fetched_transcript if fetched_transcript else "",
            placeholder="[00:01:15] Spoken line 1...\n[01:45:22] Spoken line 2...",
            height=160
        )
        
        analyze_btn = st.button(f"🔥 Deep-Scan & Align Full Podcast Clips", type="primary", use_container_width=True)
        
        if analyze_btn:
            if not api_key:
                st.error("⚠️ Gemini API Key missing! Add GEMINI_API_KEY to Streamlit secrets or paste it in the sidebar.")
            elif not transcript_input and not video_title:
                st.warning("Please provide transcript text or a video title.")
            else:
                with st.spinner(f"Analyzing multi-hour podcast timeline across full duration..."):
                    models_to_try = ["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-flash-latest"]
                    raw_text = None
                    last_error = None
                    
                    prompt = f"""
                    You are an expert podcast editor and viral content strategist.
                    VIDEO TITLE: {video_title if video_title else "Podcast Episode"}
                    
                    TIMED TRANSCRIPT (Spanning full length up to 3 hours):
                    {transcript_input if transcript_input else "Title: " + video_title}
                    
                    CRITICAL REQUIREMENTS:
                    1. Read timestamps in bracket format like [MM:SS] or [HH:MM:SS] across the ENTIRE duration (early, middle, and late hours).
                    2. Choose {max_clips} viral podcast highlights distributed evenly across the full length.
                    3. The "start" and "end" MUST match exact bracketed timestamps from the transcript.
                    4. The "hook" and "caption" MUST be word-for-word quotes from the transcript at that EXACT start timestamp.
                    
                    Return ONLY a JSON array of objects with these exact keys:
                    [
                      {{
                        "title": "Short Catchy Headline",
                        "score": 95,
                        "start": "MM:SS",
                        "end": "MM:SS",
                        "hook": "Exact quote spoken at start timestamp",
                        "reason": "Why this specific podcast section is viral",
                        "caption": "Subtitles spoken at this exact timestamp"
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
                            st.error("Could not parse JSON response from AI:")
                            st.code(raw_text)
                    else:
                        st.error(f"Gemini API Error: {str(last_error)}")

    if 'clips' in st.session_state and st.session_state['clips']:
        st.divider()
        st.subheader(f"✂️ Extracted Podcast Clips for: {video_title if video_title else 'Your Video'}")
        
        for idx, clip in enumerate(st.session_state['clips']):
            with st.container():
                st.markdown(f"""
                <div class="stCard">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin:0; color:#38bdf8;">Clip #{idx+1}: {clip['title']}</h4>
                        <span class="score-badge">🔥 Virality: {clip.get('score', 90)}/100</span>
                    </div>
                    <p style="margin-top:10px; color:#cbd5e1;">⏱️ <b>Exact Timestamp:</b> <span style="color:#facc15; font-weight:bold;">{clip['start']} ➔ {clip['end']}</span> | 💡 <b>Context:</b> {clip.get('reason', '')}</p>
                    <p style="color:#f472b6;"><b>Viral Hook:</b> "{clip.get('hook', '')}"</p>
                    <div style="background:#0f172a; padding:10px; border-radius:6px; font-family:monospace; color:#facc15;">
                        💬 Subtitles: {clip.get('caption', '')}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    start_sec = timestamp_to_seconds(clip['start'])
                    if st.button(f"▶️ Jump & Play ({clip['start']})", key=f"play_{idx}", use_container_width=True):
                        st.session_state['seek_start'] = start_sec
                        st.rerun()

                with c2:
                    if st.button(f"📥 Render & Download MP4", key=f"render_{idx}", use_container_width=True):
                        s_sec = timestamp_to_seconds(clip['start'])
                        e_sec = timestamp_to_seconds(clip['end'])
                        if e_sec <= s_sec:
                            e_sec = s_sec + 30
                        
                        with st.spinner(f"Slicing clip from {clip['start']} to {clip['end']}..."):
                            success, res = download_and_crop_clip(video_url, s_sec, e_sec, f"clip_{idx}.mp4")
                            if success:
                                st.success("✅ Clip rendered successfully!")
                                with open(res, "rb") as file:
                                    st.download_button(
                                        label=f"💾 Save MP4 File ({clip['start']})",
                                        data=file,
                                        file_name=f"podcast_clip_{idx+1}_{clip['start'].replace(':','-')}.mp4",
                                        mime="video/mp4",
                                        key=f"dl_btn_{idx}"
                                    )
                            else:
                                st.error(f"Failed to extract video clip segment: {res}")

                with c3:
                    st.markdown(f'''
                        <a href="https://www.capcut.com/editor" target="_blank" style="text-decoration:none;">
                            <button style="width:100%; background-color:#2563eb; color:white; border:none; padding:8px; border-radius:6px; font-weight:bold; cursor:pointer;">
                                🎬 Edit in CapCut
                            </button>
                        </a>
                    ''', unsafe_allow_html=True)

else:
    st.info("👈 Paste a YouTube link or podcast URL above to begin full-length scanning.")
