import os
import tempfile
import zipfile

import streamlit as st
import yt_dlp

st.set_page_config(page_title="TikTok Downloader", page_icon="🎬", layout="centered")

st.title("🎬 TikTok Downloader")
st.caption("ទាញយកវីដេអូសាធារណៈច្រើនក្នុងពេលតែមួយ (សម្រាប់មើលផ្ទាល់ខ្លួនប៉ុណ្ណោះ)")

links_text = st.text_area(
    "ដាក់ link (មួយបន្ទាត់ម្ដង) ឬ link profile",
    height=150,
    placeholder="https://www.tiktok.com/@smeyai26",
)

col1, col2 = st.columns(2)
start = col1.number_input("ចាប់ពីវីដេអូទី", min_value=1, value=1, step=1)
end = col2.number_input("ដល់វីដេអូទី", min_value=1, value=20, step=1)

if st.button("ទាញយកទាំងអស់", type="primary"):
    links = [l.strip() for l in links_text.splitlines() if l.strip()]

    if not links:
        st.warning("សូមដាក់ link យ៉ាងតិចមួយ")
        st.stop()

    if end < start:
        st.warning("លេខ 'ដល់' ត្រូវធំជាងលេខ 'ចាប់ពី'")
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
        "outtmpl": os.path.join(tmp_dir, "%(playlist_index|0)03d_%(id)s.%(ext)s"),
        "format": "best",
        "ignoreerrors": True,
        "playlist_items": f"{int(start)}-{int(end)}",
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

    zip_path = os.path.join(tmp_dir, "tiktok_videos.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
        for name in files:
            zf.write(os.path.join(tmp_dir, name), arcname=name)

    with open(zip_path, "rb") as zf:
        st.download_button(
            f"📦 ទាញយក ZIP ({len(files)} វីដេអូ)",
            data=zf,
            file_name=f"tiktok_{int(start)}-{int(end)}.zip",
            mime="application/zip",
        )

st.divider()
st.caption(
    "ប្រើសម្រាប់វីដេអូសាធារណៈ និងការប្រើប្រាស់ផ្ទាល់ខ្លួនប៉ុណ្ណោះ។ "
    "សូមគោរពសិទ្ធិម្ចាស់ និងលក្ខខណ្ឌរបស់ TikTok។"
)
