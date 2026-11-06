import streamlit as st
import google.generativeai as genai
import re
import json
import urllib.request
import os
import subprocess
import asyncio
from urllib.parse import quote

# ---------------------------------------------------------------------------
# Page config & styling
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="OpusCut AI Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .stApp { background-color: #0d0f17; color: #f1f5f9; }
    .main-header {
        font-size: 2.2rem; font-weight: 800;
        background: linear-gradient(90deg, #a855f7 0%, #ec4899 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .stCard {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px; padding: 20px; margin-bottom: 15px;
    }
    .score-badge {
        background: linear-gradient(135deg, #a855f7, #ec4899);
        color: white; padding: 4px 10px; border-radius: 20px;
        font-weight: bold; font-size: 0.85rem;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Safe secret reader
# ---------------------------------------------------------------------------
def _secret(key, default=None):
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return default


def get_api_key():
    return _secret("GEMINI_API_KEY")


# ---------------------------------------------------------------------------
# Transcript fetching: yt-transcript-pro → proxy API → direct API → yt-dlp
# ---------------------------------------------------------------------------
def _format_seconds_to_timestamp(seconds):
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def _try_yt_transcript_pro(video_url):
    """
    yt-transcript-pro v2 cascades watch → yt-dlp → legacy API.
    Designed to bypass IP blocks without proxies.
    """
    try:
        from yt_transcript_pro import extract_transcript  # type: ignore

        async def _run():
            return await extract_transcript(video_url, languages=["en"])

        raw = asyncio.run(_run())

        # Normalise whatever format the library returns into [MM:SS] text lines
        lines = []
        if hasattr(raw, "segments"):
            for seg in raw.segments:
                start = getattr(seg, "start", 0)
                text = getattr(seg, "text", "").strip()
                if text:
                    lines.append(f"[{_format_seconds_to_timestamp(start)}] {text}")
        elif isinstance(raw, list):
            for item in raw:
                start = item.get("start", 0) if isinstance(item, dict) else getattr(item, "start", 0)
                text = item.get("text", "") if isinstance(item, dict) else getattr(item, "text", "")
                if text:
                    lines.append(f"[{_format_seconds_to_timestamp(start)}] {text.strip()}")
        elif isinstance(raw, str):
            return raw

        return "\n".join(lines) if lines else None
    except Exception:
        return None


def _try_youtube_transcript_api(video_id, use_proxy=True):
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.proxies import GenericProxyConfig  # type: ignore
    except ImportError:
        return None

    if use_proxy:
        username = _secret("WEBSHARE_USERNAME")
        password = _secret("WEBSHARE_PASSWORD")
        if not (username and password):
            return None
        host = str(_secret("WEBSHARE_HOST", "p.webshare.io"))
        port = str(_secret("WEBSHARE_PORT", "80"))
        proxy_url = (
            f"http://{quote(str(username), safe='')}:"
            f"{quote(str(password), safe='')}@{host}:{port}"
        )
        api = YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(http_url=proxy_url, https_url=proxy_url)
        )
    else:
        api = YouTubeTranscriptApi()

    try:
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        lines = []
        for snippet in fetched:
            start = getattr(snippet, "start", 0)
            text = getattr(snippet, "text", "").strip()
            if text:
                lines.append(f"[{_format_seconds_to_timestamp(start)}] {text}")
        return "\n".join(lines) if lines else None
    except Exception:
        return None


def _try_ytdlp(video_url, video_id):
    vtt_base = f"sub_{video_id}"
    cookies_file = None

    cookies_text = _secret("YOUTUBE_COOKIES")
    if cookies_text:
        cookies_file = f"cookies_{video_id}.txt"
        with open(cookies_file, "w", encoding="utf-8") as f:
            f.write(cookies_text)

    try:
        cmd = [
            "yt-dlp",
            "--impersonate", "chrome",  # TLS fingerprint mimicry helps on cloud IPs
            "--extractor-args", "youtube:player_client=ios,web,android",
            "--user-agent",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
            "Mobile/15E148 Safari/604.1",
            "--skip-download",
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", "en,en-US,en-GB",
            "--sub-format", "vtt",
            "-o", vtt_base,
            video_url,
        ]
        if cookies_file:
            cmd.extend(["--cookies", cookies_file])

        subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        for filename in os.listdir("."):
            if filename.startswith(vtt_base) and filename.endswith(".vtt"):
                parsed = _parse_vtt(filename)
                try:
                    os.remove(filename)
                except OSError:
                    pass
                if parsed:
                    return parsed
    except Exception:
        pass
    finally:
        if cookies_file and os.path.exists(cookies_file):
            try:
                os.remove(cookies_file)
            except OSError:
                pass
    return None


def _parse_vtt(vtt_path):
    formatted_lines = []
    try:
        with open(vtt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        time_pattern = re.compile(
            r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})\s*-->\s*"
            r"(\d{2}):(\d{2}):(\d{2})[.,](\d{3})"
        )
        current_time_str = None
        for line in lines:
            line_str = line.strip()
            match = time_pattern.search(line_str)
            if match:
                h, m, s = int(match.group(1)), int(match.group(2)), int(match.group(3))
                current_time_str = (
                    f"{h:02d}:{m:02d}:{s:02d}" if h > 0 else f"{m:02d}:{s:02d}"
                )
            elif (
                current_time_str
                and line_str
                and "-->" not in line_str
                and not line_str.isdigit()
                and not line_str.upper().startswith("WEBVTT")
            ):
                clean_text = re.sub(r"<[^>]*>", "", line_str)
                formatted_lines.append(f"[{current_time_str}] {clean_text}")
                current_time_str = None
    except Exception:
        pass
    return "\n".join(formatted_lines) if formatted_lines else None


def fetch_auto_transcript(video_url, video_id):
    """
    Four-tier cascade:
    1. yt-transcript-pro (cloud-optimised, no proxy needed)
    2. youtube-transcript-api via GenericProxyConfig (if proxy configured)
    3. youtube-transcript-api direct
    4. yt-dlp with --impersonate chrome
    """
    # 1. yt-transcript-pro
    result = _try_yt_transcript_pro(video_url)
    if result:
        return result

    # 2. proxy API (only if configured and not already failed this session)
    if not st.session_state.get("proxy_failed", False) and _secret("WEBSHARE_USERNAME"):
        result = _try_youtube_transcript_api(video_id, use_proxy=True)
        if result:
            return result
        st.session_state["proxy_failed"] = True

    # 3. direct API
    result = _try_youtube_transcript_api(video_id, use_proxy=False)
    if result:
        return result

    # 4. yt-dlp
    return _try_ytdlp(video_url, video_id)


# ---------------------------------------------------------------------------
# Metadata, timestamp, and clip utilities (unchanged)
# ---------------------------------------------------------------------------
def parse_youtube_id(url):
    pattern = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    match = re.search(pattern, url)
    return match.group(1) if match else None


def fetch_youtube_metadata(yt_id):
    try:
        oembed_url = (
            f"https://www.youtube.com/oembed?"
            f"url=https://www.youtube.com/watch?v={yt_id}&format=json"
        )
        req = urllib.request.urlopen(oembed_url, timeout=10)
        data = json.loads(req.read().decode())
        return data.get("title", "")
    except Exception:
        return ""


def timestamp_to_seconds(ts_str):
    try:
        parts = ts_str.strip().split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        return int(float(ts_str))
    except Exception:
        return 0


def download_and_crop_clip(video_url, start_sec, end_sec, output_filename="clip.mp4"):
    try:
        if os.path.exists(output_filename):
            os.remove(output_filename)
        cmd = [
            "yt-dlp",
            "--extractor-args", "youtube:player_client=ios,web",
            "--user-agent",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
            "Mobile/15E148 Safari/604.1",
            "-f", "b/best",
            "--download-sections", f"*{start_sec}-{end_sec}",
            "--no-check-certificates",
            "-o", output_filename,
            video_url,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return False, f"yt-dlp Error: {result.stderr}"
        if os.path.exists(output_filename) and os.path.getsize(output_filename) > 0:
            return True, output_filename
        return False, "Rendered file is missing or empty."
    except Exception as e:
        return False, str(e)


# ---------------------------------------------------------------------------
# Sidebar & main UI
# ---------------------------------------------------------------------------
api_key = get_api_key()

with st.sidebar:
    st.title("⚡ OpusCut AI")
    st.caption("Real AI Video Clipper & 3-Hour Podcast Analyzer")

    if not api_key:
        user_key = st.text_input(
            "Gemini API Key",
            type="password",
            help="Enter key or set GEMINI_API_KEY in Streamlit Secrets",
        )
        if user_key:
            api_key = user_key

    st.divider()

    if _secret("WEBSHARE_USERNAME"):
        if st.session_state.get("proxy_failed"):
            st.error("🚫 Proxy authentication failed. Skipping proxy this session.")
            if st.button("🔄 Reset proxy state", use_container_width=True):
                st.session_state["proxy_failed"] = False
                st.rerun()
        else:
            st.success("🌐 Proxy configured")
    else:
        st.info("ℹ️ No proxy configured — using yt-transcript-pro cascade + yt-dlp")

    aspect_ratio = st.selectbox(
        "Framing / Aspect Ratio",
        [
            "9:16 Vertical (TikTok/Reels)",
            "1:1 Square (Instagram)",
            "16:9 Widescreen (YouTube)",
        ],
    )
    max_clips = st.slider("Max Clips to Extract", 3, 20, 8)

if api_key:
    genai.configure(api_key=api_key)

st.markdown('<p class="main-header">🎬 OpusCut AI Studio</p>', unsafe_allow_html=True)
st.caption(
    "Supports full-length podcasts up to 3+ hours with exact timed "
    "transcript alignment and in-app MP4 clipping."
)
st.write("")

video_url = st.text_input(
    "🔗 Paste YouTube Video or Podcast Link:",
    placeholder="https://www.youtube.com/watch?v=...",
)

if video_url:
    yt_id = parse_youtube_id(video_url)
    video_title = fetch_youtube_metadata(yt_id) if yt_id else ""

    if "seek_start" not in st.session_state:
        st.session_state["seek_start"] = 0

    col1, col2 = st.columns([3, 2])

    with col1:
        st.subheader("📹 Video Stream Preview")
        if video_title:
            st.caption(f"📌 **Detected Video Title:** {video_title}")
        seek_sec = st.session_state.get("seek_start", 0)
        if yt_id:
            embed_url = (
                f"https://www.youtube.com/embed/{yt_id}"
                f"?start={seek_sec}&autoplay=1"
            )
            st.markdown(
                f'<iframe width="100%" height="380" src="{embed_url}" '
                f'frameborder="0" allow="accelerometer; autoplay; clipboard-write; '
                f'encrypted-media; gyroscope; picture-in-picture" allowfullscreen '
                f'style="border-radius:12px;"></iframe>',
                unsafe_allow_html=True,
            )
        else:
            try:
                st.video(video_url, start_time=seek_sec)
            except Exception:
                st.info("Direct preview unavailable.")

    with col2:
        st.subheader("📜 FULL-SPAN PODCAST TRANSCRIPT")
        fetched_transcript = (
            fetch_auto_transcript(video_url, yt_id) if yt_id else None
        )

        if fetched_transcript:
            st.success("✅ Timed transcript auto-detected (Supports 3+ hours)!")
        else:
            st.warning(
                "⚠️ Auto-capture failed across all backends. "
                "Paste a timed transcript below to proceed.\n\n"
                "**Tips for cloud deployments:**\n"
                "- `yt-transcript-pro` is already installed and tries multiple endpoints.\n"
                "- If a proxy is configured, a known 407 bug may skip it after one attempt.\n"
                "- `yt-dlp` fallback uses `--impersonate chrome` to mimic a real browser."
            )

        transcript_input = st.text_area(
            "Video / Podcast Timed Transcript:",
            value=fetched_transcript if fetched_transcript else "",
            placeholder="[00:01:15] Spoken line 1...\n[01:45:22] Spoken line 2...",
            height=160,
        )

        analyze_btn = st.button(
            "🔥 Deep-Scan & Align Full Podcast Clips",
            type="primary",
            use_container_width=True,
        )

        if analyze_btn:
            if not api_key:
                st.error("⚠️ Gemini API Key missing!")
            elif not transcript_input and not video_title:
                st.warning("Please provide transcript text or a video title.")
            else:
                with st.spinner("Analyzing multi-hour timeline..."):
                    models_to_try = [
                        "gemini-2.5-flash",
                        "gemini-3-flash-preview",
                        "gemini-flash-latest",
                    ]
                    raw_text = None
                    last_error = None
                    prompt = f"""
                    You are an expert podcast editor and viral content strategist.
                    VIDEO TITLE: {video_title if video_title else "Podcast Episode"}
                    TIMED TRANSCRIPT:
                    {transcript_input if transcript_input else "Title: " + video_title}
                    Choose {max_clips} viral highlights distributed evenly across the full duration.
                    Return ONLY a JSON array with keys:
                    title, score, start, end, hook, reason, caption.
                    Start/end MUST match exact bracketed timestamps.
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
                        json_match = re.search(r"\[.*\]", raw_text, re.DOTALL)
                        if json_match:
                            st.session_state["clips"] = json.loads(json_match.group(0))
                        else:
                            st.error("Could not parse JSON response from AI:")
                            st.code(raw_text)
                    else:
                        st.error(f"Gemini API Error: {str(last_error)}")

    if "clips" in st.session_state and st.session_state["clips"]:
        st.divider()
        st.subheader(
            f"✂️ Extracted Podcast Clips for: "
            f"{video_title if video_title else 'Your Video'}"
        )
        for idx, clip in enumerate(st.session_state["clips"]):
            with st.container():
                st.markdown(
                    f"""
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
                """,
                    unsafe_allow_html=True,
                )

                c1, c2, c3 = st.columns(3)

                with c1:
                    start_sec = timestamp_to_seconds(clip["start"])
                    if st.button(
                        f"▶️ Jump & Play ({clip['start']})",
                        key=f"play_{idx}",
                        use_container_width=True,
                    ):
                        st.session_state["seek_start"] = start_sec
                        st.rerun()

                with c2:
                    if st.button(
                        "📥 Render & Download MP4",
                        key=f"render_{idx}",
                        use_container_width=True,
                    ):
                        s_sec = timestamp_to_seconds(clip["start"])
                        e_sec = timestamp_to_seconds(clip["end"])
                        if e_sec <= s_sec:
                            e_sec = s_sec + 30
                        with st.spinner(
                            f"Slicing clip from {clip['start']} to {clip['end']}..."
                        ):
                            success, res = download_and_crop_clip(
                                video_url, s_sec, e_sec, f"clip_{idx}.mp4"
                            )
                            if success:
                                st.success("✅ Clip rendered successfully!")
                                with open(res, "rb") as file:
                                    st.download_button(
                                        label=f"💾 Save MP4 ({clip['start']})",
                                        data=file,
                                        file_name=(
                                            f"podcast_clip_{idx+1}_"
                                            f"{clip['start'].replace(':', '-')}.mp4"
                                        ),
                                        mime="video/mp4",
                                        key=f"dl_btn_{idx}",
                                    )
                            else:
                                st.error(
                                    f"Failed to extract segment: {res}"
                                )

                with c3:
                    st.markdown(
                        '''
                        <a href="https://www.capcut.com/editor" target="_blank" style="text-decoration:none;">
                            <button style="width:100%; background-color:#2563eb; color:white; border:none; padding:8px; border-radius:6px; font-weight:bold; cursor:pointer;">
                                🎬 Edit in CapCut
                            </button>
                        </a>
                    ''',
                        unsafe_allow_html=True,
                    )

else:
    st.info("👈 Paste a YouTube link or podcast URL above to begin.")
