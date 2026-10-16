import io
import os
import tempfile
import zipfile

import streamlit as st
import yt_dlp

st.set_page_config(page_title="TikTok Downloader", page_icon="🎬", layout="centered")

st.title("🎬 TikTok Downloader")
st.caption("ទាញយកវីដេអូសាធារណៈច្រើនក្នុងពេលតែមួយ (សម្រាប់មើលផ្ទាល់ខ្លួនប៉ុណ្ណោះ)")

MAX_VIDEOS = 30

links_text = st.text_area(
    "ដាក់ link (មួយបន្ទាត់ម្ដង) ឬ link profile / playlist",
    height=180,
    placeholder="https://www.tiktok.com/@user/video/123...\nhttps://www.tiktok.com/@user",
)

if st.button("ទាញយកទាំងអស់", type="primary"):
    links = [l.strip() for l in links_text.splitlines() if l.strip()]

    if not links:
        st.warning("សូមដាក់ link យ៉ាងតិចមួយ")
        st.stop()

    tmp_dir = tempfile.mkdtemp()
    status = st.empty()
    bar = st.progress(0.0)
    done = {"count": 0}

    def hook(d):
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            if total:
                bar.progress(min(d["downloaded_bytes"] / total, 1.0))
            status.info(f"កំពុងទាញយកវីដេអូទី {done['count'] + 1} ...")
        elif d["status"] == "finished":
            done["count"] += 1
            bar.progress(1.0)

    options = {
        "outtmpl": os.path.join(tmp_dir, "%(uploader)s_%(title).60s_%(id)s.%(ext)s"),
        "format": "best",
        "ignoreerrors": True,
        "playlistend": MAX_VIDEOS,
        "quiet": True,
        "noprogress": True,
        "progress_hooks": [hook],
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download(links)
    except Exception as e:
        st.error(f"មានបញ្ហា: {e}")
        st.stop()

    files = sorted(
        f for f in os.listdir(tmp_dir) if f.lower().endswith((".mp4", ".mov", ".webm"))
    )

    if not files:
        status.error("មិនអាចទាញយកបានទេ។ សូមពិនិត្យ link (ត្រូវតែជាវីដេអូសាធារណៈ)")
        st.stop()

    status.success(f"ទាញយកបាន {len(files)} វីដេអូ ✅")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_STORED) as zf:
        for name in files:
            zf.write(os.path.join(tmp_dir, name), arcname=name)

    st.download_button(
        "📦 ទាញយកទាំងអស់ជា ZIP",
        data=zip_buffer.getvalue(),
        file_name="tiktok_videos.zip",
        mime="application/zip",
    )

    st.divider()
    for i, name in enumerate(files):
        with open(os.path.join(tmp_dir, name), "rb") as f:
            st.download_button(
                f"⬇️ {name[:50]}",
                data=f.read(),
                file_name=name,
                mime="video/mp4",
                key=f"dl_{i}",
            )

st.divider()
st.caption(
    "ប្រើសម្រាប់វីដេអូសាធារណៈ និងការប្រើប្រាស់ផ្ទាល់ខ្លួនប៉ុណ្ណោះ។ "
    "សូមគោរពសិទ្ធិម្ចាស់ និងលក្ខខណ្ឌរបស់ TikTok។"
)
