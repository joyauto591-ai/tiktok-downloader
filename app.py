import io
import os
import re
import json
import shutil
import tempfile
import zipfile
import html
from urllib.parse import urlparse, unquote

import requests
import streamlit as st
import yt_dlp


MAX_VIDEOS = 20

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
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
    "m.facebook.com/share",
    "facebook.com/share",
    "t.co",
    "bit.ly",
    "tinyurl.com",
)

SHORTDRAMA_PATTERN = re.compile(
    r"tiktok\.com/shortdrama/episode/(\d+)(?:/(\d+))?",
    re.IGNORECASE,
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
    "TikTok • Short Drama • Facebook • YouTube • "
    "Instagram • X • និងគេហទំព័រផ្សេងៗ"
)

link = st.text_input(
    "Link",
    placeholder="Insert a link here",
    label_visibility="collapsed",
)


def extract_url(text):
    """ទាញយក URL ពីអត្ថបទ"""
    for part in text.replace("\n", " ").split():
        if part.lower().startswith(("http://", "https://")):
            return part.strip()

    if "." in text and " " not in text:
        return "https://" + text.strip()

    return text.strip()


def is_shortdrama_url(url):
    """ពិនិត្យ Link TikTok Short Drama"""
    return bool(SHORTDRAMA_PATTERN.search(url))


def resolve_short_link(url):
    """តាមដាន Link ខ្លីទៅ Link ពេញ"""
    low = url.lower()

    if not any(host in low for host in SHORT_HOSTS):
        return url

    try:
        r = requests.get(
            url,
            headers={"User-Agent": UA},
            allow_redirects=True,
            timeout=20,
        )

        if r.url and r.url.startswith("http"):
            return r.url

    except Exception:
        pass

    return url


def get_impersonate_target():
    """ប្រើ Chrome impersonation ប្រសិនបើមាន curl_cffi"""
    try:
        import curl_cffi  # noqa: F401

        from yt_dlp.networking.impersonate import ImpersonateTarget

        return ImpersonateTarget.from_str("chrome")

    except Exception:
        return None


def is_playlist_link(url):
    """ពិនិត្យថា Link ជា playlist ឬវីដេអូតែមួយ"""
    try:
        with yt_dlp.YoutubeDL(
            {
                "quiet": True,
                "extract_flat": True,
                "ignoreerrors": True,
                "playlistend": 1,
                "noplaylist": False,
                "http_headers": {"User-Agent": UA},
                "socket_timeout": 20,
            }
        ) as y:

            info = y.extract_info(
                url,
                download=False,
            )

        return bool(info) and info.get("_type") == "playlist"

    except Exception:
        return False


def build_attempts(url, has_ffmpeg, playlist):
    """បង្កើតវិធីទាញយកសម្រាប់ TikTok និងគេហទំព័រផ្សេងៗ"""

    is_tiktok = "tiktok.com" in url.lower()
    imp = get_impersonate_target()

    if has_ffmpeg and not is_tiktok:
        formats = [
            "bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b",
            "best",
            None,
        ]

    elif is_tiktok:
        formats = [
            "best[format_id!=download]/best",
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
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "geo_bypass": True,
            "http_headers": {"User-Agent": UA},
        }

        if fmt:
            opt["format"] = fmt

        if has_ffmpeg and not is_tiktok:
            opt["merge_output_format"] = "mp4"

        if playlist:
            opt["playlist_items"] = f"1-{MAX_VIDEOS}"

        if imp is not None and idx != 1:
            opt["impersonate"] = imp

        if is_tiktok and idx == 2:
            opt["extractor_args"] = {
                "tiktok": {
                    "api_hostname": [
                        "api22-normal-c-useast2a.tiktokv.com"
                    ]
                }
            }

        attempts.append(opt)

    return attempts


def decode_json_text(text):
    """សម្អាត JSON ដែលបានដកចេញពី HTML"""
    text = html.unescape(text)

    text = text.replace("\\/", "/")
    text = text.replace("\\u002F", "/")
    text = text.replace("\\u0026", "&")
    text = text.replace("\\u003D", "=")

    return text


def extract_video_urls_from_html(page):
    """
    ស្វែងរក URL វីដេអូក្នុង HTML របស់ Short Drama។

    វិធីនេះគ្រាន់តែសាកល្បងស្វែងរកប្រភពវីដេអូ
    មិនធានាថាទំព័រ TikTok នឹងបង្ហាញ URL ទាំងនោះទេ។
    """

    page = decode_json_text(page)

    found = []

    # ស្វែងរក URL វីដេអូដែលបង្ហាញក្នុង HTML
    patterns = [
        r'https?://[^"\'\s<>]+\.mp4[^"\'\s<>]*',
        r'https?://[^"\'\s<>]+\.m3u8[^"\'\s<>]*',
        r'"playAddr"\s*:\s*"([^"]+)"',
        r'"downloadAddr"\s*:\s*"([^"]+)"',
        r'"videoUrl"\s*:\s*"([^"]+)"',
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            page,
            flags=re.IGNORECASE,
        )

        for item in matches:

            item = html.unescape(item)
            item = item.replace("\\/", "/")
            item = item.replace("\\u002F", "/")
            item = item.replace("\\u0026", "&")

            if item.startswith("//"):
                item = "https:" + item

            if item.startswith("http"):
                if ".mp4" in item.lower() or ".m3u8" in item.lower():
                    if item not in found:
                        found.append(item)

    return found


def download_direct_video(url, folder, referer):
    """
    ទាញយកពី URL វីដេអូដោយផ្ទាល់
    """

    headers = {
        "User-Agent": UA,
        "Referer": referer,
    }

    with requests.get(
        url,
        headers=headers,
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
                "ប្រភពដែលបានរកឃើញមិនមែនជា Video File ទេ"
            )

        filename = "shortdrama_video.mp4"

        path = os.path.join(
            folder,
            filename,
        )

        with open(path, "wb") as f:

            for chunk in resp.iter_content(
                chunk_size=1024 * 256
            ):

                if chunk:
                    f.write(chunk)

        return path


def download_shortdrama_episode(url, folder):
    """
    វិធីសាកល្បងសម្រាប់ TikTok Short Drama។

    1. ទាញយក HTML របស់ Episode។
    2. ស្វែងរក URL វីដេអូក្នុង HTML។
    3. សាកទាញយកប្រភពវីដេអូដោយផ្ទាល់។
    """

    errors = []

    headers = {
        "User-Agent": UA,
        "Referer": "https://www.tiktok.com/",
    }

    try:

        response = requests.get(
            url,
            headers=headers,
            allow_redirects=True,
            timeout=30,
        )

        response.raise_for_status()

        page = response.text

    except Exception as e:

        raise RuntimeError(
            "មិនអាចបើកទំព័រ Short Drama បានទេ: "
            + str(e)
        )

    video_urls = extract_video_urls_from_html(page)

    if not video_urls:

        raise RuntimeError(
            "មិនអាចរកឃើញ URL វីដេអូក្នុង HTML របស់ Short Drama បានទេ។ "
            "TikTok អាចផ្ទុកវីដេអូតាម API ឬ JavaScript ដែលមិនបង្ហាញក្នុង HTML។"
        )

    for video_url in video_urls:

        try:

            path = download_direct_video(
                video_url,
                folder,
                response.url,
            )

            return path

        except Exception as e:

            errors.append(str(e))

    raise RuntimeError(
        "រកឃើញ URL វីដេអូ ប៉ុន្តែទាញយកមិនបាន: "
        + " | ".join(errors)
    )


def download_via_tikwm(url, folder):
    """
    ជម្រើសបម្រុងសម្រាប់ TikTok វីដេអូធម្មតា។

    មិនប្រើសម្រាប់ Short Drama Episode ទេ។
    """

    r = requests.post(
        "https://www.tikwm.com/api/",
        data={
            "url": url,
            "hd": 1,
        },
        headers={"User-Agent": UA},
        timeout=30,
    )

    j = r.json()

    if j.get("code") != 0:
        raise RuntimeError(
            f"TikWM API error: {j.get('msg')}"
        )

    d = j.get("data") or {}

    play = d.get("hdplay") or d.get("play")

    if not play:
        raise RuntimeError(
            "រកមិនឃើញ Link វីដេអូ"
        )

    if play.startswith("/"):
        play = "https://www.tikwm.com" + play

    vid = str(d.get("id") or "video")

    path = os.path.join(
        folder,
        f"tikwm_{vid}.mp4",
    )

    with requests.get(
        play,
        headers={"User-Agent": UA},
        stream=True,
        timeout=60,
    ) as resp:

        resp.raise_for_status()

        with open(path, "wb") as f:

            for chunk in resp.iter_content(
                chunk_size=1024 * 256
            ):

                if chunk:
                    f.write(chunk)

    return path


def find_videos(folder):
    names = sorted(os.listdir(folder))

    return [
        n for n in names
        if n.lower().endswith(tuple(MIME_TYPES))
    ]


def friendly_hint(err_text):

    t = err_text.lower()

    if "shortdrama" in t or "short drama" in t:

        return (
            "មិនអាចរកប្រភពវីដេអូ Short Drama ក្នុងទំព័រ TikTok បានទេ។ "
            "ប្រភេទ Link នេះអាចប្រើ API ឬប្រព័ន្ធផ្ទុកវីដេអូដាច់ដោយឡែក។"
        )

    if "no video formats found" in t:

        return (
            "TikTok មិនផ្តល់ប្រភពវីដេអូមក Server នេះទេ។ "
            "អាចបណ្តាលមកពីការរារាំង IP ឬប្រភពវីដេអូមិនអាចចូលប្រើបាន។"
        )

    if (
        "ip address is blocked" in t
        or "blocked" in t
        or "403" in t
        or "429" in t
    ):

        return (
            "គេហទំព័របានរារាំង Server នេះ។ "
            "សូមសាកល្បងលើកុំព្យូទ័រផ្ទាល់ខ្លួន។"
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

    if "unsupported url" in t:

        return (
            "Link នេះមិនត្រូវបានគាំទ្រដោយ yt-dlp ទេ។"
        )

    if "ffmpeg" in t:

        return (
            "ត្រូវការ ffmpeg។ "
            "សូមបន្ថែម packages.txt ដែលមាន ffmpeg។"
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
        "សូមពិនិត្យ Link ឬសាកល្បងម្តងទៀត។"
    )


if st.button("Download", type="primary"):

    raw = link.strip()

    if not raw:

        st.warning(
            "សូមដាក់ Link ជាមុនសិន"
        )

        st.stop()

    orig_url = extract_url(raw)

    url = orig_url

    has_ffmpeg = shutil.which("ffmpeg") is not None

    tmp_dir = tempfile.mkdtemp()

    errors = []

    videos = []

    results = []

    try:

        with st.spinner("កំពុងពិនិត្យ Link ..."):

            url = resolve_short_link(url)

        # ---------------------------------
        # TikTok Short Drama
        # ---------------------------------

        if is_shortdrama_url(url):

            st.info(
                "បានរកឃើញ Link TikTok Short Drama។ "
                "កំពុងសាកស្វែងរកប្រភពវីដេអូ..."
            )

            try:

                download_shortdrama_episode(
                    url,
                    tmp_dir,
                )

                videos = find_videos(tmp_dir)

            except Exception as e:

                errors.append(
                    "[Short Drama] " + str(e)
                )

        # ---------------------------------
        # TikTok / Other platforms
        # ---------------------------------

        if not videos and not is_shortdrama_url(url):

            with st.spinner("កំពុងពិនិត្យ Playlist ..."):

                playlist = is_playlist_link(url)

            attempts = build_attempts(
                url,
                has_ffmpeg,
                playlist,
            )

            with st.spinner("កំពុងទាញយក..."):

                for n, opt in enumerate(
                    attempts,
                    start=1,
                ):

                    opt["outtmpl"] = os.path.join(
                        tmp_dir,
                        f"a{n}_%(playlist_index|0)03d_%(id)s.%(ext)s",
                    )

                    try:

                        with yt_dlp.YoutubeDL(opt) as ydl:

                            ydl.download([url])

                    except Exception as e:

                        errors.append(
                            f"[ព្យាយាមទី {n}] {e}"
                        )

                    videos = find_videos(tmp_dir)

                    if videos:
                        break

            # TikTok normal video fallback
            if (
                not videos
                and "tiktok.com" in url.lower()
            ):

                variants = []

                for cand in (
                    orig_url,
                    url.split("?")[0],
                    url,
                ):

                    if cand and cand not in variants:
                        variants.append(cand)

                for cand in variants:

                    try:

                        download_via_tikwm(
                            cand,
                            tmp_dir,
                        )

                    except Exception as e:

                        errors.append(
                            f"[TikWM {cand[:60]}] {e}"
                        )

                    videos = find_videos(tmp_dir)

                    if videos:
                        break

        # ---------------------------------
        # Read video files
        # ---------------------------------

        if videos:

            for name in videos:

                path = os.path.join(
                    tmp_dir,
                    name,
                )

                with open(path, "rb") as f:

                    results.append(
                        (name, f.read())
                    )

    finally:

        shutil.rmtree(
            tmp_dir,
            ignore_errors=True,
        )

    # ---------------------------------
    # Error display
    # ---------------------------------

    if not results:

        err_text = (
            "\n".join(errors)
            if errors
            else "មិនមានព័ត៌មាន Error ទេ"
        )

        st.error(
            "មិនអាចទាញយកបានទេ។ "
            + friendly_hint(err_text)
        )

        with st.expander(
            "មើលព័ត៌មាន Error លម្អិត"
        ):

            st.code(err_text)

        st.stop()

    # ---------------------------------
    # Success display
    # ---------------------------------

    st.success(
        f"ទាញយកបាន {len(results)} វីដេអូ ✅"
    )

    for i, (name, data) in enumerate(
        results,
        start=1,
    ):

        ext = os.path.splitext(name)[1].lower()

        st.markdown(
            f"**វីដេអូទី {i}**"
        )

        if len(results) == 1:

            st.video(data)

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

    # ---------------------------------
    # ZIP download
    # ---------------------------------

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
    "ប្រើសម្រាប់វីដេអូសាធារណៈ និងការប្រើប្រាស់ដែលមានការអនុញ្ញាត។ "
    "សូមគោរពសិទ្ធិម្ចាស់វីដេអូ និងលក្ខខណ្ឌរបស់គេហទំព័រនីមួយៗ។"
        )
