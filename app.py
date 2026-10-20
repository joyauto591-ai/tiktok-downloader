import re
import html
import base64
import io
import zipfile
import time
import requests
import streamlit as st
from urllib.parse import urlparse

# =========================
# CONFIG
# =========================

APP_NAME = "Video Downloader"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

SSSTIK_BASE = "https://ssstik.io"

HEADERS = {
    "User-Agent": UA,
    "Accept-Language": "en-US,en;q=0.9",
}

# =========================
# STREAMLIT UI
# =========================

st.set_page_config(
    page_title=APP_NAME,
    page_icon="🎬",
    layout="centered",
)

st.markdown(
    """
    <style>
    #MainMenu {
        visibility: hidden;
    }

    header {
        visibility: hidden;
        height: 0;
    }

    footer {
        visibility: hidden;
    }

    .stDeployButton {
        display: none;
    }

    .stApp {
        background: linear-gradient(
            135deg,
            #5b3df0 0%,
            #8a2be2 50%,
            #d100ff 100%
        );
    }

    h1, p, label, .stMarkdown {
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

    .info-box {
        background: rgba(255,255,255,0.12);
        padding: 18px;
        border-radius: 16px;
        margin-top: 15px;
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# TITLE
# =========================

st.title("🎬 Video Downloader")

st.caption(
    "TikTok Short Drama Downloader"
)

st.markdown(
    """
    <div class="info-box">
    ទាញយក Episode ច្រើនក្នុងពេលតែមួយ
    ហើយបញ្ចូលជាឯកសារ ZIP មួយ។
    </div>
    """,
    unsafe_allow_html=True,
)

# =========================
# INPUT
# =========================

link = st.text_input(
    "Short Drama Link",
    placeholder="Paste TikTok Short Drama Episode Link",
    label_visibility="visible",
)

col1, col2 = st.columns(2)

with col1:
    start_episode = st.number_input(
        "Episode ចាប់ផ្តើម",
        min_value=1,
        max_value=500,
        value=1,
        step=1,
    )

with col2:
    end_episode = st.number_input(
        "Episode បញ្ចប់",
        min_value=1,
        max_value=500,
        value=70,
        step=1,
    )

# =========================
# URL FUNCTIONS
# =========================

def extract_url(text):
    text = text.strip()

    for part in text.replace("\n", " ").split():
        if part.startswith(("http://", "https://")):
            return part.strip()

    return text


def validate_url(url):
    try:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            return False

        host = parsed.netloc.lower()

        allowed = (
            "tiktok.com",
            "www.tiktok.com",
            "vt.tiktok.com",
            "vm.tiktok.com",
        )

        return any(
            host == item or host.endswith("." + item)
            for item in allowed
        )

    except Exception:
        return False


def make_episode_url(url, episode_number):
    """
    ប្ដូរលេខ Episode នៅចុង URL។
    ឧទាហរណ៍:
    /shortdrama/episode/12345/3
    ទៅ:
    /shortdrama/episode/12345/4
    """

    parsed = urlparse(url)

    path = parsed.path.rstrip("/")

    match = re.search(
        r"(/shortdrama/episode/[^/]+)/(\d+)$",
        path,
        flags=re.I,
    )

    if not match:
        raise RuntimeError(
            "Link មិនមែនជា Short Drama Episode Link "
            "ដែលមានលេខ Episode នៅចុង URL ទេ។"
    )

    new_path = (
        match.group(1)
        + "/"
        + str(episode_number)
    )

    return parsed._replace(
        path=new_path,
        query="",
        fragment="",
    ).geturl()


# =========================
# SSSTIK FUNCTIONS
# =========================

def get_ssstik_token(session):

    response = session.get(
        SSSTIK_BASE + "/en",
        headers={
            **HEADERS,
            "Referer": SSSTIK_BASE + "/",
        },
        timeout=30,
    )

    response.raise_for_status()

    page = response.text

    match = re.search(
        r"s_tt\s*=\s*['\"]([^'\"]+)['\"]",
        page,
    )

    if not match:
        match = re.search(
            r"tt\s*:\s*['\"]([^'\"]+)['\"]",
            page,
        )

    if not match:
        raise RuntimeError(
            "រកមិនឃើញ SSSTik Token។"
        )

    token = match.group(1)

    furl_match = re.search(
        r"s_furl\s*=\s*['\"]([^'\"]+)['\"]",
        page,
    )

    endpoint = (
        furl_match.group(1)
        if furl_match
        else "abc"
    )

    return token, endpoint


def clean_html(text):
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", "", text)

    return text.strip()


def decode_ssstik_link(url):

    if "ssscdn.io" not in url:
        return url

    try:
        parts = url.split("/")

        encoded = "/".join(parts[5:])

        decoded = base64.b64decode(
            encoded
        ).decode("utf-8")

        if decoded.startswith("http"):
            return decoded

    except Exception:
        pass

    return url


def parse_ssstik_response(page):

    links = re.findall(
        r'<a\b([^>]*?)>',
        page,
        flags=re.I,
    )

    video_links = []

    for attrs in links:

        class_match = re.search(
            r'class=["\']([^"\']*)["\']',
            attrs,
            flags=re.I,
        )

        href_match = re.search(
            r'href=["\']([^"\']+)["\']',
            attrs,
            flags=re.I,
        )

        if not href_match:
            continue

        href = html.unescape(
            href_match.group(1)
        )

        if not href.startswith("http"):
            continue

        css_class = (
            class_match.group(1)
            if class_match
            else ""
        )

        if (
            "without_watermark" in css_class
            or "download_link" in css_class
            or "dl-button" in css_class
        ):

            href = decode_ssstik_link(href)

            if href not in video_links:
                video_links.append(href)

    if not video_links:

        matches = re.findall(
            r'href=["\'](https?://[^"\']+)["\']',
            page,
            flags=re.I,
        )

        for href in matches:

            href = html.unescape(href)

            if (
                ".mp4" in href.lower()
                or "ssscdn" in href.lower()
                or "tikcdn" in href.lower()
            ):

                href = decode_ssstik_link(href)

                if href not in video_links:
                    video_links.append(href)

    return video_links


def download_from_ssstik(url):

    session = requests.Session()

    session.headers.update(HEADERS)

    try:

        token, endpoint = get_ssstik_token(
            session
        )

        payload = {
            "id": url,
            "locale": "en",
            "tt": token,
        }

        headers = {
            **HEADERS,
            "Origin": SSSTIK_BASE,
            "Referer": SSSTIK_BASE + "/en",
            "HX-Current-URL": SSSTIK_BASE + "/en",
            "HX-Request": "true",
            "HX-Target": "target",
            "HX-Trigger": "_gcaptcha_pt",
            "Content-Type": (
                "application/x-www-form-urlencoded"
            ),
        }

        response = session.post(
            f"{SSSTIK_BASE}/{endpoint}?url=dl",
            data=payload,
            headers=headers,
            timeout=60,
        )

        response.raise_for_status()

        video_links = parse_ssstik_response(
            response.text
        )

        if not video_links:

            message = clean_html(
                response.text[:1000]
            )

            raise RuntimeError(
                "SSSTik មិនបានបញ្ជូន Link វីដេអូមកវិញ។ "
                + message
            )

        return video_links

    finally:
        session.close()


# =========================
# VIDEO DOWNLOAD
# =========================

def fetch_video(video_url):

    response = requests.get(
        video_url,
        headers={
            "User-Agent": UA,
            "Referer": SSSTIK_BASE + "/",
        },
        stream=True,
        timeout=120,
    )

    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        "",
    ).lower()

    if (
        "text/html" in content_type
        or "application/json" in content_type
    ):

        response.close()

        raise RuntimeError(
            "Link មិនមែនជា Video File ទេ។"
        )

    buffer = io.BytesIO()

    try:

        for chunk in response.iter_content(
            chunk_size=1024 * 256
        ):

            if chunk:
                buffer.write(chunk)

    finally:
        response.close()

    data = buffer.getvalue()

    if not data:
        raise RuntimeError(
            "Video File ទទេ។"
        )

    return data


# =========================
# BULK DOWNLOAD
# =========================

def download_all_episodes(
    base_url,
    first_episode,
    last_episode,
):

    zip_buffer = io.BytesIO()

    successful = []
    failed = []

    total = last_episode - first_episode + 1

    progress = st.progress(0)

    status = st.empty()

    with zipfile.ZipFile(
        zip_buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
    ) as zip_file:

        for index, episode in enumerate(
            range(first_episode, last_episode + 1),
            start=1,
        ):

            episode_url = make_episode_url(
                base_url,
                episode,
            )

            status.info(
                f"កំពុងទាញយក Episode {episode} "
                f"({index}/{total})"
            )

            try:

                # រក Link តាម SSSTik
                video_links = download_from_ssstik(
                    episode_url
                )

                # យក Link វីដេអូដំបូង
                video_url = video_links[0]

                # ទាញយកវីដេអូ
                video_data = fetch_video(
                    video_url
                )

                # ដាក់វីដេអូចូល ZIP
                zip_file.writestr(
                    f"Episode_{episode:03d}.mp4",
                    video_data,
                )

                successful.append(episode)

            except Exception as error:

                failed.append(
                    {
                        "episode": episode,
                        "error": str(error),
                    }
                )

            progress.progress(
                index / total
            )

            # សម្រាកបន្តិច ដើម្បីកុំផ្ញើ Request លឿនពេក
            time.sleep(1)

    status.success(
        "ការទាញយកបានបញ្ចប់។"
    )

    zip_buffer.seek(0)

    return (
        zip_buffer.getvalue(),
        successful,
        failed,
    )


# =========================
# MAIN
# =========================

if st.button(
    "⬇️ Download All Episodes",
    type="primary",
):

    raw = link.strip()

    if not raw:

        st.warning(
            "សូមដាក់ Short Drama Link ជាមុនសិន។"
        )

        st.stop()

    url = extract_url(raw)

    if not validate_url(url):

        st.error(
            "Link មិនត្រឹមត្រូវ។ "
            "សូមប្រើ TikTok Short Drama Link។"
        )

        st.stop()

    if start_episode > end_episode:

        st.error(
            "Episode ចាប់ផ្តើមមិនអាចធំជាង "
            "Episode បញ្ចប់បានទេ។"
        )

        st.stop()

    try:

        # ពិនិត្យថា Link មានទម្រង់ Episode ត្រឹមត្រូវ
        make_episode_url(
            url,
            int(start_episode),
        )

        with st.spinner(
            "កំពុងចាប់ផ្តើមទាញយក..."
        ):

            zip_data, successful, failed = (
                download_all_episodes(
                    url,
                    int(start_episode),
                    int(end_episode),
            )
        )

        st.success(
            f"ទាញយកបាន {len(successful)} Episode "
            f"ក្នុងចំណោម "
            f"{end_episode - start_episode + 1} Episode។"
        )

        if successful:

            st.download_button(
                label="📦 Download All Videos (ZIP)",
                data=zip_data,
                file_name="Short_Drama_Episodes.zip",
                mime="application/zip",
            )

        if failed:

            st.warning(
                f"ទាញយកមិនបាន {len(failed)} Episode។"
            )

            with st.expander(
                "មើល Episode ដែលបរាជ័យ"
            ):

                for item in failed:

                    st.write(
                        f"Episode {item['episode']}: "
                        f"{item['error']}"
                    )

    except Exception as error:

        st.error(
            "មិនអាចចាប់ផ្តើមទាញយកបានទេ។"
        )

        with st.expander(
            "មើល Error លម្អិត"
        ):

            st.code(str(error))


# =========================
# FOOTER
# =========================

st.divider()

st.caption(
    "សូមគោរពសិទ្ធិម្ចាស់វីដេអូ "
    "និងលក្ខខណ្ឌប្រើប្រាស់របស់ TikTok។"
)
