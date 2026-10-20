import io
import os
import re
import shutil
import tempfile
import zipfile
from urllib.parse import urlparse

import requests
import streamlit as st
import yt_dlp

MAX_VIDEOS = 20

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

MIME_TYPES = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
    ".mkv": "video/x-matroska",
    ".flv": "video/x-flv",
    ".3gp": "video/3gpp",
}

SHORT_HOSTS = (
    "vt.tiktok.com",
    "vm.tiktok.com",
    "fb.watch",
    "m.facebook.com",
    "t.co",
    "bit.ly",
    "tinyurl.com",
)

st.set_page_config(
    page_title="Video Downloader",
    page_icon="🎬",
    layout="centered",
)

st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(
            135deg,
            #5b3df0 0%,
            #8a2be2 50%,
            #d100ff 100%
        );
    }

    h1, .stCaption, p, label, .stMarkdown {
        color: #ffffff !important;
    }

    h1 {
        text-align: center;
        font-weight: 800;
    }

    div[data-baseweb="input"] > div {
        background: #efe6ff !important;
        border-radius: 14px !important;
    }

    div[data-baseweb="input"] input {
        color: #2b1b5a !important;
        font-size: 18px !important;
        padding: 14px !important;
    }

    .stButton > button,
    .stDownloadButton > button {
        width: 100%;
        padding: 0.9rem 1rem;
        font-size: 20px;
        font-weight: 700;
        color: #ffffff;
        border: 2px solid #ffffff;
        border-radius: 14px;
        background: linear-gradient(
            90deg,
            #d100ff,
            #5b3df0
        );
    }

    .stButton > button:hover,
    .stDownloadButton > button:hover {
        color: #ffffff;
        border-color: #ffffff;
        filter: brightness(1.1);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎬 Video Downloader")

st.caption(
    "TikTok • Facebook • YouTube • Instagram • X "
    "• និងគេហទំព័រផ្សេងទៀត"
)

link = st.text_input(
    "Link",
    placeholder="Insert a link here",
    label_visibility="collapsed",
)


def extract_url(text):
    """ទាញយក URL ពីអត្ថបទ។"""

    text = text.strip()

    for part in text.replace("\n", " ").split():

        part = part.strip(" \t\r\n<>\"'")

        part = part.rstrip(".,!?;)]}")

        if part.lower().startswith(
            ("http://", "https://")
        ):
            return part

    if "." in text and " " not in text:
        return "https://" + text.strip()

    return text


def is_tiktok_url(url):
    """ពិនិត្យថា URL ជា TikTok ឬអត់។"""

    try:
        host = urlparse(url).netloc.lower()

        return (
            host == "tiktok.com"
            or host.endswith(".tiktok.com")
        )

    except Exception:
        return False


def resolve_short_link(url):
    """
    តាម Short Link ទៅ Link ពេញ។

    សម្រាប់ TikTok បើ redirect ទៅ 404
    ឬមិនអាចរក Link ពេញបាន គឺរក្សា Link ដើម។
    """

    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()

        is_short = any(
            host == short_host
            or host.endswith("." + short_host)
            for short_host in SHORT_HOSTS
        )

        if not is_short:
            return url

        response = requests.get(
            url,
            headers={"User-Agent": UA},
            allow_redirects=True,
            timeout=20,
            stream=True,
        )

        final_url = response.url
        status_code = response.status_code

        response.close()

        if not final_url:
            return url

        # TikTok redirect ទៅ 404 មិនត្រូវយក URL នោះទេ
        if is_tiktok_url(url):

            final_path = urlparse(final_url).path.lower()

            if (
                status_code >= 400
                or "/404" in final_path
                or "fromurl=" in final_url.lower()
            ):
                return url

            # ប្រើ Link ពេញ បើ redirect បានត្រឹមត្រូវ
            if "/video/" in final_url:
                return final_url

            # បើ redirect មិនបាន Link វីដេអូ
            # រក្សា Link ខ្លីដើម
            return url

        if (
            final_url.startswith("http")
            and status_code < 400
        ):
            return final_url

    except Exception:
        pass

    return url


def get_impersonate_target():
    """ប្រើ Chrome impersonation ប្រសិនបើមាន curl_cffi។"""

    try:
        import curl_cffi  # noqa: F401

        from yt_dlp.networking.impersonate import (
            ImpersonateTarget,
        )

        return ImpersonateTarget.from_str("chrome")

    except Exception:
        return None


def is_playlist_link(url):
    """ពិនិត្យ Playlist/Profile។"""

    try:
        options = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,
            "ignoreerrors": True,
            "playlistend": 1,
            "noplaylist": False,
            "http_headers": {
                "User-Agent": UA,
            },
            "socket_timeout": 20,
        }

        with yt_dlp.YoutubeDL(options) as ydl:

            info = ydl.extract_info(
                url,
                download=False,
            )

        return (
            bool(info)
            and info.get("_type") == "playlist"
        )

    except Exception:
        return False


def build_attempts(url, has_ffmpeg, playlist):
    """បង្កើតវិធីទាញយកវីដេអូ។"""

    tiktok = is_tiktok_url(url)

    imp = get_impersonate_target()

    if tiktok:

        formats = [
            "best",
            "best[ext=mp4]",
            None,
        ]

    elif has_ffmpeg:

        formats = [
            "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b",
            "best",
            None,
        ]

    else:

        formats = [
            "best[ext=mp4]/best",
            "best",
            None,
        ]

    attempts = []

    for idx, fmt in enumerate(formats):

        opt = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "restrictfilenames": True,

            "noplaylist": not playlist,
            "ignoreerrors": bool(playlist),

            "retries": 2,
            "fragment_retries": 2,
            "socket_timeout": 30,

            "geo_bypass": True,

            "http_headers": {
                "User-Agent": UA,
            },
        }

        if fmt:
            opt["format"] = fmt

        if has_ffmpeg and not tiktok:
            opt["merge_output_format"] = "mp4"

        if playlist:
            opt["playlist_items"] = (
                f"1-{MAX_VIDEOS}"
            )

        if imp is not None:
            opt["impersonate"] = imp

        if tiktok and idx == 2:

            opt["extractor_args"] = {
                "tiktok": {
                    "api_hostname": [
                        "api22-normal-c-useast2a.tiktokv.com"
                    ]
                }
            }

        attempts.append(opt)

    return attempts


def download_via_tikwm(url, folder):
    """វិធីបម្រុងសម្រាប់ TikTok។"""

    # ប្រើ URL ដែលទទួលបាន មិនបង្កើត URL /404 ទេ
    response = requests.post(
        "https://www.tikwm.com/api/",
        data={
            "url": url,
            "hd": 1,
        },
        headers={
            "User-Agent": UA,
            "Referer": "https://www.tikwm.com/",
        },
        timeout=35,
    )

    response.raise_for_status()

    try:
        j = response.json()

    except Exception:
        raise RuntimeError(
            "TikWM មិនបានផ្ញើ JSON ត្រឹមត្រូវ។"
        )

    if str(j.get("code")) != "0":

        raise RuntimeError(
            f"TikWM API error: {j.get('msg')}"
        )

    d = j.get("data") or {}

    play = (
        d.get("hdplay")
        or d.get("play")
        or d.get("wmplay")
    )

    if not play:

        raise RuntimeError(
            "រកមិនឃើញ Link វីដេអូ។ "
            "វីដេអូអាចជា Private ឬមិនមានទៀត។"
        )

    if play.startswith("//"):
        play = "https:" + play

    elif play.startswith("/"):
        play = "https://www.tikwm.com" + play

    video_id = str(
        d.get("id") or "video"
    )

    path = os.path.join(
        folder,
        f"tikwm_{video_id}.mp4",
    )

    with requests.get(
        play,
        headers={"User-Agent": UA},
        stream=True,
        timeout=60,
    ) as resp:

        resp.raise_for_status()

        content_type = resp.headers.get(
            "Content-Type",
            "",
        ).lower()

        if "text/html" in content_type:

            raise RuntimeError(
                "TikWM បានផ្ញើ HTML មិនមែន Video។"
            )

        with open(path, "wb") as f:

            for chunk in resp.iter_content(
                chunk_size=1024 * 256
            ):

                if chunk:
                    f.write(chunk)

    if (
        not os.path.exists(path)
        or os.path.getsize(path) < 1024
    ):

        if os.path.exists(path):
            os.remove(path)

        raise RuntimeError(
            "ឯកសារវីដេអូទាញយកមិនបានពេញលេញ។"
        )


def find_videos(folder):
    """រកឯកសារវីដេអូ។"""

    names = sorted(
        os.listdir(folder)
    )

    return [
        name
        for name in names
        if name.lower().endswith(
            tuple(MIME_TYPES.keys())
        )
    ]


def friendly_hint(err_text):
    """បកស្រាយ Error ជាភាសាខ្មែរ។"""

    t = err_text.lower()

    if (
        "no video formats found" in t
        or "no formats found" in t
    ):

        return (
            "TikTok មិនបានផ្តល់ Video Format មក server ទេ។ "
            "អាចបណ្តាលមកពី yt-dlp ចាស់ ឬ TikTok "
            "រារាំង server របស់ Streamlit Cloud។"
        )

    if (
        "unsupported url" in t
        or "url parsing" in t
    ):

        return (
            "Link មិនត្រឹមត្រូវ ឬសេវាទាញយក "
            "មិនអាចបកស្រាយ Link នេះបាន។ "
            "សូម Copy Link ថ្មីពី TikTok។"
        )

    if (
        "ip address is blocked" in t
        or "blocked" in t
        or "403" in t
        or "429" in t
    ):

        return (
            "គេហទំព័របានរារាំង server នេះ។ "
            "សូមសាកល្បងលើកុំព្យូទ័រផ្ទាល់ខ្លួន "
            "ឬសាកល្បង Link ផ្សេង។"
        )

    if (
        "private" in t
        or "login" in t
        or "sign in" in t
        or "cookies" in t
    ):

        return (
            "វីដេអូនេះអាចជា Private ឬត្រូវការ Login។"
        )

    if "ffmpeg" in t:

        return (
            "ត្រូវការ ffmpeg។ "
            "សូមបន្ថែម packages.txt ដែលមាន ffmpeg "
            "ហើយ Reboot App។"
        )

    if (
        "unavailable" in t
        or "not available" in t
        or "removed" in t
    ):

        return (
            "វីដេអូនេះលែងមាន ឬត្រូវបានលុប។"
        )

    return (
        "សូមសាកល្បងម្តងទៀត ឬ Update yt-dlp។"
    )


# ==================================================
# DOWNLOAD BUTTON
# ==================================================

if st.button("Download", type="primary"):

    raw = link.strip()

    if not raw:

        st.warning(
            "សូមដាក់ Link ជាមុនសិន។"
        )

        st.stop()

    orig_url = extract_url(raw)

    if not orig_url.startswith(
        ("http://", "https://")
    ):

        st.warning(
            "Link មិនត្រឹមត្រូវទេ។"
        )

        st.stop()

    has_ffmpeg = (
        shutil.which("ffmpeg") is not None
    )

    # TikTok: រក្សា Link ដើម បើ redirect ខូច
    with st.spinner("កំពុងពិនិត្យ Link..."):

        url = resolve_short_link(
            orig_url
        )

        playlist = is_playlist_link(
            url
        )

    tmp_dir = tempfile.mkdtemp()

    errors = []
    videos = []
    results = []

    try:

        attempts = build_attempts(
            url,
            has_ffmpeg,
            playlist,
        )

        with st.spinner(
            "កំពុងទាញយកវីដេអូ..."
        ):

            # សាកល្បង yt-dlp
            for n, opt in enumerate(
                attempts,
                start=1,
            ):

                opt["outtmpl"] = os.path.join(
                    tmp_dir,
                    f"a{n}_%(playlist_index|0)03d_%(id)s.%(ext)s",
                )

                try:

                    with yt_dlp.YoutubeDL(
                        opt
                    ) as ydl:

                        ydl.download(
                            [url]
                        )

                except Exception as e:

                    errors.append(
                        f"[ព្យាយាមទី {n}] {e}"
                    )

                videos = find_videos(
                    tmp_dir
                )

                if videos:
                    break

            # TikTok backup
            if (
                not videos
                and is_tiktok_url(orig_url)
            ):

                candidates = []

                # សាកល្បង Link ដើម
                candidates.append(
                    orig_url
                )

                # សាកល្បង Link ពេញ បើខុសពី Link ដើម
                if url and url not in candidates:
                    candidates.append(url)

                for cand in candidates:

                    try:

                        download_via_tikwm(
                            cand,
                            tmp_dir,
                        )

                    except Exception as e:

                        errors.append(
                            f"[TikWM {cand[:50]}] {e}"
                        )

                    videos = find_videos(
                        tmp_dir
                    )

                    if videos:
                        break

        # អានឯកសារវីដេអូ
        if videos:

            for name in videos:

                file_path = os.path.join(
                    tmp_dir,
                    name,
                )

                with open(
                    file_path,
                    "rb",
                ) as f:

                    results.append(
                        (
                            name,
                            f.read(),
                        )
                    )

    finally:

        shutil.rmtree(
            tmp_dir,
            ignore_errors=True,
        )

    # បើទាញយកមិនបាន
    if not results:

        err_text = (
            "\n".join(errors)
            if errors
            else "មិនមានព័ត៌មាន Error ទេ"
        )

        st.error(
            "មិនអាចទាញយកបានទេ។ "
            + friendly_hint(
                err_text
            )
        )

        with st.expander(
            "មើលព័ត៌មាន Error លម្អិត"
        ):

            st.code(
                err_text
            )

        st.stop()

    # បើទាញយកបាន
    st.success(
        f"ទាញយកបាន {len(results)} វីដេអូ ✅"
    )

    for i, (name, data) in enumerate(
        results,
        start=1,
    ):

        ext = os.path.splitext(
            name
        )[1].lower()

        st.markdown(
            f"**វីដេអូទី {i}**"
        )

        if len(results) == 1:

            st.video(
                data
            )

        st.download_button(
            f"⬇️ Download ({name[:30]})",
            data=data,
            file_name=name,
            mime=MIME_TYPES.get(
                ext,
                "video/mp4",
            ),
            key=f"vid_{i}",
            on_click="ignore",
        )

    # ទាញយក ZIP បើមានវីដេអូច្រើន
    if len(results) > 1:

        buf = io.BytesIO()

        with zipfile.ZipFile(
            buf,
            "w",
            zipfile.ZIP_STORED,
        ) as zf:

            for name, data in results:

                zf.writestr(
                    name,
                    data,
                )

        st.download_button(
            f"📦 ទាញយក ZIP ({len(results)} វីដេអូ)",
            data=buf.getvalue(),
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
