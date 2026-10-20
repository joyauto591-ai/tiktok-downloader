import os
import re
import tempfile
import streamlit as st
import imageio_ffmpeg

st.set_page_config(
    page_title="Short Drama Downloader",
    page_icon="🎬",
    layout="centered"
)

st.markdown("""
<style>
.stApp {
    background: linear-gradient(
        180deg,
        #070b12 0%,
        #0c1320 55%,
        #070a10 100%
    );
    color: #ffffff;
}

.block-container {
    max-width: 760px;
    padding: 24px 16px 50px;
}

/* Hide Streamlit header and footer */
header[data-testid="stHeader"] {
    visibility: hidden;
    height: 0;
}

footer {
    visibility: hidden;
    height: 0;
}

[data-testid="stToolbar"] {
    visibility: hidden;
    height: 0;
}

[data-testid="stDecoration"] {
    display: none;
}

.hero {
    text-align: center;
    margin-bottom: 24px;
}

.hero h1 {
    font-size: 34px;
    margin: 0;
    font-weight: 900;
}

.hero p {
    color: #aeb9c9;
}

.card {
    padding: 18px;
    border-radius: 18px;
    background: rgba(255,255,255,.045);
    border: 1px solid rgba(255,255,255,.09);
    margin: 12px 0;
}

.stButton > button {
    width: 100%;
    border-radius: 14px;
    height: 48px;
    font-weight: 800;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
    <h1>🎬 Short Drama Downloader</h1>
    <p>Paste a public drama/video link → Download Video</p>
</div>
""", unsafe_allow_html=True)


def download_video(url, workdir):

    try:
        import yt_dlp
    except ImportError:
        raise RuntimeError(
            "yt-dlp មិនទាន់មានក្នុង requirements.txt"
        )

    outtmpl = os.path.join(
        workdir,
        "%(title)s.%(ext)s"
    )

    opts = {
        "outtmpl": outtmpl,
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Linux; Android 12) "
                "AppleWebKit/537.36 Chrome/140 "
                "Mobile Safari/537.36"
            )
        }
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(
            url,
            download=True
        )

    files = [
        os.path.join(workdir, name)
        for name in os.listdir(workdir)
        if os.path.isfile(
            os.path.join(workdir, name)
        )
    ]

    if not files:
        raise RuntimeError(
            "រកមិនឃើញវីដេអូដែលអាច Download បានពី Link នេះ"
        )

    files.sort(
        key=os.path.getsize,
        reverse=True
    )

    return files[0], info


def safe_name(value):

    value = re.sub(
        r'[\\/:*?"<>|]+',
        "_",
        value or "short_drama"
    )

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()[:120] or "short_drama"


st.markdown(
    '<div class="card">',
    unsafe_allow_html=True
)

url = st.text_input(
    "🔗 Video / Short Drama Link",
    placeholder="https://example.com/episode-1"
)

if st.button(
    "📥 DOWNLOAD VIDEO",
    type="primary"
):

    if not url.strip():
        st.warning("សូមដាក់ Link ជាមុន")
        st.stop()

    workdir = tempfile.mkdtemp(
        prefix="drama_download_"
    )

    try:

        with st.status(
            "⬇️ កំពុងទាញយកវីដេអូ...",
            expanded=True
        ) as status:

            st.write(
                "🔎 កំពុងស្វែងរក Video Stream..."
            )

            path, info = download_video(
                url.strip(),
                workdir
            )

            title = safe_name(
                info.get(
                    "title",
                    "short_drama"
                )
            )

            with open(path, "rb") as video_file:
                data = video_file.read()

            status.update(
                label="✅ Download រួចរាល់!",
                state="complete"
            )

        st.video(data)

        st.download_button(
            "📥 SAVE VIDEO TO PHONE",
            data=data,
            file_name=f"{title}.mp4",
            mime="video/mp4",
            type="primary"
        )

        st.success(
            "វីដេអូរួចរាល់ — "
            "ចុច SAVE VIDEO TO PHONE "
            "ដើម្បីរក្សាទុកក្នុងទូរសព្ទ។"
        )

    except Exception as error:

        st.error(
            f"❌ Download មិនបាន: {error}"
        )

        st.caption(
            "Link ត្រូវតែជាវីដេអូសាធារណៈ "
            "ដែលប្រភពអនុញ្ញាតឱ្យចូលប្រើ។ "
            "Private/login-required/DRM "
            "មិនត្រូវបាន bypass ទេ។"
        )

st.markdown(
    "</div>",
    unsafe_allow_html=True
)
