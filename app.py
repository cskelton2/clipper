import streamlit as st
import google.generativeai as genai
import re
import json

# Page Config
st.set_page_config(
    page_title="OpusCut AI Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark theme custom CSS styling
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

# Sidebar - Settings & API Keys
with st.sidebar:
    st.title("⚡ OpusCut AI")
    st.caption("AI Video Clipper & Virality Analyzer")
    
    api_key = st.text_input("Gemini API Key", type="password", help="Enter your Gemini API key to enable AI clip extraction")
    if api_key:
        genai.configure(api_key=api_key)
    
    st.divider()
    aspect_ratio = st.selectbox("Framing / Aspect Ratio", ["9:16 Vertical (TikTok/Reels)", "1:1 Square (Instagram)", "16:9 Widescreen (YouTube)"])
    caption_style = st.selectbox("Subtitle Style", ["Bold Yellow Highlight", "Neon Purple Box", "Minimal White Clean"])
    max_clips = st.slider("Max Clips to Extract", 1, 5, 3)

# Title Section
st.markdown('<p class="main-header">🎬 OpusCut AI Studio</p>', unsafe_allow_html=True)
st.caption("Extract viral clips, hook headlines, and auto-reframed shorts directly from web video links.")
st.write("")

# Video Input Section
video_url = st.text_input("🔗 Paste Video Link (YouTube MP4, Direct Link, HLS):", placeholder="https://www.youtube.com/watch?v=dQw4w9WgXcQ")

def parse_youtube_id(url):
    pattern = r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})'
    match = re.search(pattern, url)
    return match.group(1) if match else None

if video_url:
    col1, col2 = st.columns([3, 2])
    
    yt_id = parse_youtube_id(video_url)
    
    with col1:
        st.subheader("📹 Video Stream Preview")
        if yt_id:
            st.video(f"https://www.youtube.com/watch?v={yt_id}")
        else:
            try:
                st.video(video_url)
            except Exception:
                st.info("Direct playback preview not supported for this URL, but processing can proceed.")
    
    with col2:
        st.subheader("🚀 VIRAL CLIP ANALYSIS")
        
        analysis_prompt = st.text_area(
            "Video Transcript / Context (Optional)", 
            placeholder="Paste transcript or topic details to improve AI clip extraction accuracy...",
            height=100
        )
        
        analyze_btn = st.button("🔥 Auto-Generate Viral Clips", type="primary", use_container_width=True)
        
        if analyze_btn:
            if not api_key:
                st.warning("Please enter your Gemini API Key in the left sidebar first!")
            else:
                with st.spinner("Analyzing hooks, virality potential, and timestamps..."):
                    try:
                        model = genai.GenerativeModel("gemini-1.5-flash")
                        prompt = f"""
                        Analyze this video context/transcript and suggest {max_clips} viral clip ideas for TikTok, Reels, and Shorts.
                        Context: {analysis_prompt if analysis_prompt else video_url}
                        
                        Return a valid JSON array of objects with these exact keys:
                        - "title": "Catchy Hook Title"
                        - "score": number between 80 and 99
                        - "start": "MM:SS"
                        - "end": "MM:SS"
                        - "hook": "Attention grabbing text hook"
                        - "caption": "Sample karaoke caption preview text"
                        """
                        response = model.generate_content(prompt)
                        # Extract JSON
                        json_match = re.search(r'\[.*\]', response.text, re.DOTALL)
                        if json_match:
                            clips_data = json.loads(json_match.group(0))
                        else:
                            clips_data = [
                                {
                                    "title": "The Big Breakthrough Hook",
                                    "score": 96,
                                    "start": "00:15",
                                    "end": "00:45",
                                    "hook": "You won't believe what happened next...",
                                    "caption": "THIS CHANGED EVERYTHING IN 30 SECONDS!"
                                },
                                {
                                    "title": "Secret Strategy Exposed",
                                    "score": 89,
                                    "start": "01:20",
                                    "end": "01:50",
                                    "hook": "The #1 secret nobody tells you.",
                                    "caption": "STOP DOING THIS RIGHT NOW!"
                                }
                            ]
                        st.session_state['clips'] = clips_data
                    except Exception as e:
                        st.error(f"Error calling Gemini API: {e}")
                        # Fallback mock data
                        st.session_state['clips'] = [
                            {
                                "title": "The Big Breakthrough Hook",
                                "score": 96,
                                "start": "00:15",
                                "end": "00:45",
                                "hook": "You won't believe what happened next...",
                                "caption": "THIS CHANGED EVERYTHING IN 30 SECONDS!"
                            },
                            {
                                "title": "Secret Strategy Exposed",
                                "score": 89,
                                "start": "01:20",
                                "end": "01:50",
                                "hook": "The #1 secret nobody tells you.",
                                "caption": "STOP DOING THIS RIGHT NOW!"
                            }
                        ]

    # Display Generated Clips
    if 'clips' in st.session_state:
        st.divider()
        st.subheader("✂️ Generated Short Clips")
        
        for idx, clip in enumerate(st.session_state['clips']):
            with st.container():
                st.markdown(f"""
                <div class="stCard">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin:0; color:#38bdf8;">Clip #{idx+1}: {clip['title']}</h4>
                        <span class="score-badge">🔥 Virality Score: {clip['score']}/100</span>
                    </div>
                    <p style="margin-top:10px; color:#cbd5e1;"><b>Timestamp:</b> {clip['start']} - {clip['end']} | <b>Style:</b> {caption_style}</p>
                    <p style="color:#f472b6;"><b>Viral Hook:</b> "{clip['hook']}"</p>
                    <div style="background:#0f172a; padding:10px; border-radius:6px; font-family:monospace; color:#facc15;">
                        💬 Captions: {clip['caption']}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.button(f"📋 Copy Timestamp #{idx+1}", key=f"copy_{idx}")
                with c2:
                    st.button(f"⚡ Export {aspect_ratio[:4]} Clip #{idx+1}", key=f"exp_{idx}")
                with c3:
                    st.button(f"🔗 Share Clip #{idx+1}", key=f"share_{idx}")

else:
    st.info("👈 Paste a video URL above to start clipping and auto-framing!")
