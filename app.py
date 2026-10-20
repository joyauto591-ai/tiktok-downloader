import os
import shutil
import tempfile
import zipfile

import streamlit as st
import yt_dlp

st.set_page_config(page_title="TikTok Downloader", page_icon="🎬", layout="centered")

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

st.title("🎬 TikTok Video Downloader")
st.caption("ដាក់ link វីដេអូសាធារណៈ ហើយចុច Download (សម្រាប់មើលផ្ទាល់ខ្លួនប៉ុណ្ណោះ)")

link = st.text_input(
    "Link",
    placeholder="Insert a link here",
    label_visibility="collapsed",
)

with st.expander("ជម្រើសបន្ថែម"):
    want_mp3 = st.checkbox("ទាញយក MP3 (សំឡេង) ផងដែរ", value=False)
    st.caption("បើ link ជា profile (ឧ. https://www.tiktok.com/@name) សូមជ្រើសចន្លោះវីដេអូ៖")
    col1, col2 = st.columns(2)
    start = col1.number_input("ចាប់ពីវីដេអូទី", min_value=1, value=1, step=1)
    end = col2.number_input("ដល់វីដេអូទី", min_value=1, value=20, step=1)

if st.button("Download", type="primary"):
    link = link.strip()

    if not link:
        st.warning("សូមដាក់ link ជាមុនសិន")
        st.stop()

    if end < start:
        st.warning("លេខ 'ដល់' ត្រូវធំជាងលេខ 'ចាប់ពី'")
        st.stop()

    is_single_video = "/video/" in link or "/photo/" in link or "vm.tiktok.com" in link or "vt.tiktok.com" in link or "/t/" in link
    has_ffmpeg = shutil.which("ffmpeg") is not None
    tmp_dir = tempfile.mkdtemp()

    options = {
        "outtmpl": os.path.join(tmp_dir, "%(playlist_index|0)03d_%(id)s.%(ext)s"),
        # ជ្រើស format ដែលមិនមែនជា "download" (ជាធម្មតាមាន watermark) បើមាន
        "format": "best[format_id!=download]/best",
        "ignoreerrors": True,
        "quiet": True,
        "noprogress": True,
    }

    if not is_single_video:
        options["playlist_items"] = f"{int(start)}-{int(end)}"

    if want_mp3:
        if has_ffmpeg:
            options["keepvideo"] = True
            options["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ]
        else:
            st.warning("មិនមាន ffmpeg នៅលើម៉ាស៊ីននេះ ដូច្នេះមិនអាចបង្កើត MP3 បានទេ")

    try:
        with st.spinner("កំពុងទាញយក..."):
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.download([link])
    except Exception as e:
        st.error(f"មានបញ្ហា: {e}")
        st.stop()

    all_files = sorted(os.listdir(tmp_dir))
    videos = [f for f in all_files if f.lower().endswith((".mp4", ".mov", ".webm"))]
    audios = [f for f in all_files if f.lower().endswith(".mp3")]

    if not videos:
        st.error("មិនអាចទាញយកបានទេ។ សូមពិនិត្យ link (ត្រូវតែជាវីដេអូសាធារណៈ)")
        st.stop()

    st.success(f"ទាញយកបាន {len(videos)} វីដេអូ ✅")

    for i, name in enumerate(videos, start=1):
        path = os.path.join(tmp_dir, name)
        st.markdown(f"**វីដេអូទី {i}**")
        if len(videos) == 1:
            st.video(path)
        with open(path, "rb") as f:
            st.download_button(
                f"⬇️ Download MP4 ({name[:30]})",
                data=f.read(),
                file_name=name,
                mime="video/mp4",
                key=f"mp4_{i}",
                on_click="ignore",
            )
        mp3_name = os.path.splitext(name)[0] + ".mp3"
        if mp3_name in audios:
            with open(os.path.join(tmp_dir, mp3_name), "rb") as f:
                st.download_button(
                    "🎵 Download MP3",
                    data=f.read(),
                    file_name=mp3_name,
                    mime="audio/mpeg",
                    key=f"mp3_{i}",
                    on_click="ignore",
                )

    if len(videos) > 1:
        zip_path = os.path.join(tmp_dir, "tiktok_videos.zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
            for name in videos:
                zf.write(os.path.join(tmp_dir, name), arcname=name)
        with open(zip_path, "rb") as zf:
            st.download_button(
                f"📦 ទាញយក ZIP ({len(videos)} វីដេអូ)",
                data=zf.read(),
                file_name=f"tiktok_{int(start)}-{int(end)}.zip",
                mime="application/zip",
                key="zip_all",
                on_click="ignore",
            )

st.divider()
st.caption(
    "ប្រើសម្រាប់វីដេអូសាធារណៈ និងការប្រើប្រាស់ផ្ទាល់ខ្លួនប៉ុណ្ណោះ។ "
    "សូមគោរពសិទ្ធិម្ចាស់ និងលក្ខខណ្ឌរបស់ TikTok។"
)
