import os
import shutil
import tempfile
import zipfile

import streamlit as st
import yt_dlp

MAX_VIDEOS = 20  # ចំនួនវីដេអូអតិបរមា បើ link ជា profile ឬ playlist

st.set_page_config(page_title="Video Downloader", page_icon="🎬", layout="centered")

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #5b3df0 0%, #8a2be2 50%, #d100ff 100%);
    }
    h1, .stCaption, p, label, .stMarkdown {
        color: #ffffff !important;
    }
    h1 { text-align: center; font-weight: 800; }
    div[data-baseweb="input"] > div {
        background: #efe6ff !important;
        border-radius: 14px !important;
    }
    div[data-baseweb="input"] input {
        color: #2b1b5a !important;
        font-size: 18px !important;
        padding: 14px !important;
    }
    .stButton > button, .stDownloadButton > button {
        width: 100%;
        padding: 0.9rem 1rem;
        font-size: 20px;
        font-weight: 700;
        color: #ffffff;
        border: 2px solid #ffffff;
        border-radius: 14px;
        background: linear-gradient(90deg, #d100ff, #5b3df0);
    }
    .stButton > button:hover, .stDownloadButton > button:hover {
        color: #ffffff;
        border-color: #ffffff;
        filter: brightness(1.1);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎬 Video Downloader")
st.caption("TikTok • Facebook • YouTube • និងគេហទំព័រផ្សេងទៀត (សម្រាប់មើលផ្ទាល់ខ្លួនប៉ុណ្ណោះ)")

link = st.text_input(
    "Link",
    placeholder="Insert a link here",
    label_visibility="collapsed",
)

MIME_TYPES = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
}


def is_playlist_link(url):
    """ពិនិត្យថា link ជា profile / playlist ឬវីដេអូតែមួយ"""
    try:
        with yt_dlp.YoutubeDL(
            {
                "quiet": True,
                "extract_flat": True,
                "ignoreerrors": True,
                "playlistend": 1,
                "noplaylist": False,
            }
        ) as y:
            info = y.extract_info(url, download=False)
        return bool(info) and info.get("_type") == "playlist"
    except Exception:
        return False


if st.button("Download", type="primary"):
    link = link.strip()

    if not link:
        st.warning("សូមដាក់ link ជាមុនសិន")
        st.stop()

    has_ffmpeg = shutil.which("ffmpeg") is not None
    is_tiktok = "tiktok.com" in link.lower()
    tmp_dir = tempfile.mkdtemp()

    with st.spinner("កំពុងពិនិត្យ link ..."):
        playlist = is_playlist_link(link)

    # ជ្រើស format តាមគេហទំព័រ
    if is_tiktok:
        # ជៀសវាង format "download" ដែលជាធម្មតាមាន watermark
        fmt = "best[format_id!=download]/best"
    elif has_ffmpeg:
        fmt = "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b"
    else:
        fmt = "best[ext=mp4]/best"

    options = {
        "outtmpl": os.path.join(tmp_dir, "%(playlist_index|0)03d_%(id)s.%(ext)s"),
        "format": fmt,
        "ignoreerrors": True,
        "quiet": True,
        "noprogress": True,
        "noplaylist": not playlist,
        "restrictfilenames": True,
    }

    if has_ffmpeg and not is_tiktok:
        options["merge_output_format"] = "mp4"

    if playlist:
        options["playlist_items"] = f"1-{MAX_VIDEOS}"

    try:
        with st.spinner("កំពុងទាញយក..."):
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([link])
    except Exception as e:
        st.error(f"មានបញ្ហា: {e}")
        st.stop()

    all_files = sorted(os.listdir(tmp_dir))
    videos = [f for f in all_files if f.lower().endswith(tuple(MIME_TYPES))]

    if not videos:
        st.error(
            "មិនអាចទាញយកបានទេ។ សូមពិនិត្យ link (ត្រូវតែជាវីដេអូសាធារណៈ "
            "ហើយមិនត្រូវការ login)"
        )
        st.stop()

    st.success(f"ទាញយកបាន {len(videos)} វីដេអូ ✅")

    for i, name in enumerate(videos, start=1):
        path = os.path.join(tmp_dir, name)
        ext = os.path.splitext(name)[1].lower()
        st.markdown(f"**វីដេអូទី {i}**")
        if len(videos) == 1:
            st.video(path)
        with open(path, "rb") as f:
            st.download_button(
                f"⬇️ Download ({name[:30]})",
                data=f.read(),
                file_name=name,
                mime=MIME_TYPES.get(ext, "video/mp4"),
                key=f"vid_{i}",
                on_click="ignore",
            )

    if len(videos) > 1:
        zip_path = os.path.join(tmp_dir, "videos.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
            for name in videos:
                zf.write(os.path.join(tmp_dir, name), arcname=name)
        with open(zip_path, "rb") as zf:
            st.download_button(
                f"📦 ទាញយក ZIP ({len(videos)} វីដេអូ)",
                data=zf.read(),
                file_name="videos.zip",
                mime="application/zip",
                key="zip_all",
                on_click="ignore",
            )

st.divider()
st.caption(
    "ប្រើសម្រាប់វីដេអូសាធារណៈ និងការប្រើប្រាស់ផ្ទាល់ខ្លួនប៉ុណ្ណោះ។ "
    "សូមគោរពសិទ្ធិម្ចាស់ និងលក្ខខណ្ឌរបស់គេហទំព័រនីមួយៗ។"
)
