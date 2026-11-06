import streamlit as st
import google.generativeai as genai
import re
import json
import urllib.request
import subprocess
import os
import tempfile

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
    st.caption("Real AI Video Clipper & Transcript Analyzer")
    
    if not api_key:
        user_key = st.text_input("Gemini API Key", type="password", help="Enter key or set GEMINI_API_KEY in Streamlit Secrets")
        if user_key:
            api_key = user_key
            
    st.divider()
    aspect_ratio = st.selectbox("Framing / Aspect Ratio", ["9:16 Vertical (TikTok/Reels)", "1:1 Square (Instagram)", "16:9 Widescreen (YouTube)"])
    max_clips = st.slider("Max Clips to Extract", 3, 10, 5)

if api_key:
    genai.configure(api_key=api_key)

st.markdown('<p class="main-header">🎬 OpusCut AI Studio</p>', unsafe_allow_html=True)
st.caption("Auto-fetches timed transcripts to synchronize clip timestamps, text hooks, and subtitles.")
st.write("")

video_url = st.text_input("🔗 Paste YouTube Video Link:", placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ")

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

def parse_vtt_timestamps(vtt_content):
    """Parses raw VTT subtitle text into clean [MM:SS] format"""
    lines = vtt_content.splitlines()
    formatted = []
    seen = set()
    current_time = ""
    
    time_pattern = re.compile(r'(\d{2}):(\d{2}):(\d{2})\.\d{3}\s+-->')
    
    for line in lines:
        line = line.strip()
        if not line or line.startswith('WEBVTT') or line.startswith('Kind:') or line.startswith('Language:'):
            continue
            
        match = time_pattern.search(line)
        if match:
            hrs, mins, secs = match.groups()
            total_mins = int(hrs) * 60 + int(mins)
            current_time = f"{total_mins:02d}:{secs}"
            continue
            
        # Clean VTT tags like <c> or timestamps inside text
        clean_text = re.sub(r'<[^>]+>', '', line).strip()
        if clean_text and clean_text not in seen and not clean_text.isdigit():
            seen.add(clean_text)
            formatted.append(f"[{current_time}] {clean_text}")
            
    return "\n".join(formatted)

def fetch_auto_transcript_ytdlp(url):
    """Extracts YouTube subtitles reliably using yt-dlp on cloud servers"""
    try:
        temp_dir = tempfile.gettempdir()
        out_tmpl = os.path.join(temp_dir, "caption_extract")
        
        # Command to dump subtitles using yt-dlp
        cmd = [
            "yt-dlp",
            "--write-auto-sub",
            "--write-sub",
            "--sub-lang", "en",
            "--sub-format", "vtt",
            "--skip-download",
            "-o", out_tmpl,
            url
        ]
        
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        
        # Look for output file
        expected_vtt = out_tmpl + ".en.vtt"
        if not os.path.exists(expected_vtt):
            for file in os.listdir(temp_dir):
                if file.startswith("caption_extract") and file.endswith(".vtt"):
                    expected_vtt = os.path.join(temp_dir, file)
                    break
                    
        if os.path.exists(expected_vtt):
            with open(expected_vtt, "r", encoding="utf-8") as f:
                vtt_data = f.read()
            os.remove(expected_vtt)
            return parse_vtt_timestamps(vtt_data)
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
        return int(ts_str)
    except Exception:
        return 0

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
        st.subheader("📜 TIMED TRANSCRIPT EXTRACTION")
        
        fetched_transcript = None
        if yt_id:
            with st.spinner("Bypassing cloud blocks & pulling video transcript..."):
                fetched_transcript = fetch_auto_transcript_ytdlp(video_url)
        
        if fetched_transcript:
            st.success("✅ Real timed transcript auto-detected from YouTube!")
        else:
            st.warning("⚠️ Captions not found or disabled on video. You can paste a transcript below:")

        transcript_input = st.text_area(
            "Video Timed Transcript:", 
            value=fetched_transcript if fetched_transcript else "",
            placeholder="[01:15] Spoken line 1...\n[01:45] Spoken line 2...",
            height=160
        )
        
        analyze_btn = st.button(f"🔥 Deep-Scan & Align Clips", type="primary", use_container_width=True)
        
        if analyze_btn:
            if not api_key:
                st.error("⚠️ Gemini API Key missing! Add GEMINI_API_KEY to Streamlit secrets or paste it in the sidebar.")
            elif not transcript_input and not video_title:
                st.warning("Please paste a transcript or context text into the text area above so Gemini can analyze the real video content.")
            else:
                with st.spinner(f"Matching exact timestamps and subtitles..."):
                    models_to_try = ["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-flash-latest"]
                    raw_text = None
                    last_error = None
                    
                    prompt = f"""
                    You are an expert video editor.
                    VIDEO TITLE: {video_title if video_title else "User Video"}
                    
                    TIMED TRANSCRIPT (Use ONLY these exact timestamps and text):
                    {transcript_input[:15000] if transcript_input else "Title: " + video_title}
                    
                    CRITICAL REQUIREMENT:
                    1. Read the timestamps inside bracket format like [MM:SS] in the transcript above.
                    2. Choose {max_clips} viral moments from DIFFERENT parts of the video.
                    3. The "start" and "end" MUST match the exact [MM:SS] timestamps where that specific text is spoken in the transcript.
                    4. The "hook" and "caption" MUST be word-for-word quotes from the transcript at that EXACT start timestamp.
                    
                    Return ONLY a JSON array of objects with these exact keys:
                    [
                      {{
                        "title": "Short Catchy Headline",
                        "score": 95,
                        "start": "MM:SS",
                        "end": "MM:SS",
                        "hook": "Exact quote spoken at start timestamp",
                        "reason": "Why this specific section of the transcript is viral",
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
        st.subheader(f"✂️ Extracted Clips for: {video_title if video_title else 'Your Video'}")
        
        for idx, clip in enumerate(st.session_state['clips']):
            with st.container():
                st.markdown(f"""
                <div class="stCard">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin:0; color:#38bdf8;">Clip #{idx+1}: {clip['title']}</h4>
                        <span class="score-badge">🔥 Virality: {clip.get('score', 90)}/100</span>
                    </div>
                    <p style="margin-top:10px; color:#cbd5e1;">⏱️ <b>Exact Video Timestamp:</b> <span style="color:#facc15; font-weight:bold;">{clip['start']} ➔ {clip['end']}</span> | 💡 <b>Context:</b> {clip.get('reason', '')}</p>
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
                    st.markdown(f'''
                        <a href="https://cobalt.tools" target="_blank" style="text-decoration:none;">
                            <button style="width:100%; background-color:#16a34a; color:white; border:none; padding:8px; border-radius:6px; font-weight:bold; cursor:pointer;">
                                ⚡ Export Clip Segment ({clip['start']})
                            </button>
                        </a>
                    ''', unsafe_allow_html=True)

                with c3:
                    st.markdown('''
                        <a href="https://www.capcut.com/editor" target="_blank" style="text-decoration:none;">
                            <button style="width:100%; background-color:#2563eb; color:white; border:none; padding:8px; border-radius:6px; font-weight:bold; cursor:pointer;">
                                🎬 Edit in CapCut
                            </button>
                        </a>
                    ''', unsafe_allow_html=True)

else:
    st.info("👈 Paste a YouTube link above to begin.")
