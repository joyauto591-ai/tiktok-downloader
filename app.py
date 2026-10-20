import io
import os
import shutil
import tempfile
import zipfile

import requests
import streamlit as st
import yt_dlp

MAX_VIDEOS = 20  # ចំនួនវីដេអូអតិបរមា បើ link ជា profile ឬ playlist

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
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
st.caption("TikTok • Facebook • YouTube • Instagram • X • និងគេហទំព័រផ្សេងទៀត (សម្រាប់មើលផ្ទាល់ខ្លួនប៉ុណ្ណោះ)")

link = st.text_input(
    "Link",
    placeholder="Insert a link here",
    label_visibility="collapsed",
)


def extract_url(text):
    """ទាញយក URL ពីអត្ថបទ (ករណី copy មកជាមួយពាក្យផ្សេង)"""
    for part in text.replace("\n", " ").split():
        if part.lower().startswith(("http://", "https://")):
            return part.strip()
    if "." in text and " " not in text:
        return "https://" + text.strip()
    return text.strip()


def resolve_short_link(url):
    """បើជា link ខ្លី ឱ្យតាមទៅរក link ពេញ"""
    low = url.lower()
    if not any(h in low for h in SHORT_HOSTS):
        return url
    try:
        r = requests.get(
            url,
            headers={"User-Agent": UA},
            allow_redirects=True,
            timeout=15,
        )
        final = r.url
        if final and final.startswith("http"):
            return final
    except Exception:
        pass
    return url


def get_impersonate_target():
    """ប្រើ impersonate browser បើមាន curl_cffi (ជួយឆ្លងកាត់ការរារាំង)"""
    try:
        import curl_cffi  # noqa: F401
        from yt_dlp.networking.impersonate import ImpersonateTarget

        return ImpersonateTarget.from_str("chrome")
    except Exception:
        return None


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
                "http_headers": {"User-Agent": UA},
                "socket_timeout": 20,
            }
        ) as y:
            info = y.extract_info(url, download=False)
        return bool(info) and info.get("_type") == "playlist"
    except Exception:
        return False


def build_attempts(url, has_ffmpeg, playlist):
    """បង្កើតបញ្ជីវិធីព្យាយាមទាញយក (បរាជ័យវិធីមួយ ទៅវិធីបន្ទាប់)"""
    is_tiktok = "tiktok.com" in url.lower()
    imp = get_impersonate_target()

    if has_ffmpeg and not is_tiktok:
        formats = ["bv*[ext=mp4]+ba[ext=m4a]/bv*+ba/b", "best", None]
    elif is_tiktok:
        formats = ["best[format_id!=download]/best", "best", None]
    else:
        formats = ["best[ext=mp4]/best", "best", None]

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
                "tiktok": {"api_hostname": ["api22-normal-c-useast2a.tiktokv.com"]}
            }
        attempts.append(opt)
    return attempts


def download_via_tikwm(url, folder):
    """ជម្រើសបម្រុងសម្រាប់ TikTok ពេល yt-dlp បរាជ័យ (ប្រើសេវាកម្មភាគីទីបី)"""
    r = requests.post(
        "https://www.tikwm.com/api/",
        data={"url": url, "hd": 1},
        headers={"User-Agent": UA},
        timeout=30,
    )
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"tikwm: {j.get('msg')}")
    d = j.get("data") or {}
    play = d.get("hdplay") or d.get("play")
    if not play:
        raise RuntimeError("tikwm: រកមិនឃើញ link វីដេអូ (ប្រហែលជាប៉ុស្តិ៍រូបភាព)")
    if play.startswith("/"):
        play = "https://www.tikwm.com" + play
    vid = str(d.get("id") or "video")
    path = os.path.join(folder, f"tikwm_{vid}.mp4")
    with requests.get(
        play, headers={"User-Agent": UA}, stream=True, timeout=60
    ) as resp:
        resp.raise_for_status()
        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 256):
                if chunk:
                    f.write(chunk)


def find_videos(folder):
    names = sorted(os.listdir(folder))
    return [n for n in names if n.lower().endswith(tuple(MIME_TYPES))]


def friendly_hint(err_text):
    t = err_text.lower()
    if "no video formats found" in t:
        return "គេហទំព័រមិនផ្តល់ link វីដេអូមក server នេះទេ (ប្រហែលជារារាំង IP ឬជាប៉ុស្តិ៍រូបភាព)។"
    if "ip address is blocked" in t or "blocked" in t or "403" in t or "429" in t:
        return "គេហទំព័របានរារាំង server នេះ (IP របស់ Streamlit Cloud)។ សូមសាកល្បង link ផ្សេង ឬដំណើរការ app លើកុំព្យូទ័រផ្ទាល់ខ្លួន។"
    if "private" in t or "login" in t or "sign in" in t or "cookies" in t:
        return "វីដេអូនេះអាចជា private ឬត្រូវការ login។"
    if "unsupported url" in t:
        return "link នេះមិនត្រូវបានគាំទ្រ ឬមិនមែនជា link វីដេអូ។"
    if "ffmpeg" in t:
        return "ត្រូវការ ffmpeg។ សូមបន្ថែមឯកសារ packages.txt ដែលមាន ffmpeg រួច reboot app។"
    if "unavailable" in t or "not available" in t or "removed" in t:
        return "វីដេអូនេះលែងមាន ឬត្រូវបានលុប។"
    return "សូមសាកល្បងម្តងទៀត ឬ update yt-dlp (reboot app)។"


if st.button("Download", type="primary"):
    raw = link.strip()

    if not raw:
        st.warning("សូមដាក់ link ជាមុនសិន")
        st.stop()

    has_ffmpeg = shutil.which("ffmpeg") is not None
    url = extract_url(raw)

    with st.spinner("កំពុងពិនិត្យ link ..."):
        url = resolve_short_link(url)
        playlist = is_playlist_link(url)

    tmp_dir = tempfile.mkdtemp()
    errors = []
    videos = []
    results = []  # (name, bytes)

    try:
        attempts = build_attempts(url, has_ffmpeg, playlist)

        with st.spinner("កំពុងទាញយក..."):
            for n, opt in enumerate(attempts, start=1):
                opt["outtmpl"] = os.path.join(
                    tmp_dir, f"a{n}_%(playlist_index|0)03d_%(id)s.%(ext)s"
                )
                try:
                    with yt_dlp.YoutubeDL(opt) as ydl:
                        ydl.download([url])
                except Exception as e:  # noqa: BLE001
                    errors.append(f"[ព្យាយាមទី {n}] {e}")

                videos = find_videos(tmp_dir)
                if videos:
                    break

            if not videos and "tiktok.com" in url.lower():
                try:
                    download_via_tikwm(url, tmp_dir)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"[ជម្រើសបម្រុង] {e}")
                videos = find_videos(tmp_dir)

        if videos:
            for name in videos:
                with open(os.path.join(tmp_dir, name), "rb") as f:
                    results.append((name, f.read()))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if not results:
        err_text = "\n".join(errors) if errors else "មិនមានព័ត៌មាន error ទេ"
        st.error("មិនអាចទាញយកបានទេ។ " + friendly_hint(err_text))
        with st.expander("មើលព័ត៌មាន error លម្អិត"):
            st.code(err_text)
        st.stop()

    st.success(f"ទាញយកបាន {len(results)} វីដេអូ ✅")

    for i, (name, data) in enumerate(results, start=1):
        ext = os.path.splitext(name)[1].lower()
        st.markdown(f"**វីដេអូទី {i}**")
        if len(results) == 1:
            st.video(data)
        st.download_button(
            f"⬇️ Download ({name[:30]})",
            data=data,
            file_name=name,
            mime=MIME_TYPES.get(ext, "video/mp4"),
            key=f"vid_{i}",
            on_click="ignore",
        )

    if len(results) > 1:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            for name, data in results:
                zf.writestr(name, data)
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
