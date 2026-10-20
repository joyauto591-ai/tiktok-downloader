import re
import html
import base64
import io
import os
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

st.title("🎬 Video Downloader")

st.caption(
    "TikTok • Short Drama • Facebook • YouTube • Instagram • X"
)

st.markdown(
    """
    <div class="info-box">
    ទាញយកវីដេអូ TikTok និង Short Drama
    ដោយប្រើ SSSTik។
    </div>
    """,
    unsafe_allow_html=True,
)

link = st.text_input(
    "Link",
    placeholder="Paste TikTok Short Drama link here",
    label_visibility="collapsed",
)

# =========================
# URL FUNCTIONS
# =========================

def extract_url(text):
    """
    ទាញយក URL ពីអត្ថបទដែលបាន Paste។
    """
    text = text.strip()

    for part in text.replace("\n", " ").split():
        if part.startswith(("http://", "https://")):
            return part.strip()

    return text


def validate_url(url):
    """
    ពិនិត្យ URL មុនផ្ញើទៅ SSSTik។
    """
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


# =========================
# SSSTIK FUNCTIONS
# =========================

def get_ssstik_token(session):
    """
    ទាញយក Token ថ្មីពី SSSTik។
    """

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

    # SSSTik token
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
            "រកមិនឃើញ SSSTik Token។ "
            "សេវា SSSTik អាចបានផ្លាស់ប្តូរប្រព័ន្ធ។"
        )

    token = match.group(1)

    # SSSTik form endpoint
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
    """
    សម្អាត HTML entities។
    """
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", "", text)

    return text.strip()


def decode_ssstik_link(url):
    """
    Decode Link របស់ ssscdn.io
    ប្រសិនបើវាជា Base64 URL។
    """

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
    """
    រក Link វីដេអូ MP4 ពី HTML របស់ SSSTik។
    """

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

        # Link វីដេអូគ្មាន Watermark
        if (
            "without_watermark" in css_class
            or "download_link" in css_class
            or "dl-button" in css_class
        ):
            href = decode_ssstik_link(href)

            if href not in video_links:
                video_links.append(href)

    # វិធីបម្រុង៖ រក Link MP4 ក្នុង HTML
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
    """
    ផ្ញើ TikTok URL ទៅ SSSTik
    ហើយទទួល Link ទាញយក។
    """

    session = requests.Session()

    session.headers.update(HEADERS)

    try:

        # 1. ទាញ Token
        token, endpoint = get_ssstik_token(
            session
        )

        # 2. ផ្ញើ Link ទៅ SSSTik
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

        # 3. Parse Link វីដេអូ
        video_links = parse_ssstik_response(
            response.text
        )

        if not video_links:

            message = clean_html(
                response.text[:1000]
            )

            raise RuntimeError(
                "SSSTik មិនបានបញ្ជូន Link វីដេអូមកវិញ។ "
                "អាចជាបញ្ហា Short Drama ឬ Server។\n"
                + message
            )

        return video_links

    finally:
        session.close()


# =========================
# VIDEO DOWNLOAD
# =========================

def fetch_video(video_url):
    """
    ទាញយក MP4 ពី Link ដែល SSSTik បានបញ្ជូន។
    """

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
        raise RuntimeError(
            "Link ដែល SSSTik បញ្ជូនមក "
            "មិនមែនជា Video File ទេ។"
        )

    buffer = io.BytesIO()

    for chunk in response.iter_content(
        chunk_size=1024 * 256
    ):
        if chunk:
            buffer.write(chunk)

    response.close()

    data = buffer.getvalue()

    if not data:
        raise RuntimeError(
            "Video File ទទេ។"
        )

    return data


# =========================
# MAIN
# =========================

if st.button("Download", type="primary"):

    raw = link.strip()

    if not raw:
        st.warning(
            "សូមដាក់ TikTok Link ជាមុនសិន។"
        )
        st.stop()

    url = extract_url(raw)

    if not validate_url(url):
        st.error(
            "Link មិនត្រឹមត្រូវ។ "
            "សូមប្រើ TikTok Video ឬ Short Drama Link។"
        )
        st.stop()

    try:

        with st.spinner(
            "កំពុងភ្ជាប់ទៅ SSSTik..."
        ):

            video_links = download_from_ssstik(
                url
            )

        st.success(
            f"រកឃើញ Link វីដេអូ {len(video_links)} ✅"
        )

        for i, video_url in enumerate(
            video_links,
            start=1,
        ):

            with st.spinner(
                f"កំពុងទាញយកវីដេអូទី {i}..."
            ):

                video_data = fetch_video(
                    video_url
                )

            st.video(video_data)

            st.download_button(
                label=f"⬇️ Download Video {i}",
                data=video_data,
                file_name=f"tiktok_video_{i}.mp4",
                mime="video/mp4",
                key=f"download_{i}",
            )

    except Exception as e:

        st.error(
            "មិនអាចទាញយកវីដេអូបានទេ។"
        )

        with st.expander(
            "មើល Error លម្អិត"
        ):
            st.code(str(e))


st.divider()

st.caption(
    "ប្រើសម្រាប់វីដេអូសាធារណៈ និងការប្រើប្រាស់ផ្ទាល់ខ្លួន។ "
    "សូមគោរពសិទ្ធិម្ចាស់វីដេអូ។"
            )
