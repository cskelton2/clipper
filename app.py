import streamlit as st
import google.generativeai as genai
import re
import json
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
    st.caption("AI Video Clipper & Virality Analyzer")
    
    if not api_key:
        user_key = st.text_input("Gemini API Key", type="password", help="Enter key or set GEMINI_API_KEY in Streamlit Secrets")
        if user_key:
            api_key = user_key
            
    st.divider()
    aspect_ratio = st.selectbox("Framing / Aspect Ratio", ["9:16 Vertical (TikTok/Reels)", "1:1 Square (Instagram)", "16:9 Widescreen (YouTube)"])
    caption_style = st.selectbox("Subtitle Style", ["Bold Yellow Highlight", "Neon Purple Box", "Minimal White Clean"])
    max_clips = st.slider("Max Clips to Extract", 3, 15, 10)
    scan_focus = st.selectbox("Scan Focus", ["Entire Video Timeline", "Mid-Video Climax & Spikes", "Ending Takeaways & Recaps"])

if api_key:
    genai.configure(api_key=api_key)

st.markdown('<p class="main-header">🎬 OpusCut AI Studio</p>', unsafe_allow_html=True)
st.caption("Extract viral clips with real AI timestamp analysis directly from web video links.")
st.write("")

video_url = st.text_input("🔗 Paste YouTube Video Link:", placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ")

def parse_youtube_id(url):
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

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
    
    if 'seek_start' not in st.session_state:
        st.session_state['seek_start'] = 0

    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.subheader("📹 Video Stream Preview")
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
        st.subheader("🔍 REAL AI TIMELINE SCANNER")
        
        video_topic_context = st.text_area(
            "Video Description / Transcript Text (Optional)", 
            placeholder="Paste text/transcript here to help Gemini pinpoint exact moments if the video is restricted...",
            height=100
        )
        
        analyze_btn = st.button(f"🔥 Deep Scan Video for Top {max_clips} Clips", type="primary", use_container_width=True)
        
        if analyze_btn:
            if not api_key:
                st.error("⚠️ Gemini API Key missing! Add GEMINI_API_KEY to Streamlit secrets or paste it in the sidebar.")
            else:
                with st.spinner(f"Analyzing video content & extracting {max_clips} real viral highlights..."):
                    # Dynamic model fallback handler to guarantee compatibility
                    models_to_try = ["gemini-2.5-flash", "gemini-3-flash-preview", "gemini-flash-latest"]
                    raw_text = None
                    last_error = None
                    
                    prompt = f"""
                    You are an expert video clipper (like Opus Pro). 
                    Analyze this YouTube Video link: {video_url}
                    
                    Additional Context/Transcript provided: 
                    {video_topic_context if video_topic_context else "None provided. Analyze the topic based on the link and title."}
                    
                    Focus Target: {scan_focus}
                    
                    Extract EXACTLY {max_clips} highly engaging viral clip segments.
                    
                    CRITICAL INSTRUCTIONS:
                    1. Do NOT give fake or hardcoded static timestamps. Estimate real timestamps based on key plot points, narrative climaxes, and topic transitions across the whole video.
                    2. Spread the clips out across the video timeline according to the Focus Target.
                    3. Return ONLY a valid JSON array.
                    
                    Required JSON format:
                    [
                      {{
                        "title": "Catchy Short Title",
                        "score": 95,
                        "start": "MM:SS",
                        "end": "MM:SS",
                        "hook": "Exact opening line or key phrase that hooks the viewer",
                        "reason": "Why this timestamp section is high retention",
                        "caption": "Karaoke subtitle preview text"
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
                            st.session_state['scan_error'] = None
                        else:
                            st.error("Could not parse JSON output from AI. Raw response received:")
                            st.code(raw_text)
                    else:
                        st.error(f"Gemini API Error: {str(last_error)}")

    if 'clips' in st.session_state and st.session_state['clips']:
        st.divider()
        st.subheader(f"✂️ Extracted Viral Clips ({len(st.session_state['clips'])} Highlights)")
        
        for idx, clip in enumerate(st.session_state['clips']):
            with st.container():
                st.markdown(f"""
                <div class="stCard">
                    <div style="display: flex; justify-space-between; align-items: center;">
                        <h4 style="margin:0; color:#38bdf8;">Clip #{idx+1}: {clip['title']}</h4>
                        <span class="score-badge">🔥 Virality: {clip.get('score', 90)}/100</span>
                    </div>
                    <p style="margin-top:10px; color:#cbd5e1;">⏱️ <b>Timestamp:</b> <span style="color:#facc15; font-weight:bold;">{clip['start']} ➔ {clip['end']}</span> | 💡 <b>AI Pick Reason:</b> {clip.get('reason', 'High engagement peak')}</p>
                    <p style="color:#f472b6;"><b>Viral Hook:</b> "{clip.get('hook', '')}"</p>
                    <div style="background:#0f172a; padding:10px; border-radius:6px; font-family:monospace; color:#facc15;">
                        💬 Subtitle Preview: {clip.get('caption', '')}
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
    st.info("👈 Paste a YouTube link above and click Deep Scan to start!")
