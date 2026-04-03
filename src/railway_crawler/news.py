from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import sqlite3
import urllib.parse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup
from googlenewsdecoder import gnewsdecoder


REQUEST_HEADERS = {
    "User-Agent": "BienHoaRailWatch/0.1 (+https://news.google.com/)",
    "Accept-Language": "vi,en;q=0.8",
}


def resolve_article_assets(url: str, *, timeout: int = 20) -> dict[str, str | None]:
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    return _fetch_article_metadata(session, url, timeout=timeout)


def fetch_and_store_news(conn: sqlite3.Connection, config: dict) -> int:
    queries = config["news"]["queries"]
    language = config["news"]["language"]
    country = config["news"]["country"]
    edition = config["news"]["edition"]
    area = config["area"]
    matching = config["matching"]
    days_back = int(config["news"].get("days_back", 365))
    threshold = datetime.now(timezone.utc) - timedelta(days=days_back)

    inserted = 0
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    metadata_cache: dict[str, dict[str, str | None]] = {}
    for query in queries:
        rss_url = (
            "https://news.google.com/rss/search?"
            + urllib.parse.urlencode(
                {
                    "q": query,
                    "hl": language,
                    "gl": country,
                    "ceid": edition,
                }
            )
        )

        response = session.get(rss_url, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        for item in root.findall("./channel/item"):
            title = _get_text(item, "title")
            url = _get_text(item, "link")
            description = html.unescape(_get_text(item, "description"))
            summary, publisher = _parse_description(description)
            metadata = metadata_cache.get(url)
            if metadata is None:
                metadata = _fetch_article_metadata(session, url)
                metadata_cache[url] = metadata
            published_at = _parse_datetime(_get_text(item, "pubDate"))
            if published_at and datetime.fromisoformat(published_at) < threshold:
                continue
            location_hint = _detect_location_hint(title, summary, area)
            severity_score = _score_severity(f"{title} {summary}", matching["severe_keywords"])

            conn.execute(
                """
                INSERT INTO news_articles (
                    source_name, title, url, external_url, image_url, publisher, published_at, summary,
                    matched_query, location_hint, severity_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title = excluded.title,
                    external_url = excluded.external_url,
                    image_url = excluded.image_url,
                    publisher = excluded.publisher,
                    published_at = excluded.published_at,
                    summary = excluded.summary,
                    matched_query = excluded.matched_query,
                    location_hint = excluded.location_hint,
                    severity_score = excluded.severity_score
                """,
                (
                    "Google News RSS",
                    title,
                    url,
                    metadata.get("external_url"),
                    metadata.get("image_url"),
                    publisher,
                    published_at,
                    summary,
                    query,
                    location_hint,
                    severity_score,
                ),
            )
            inserted += conn.execute("SELECT changes()").fetchone()[0]

    conn.commit()
    return inserted


def _get_text(element: ET.Element, tag: str) -> str:
    node = element.find(tag)
    return node.text.strip() if node is not None and node.text else ""


def _parse_description(description_html: str) -> tuple[str, str | None]:
    soup = BeautifulSoup(description_html, "html.parser")
    links = soup.find_all("a")
    summary = links[0].get_text(" ", strip=True) if links else soup.get_text(" ", strip=True)
    publisher = links[1].get_text(" ", strip=True) if len(links) > 1 else None
    return summary, publisher


def _fetch_article_metadata(session: requests.Session, url: str, *, timeout: int = 20) -> dict[str, str | None]:
    source_url = _decode_google_news_url(url)
    if source_url:
        try:
            response = session.get(source_url, timeout=timeout, allow_redirects=True)
            response.raise_for_status()
            external_url = str(response.url or "").strip() or source_url
            image_url = _extract_first_article_image(response.text, external_url)
            return {
                "external_url": external_url,
                "image_url": image_url,
            }
        except requests.RequestException:
            pass

    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
    except requests.RequestException:
        return {"external_url": None, "image_url": None}

    external_url = str(response.url or "").strip() or None
    image_url = _extract_article_image(response.text, external_url)
    return {
        "external_url": external_url,
        "image_url": image_url,
    }


def _decode_google_news_url(url: str) -> str | None:
    try:
        result = gnewsdecoder(url, interval=1)
    except Exception:
        return None
    if not result or not result.get("status"):
        return None
    decoded = str(result.get("decoded_url") or "").strip()
    return decoded or None


def _extract_article_image(html_text: str, base_url: str | None) -> str | None:
    image_url = _extract_first_article_image(html_text, base_url)
    if image_url:
        return image_url

    soup = BeautifulSoup(html_text, "html.parser")
    selectors = (
        ("meta", "property", "og:image"),
        ("meta", "name", "og:image"),
        ("meta", "name", "twitter:image"),
        ("meta", "property", "twitter:image"),
    )
    for tag_name, attr_name, attr_value in selectors:
        node = soup.find(tag_name, attrs={attr_name: attr_value})
        if node and node.get("content"):
            return urllib.parse.urljoin(base_url or "", node["content"].strip())

    image = soup.find("img")
    if image and image.get("src"):
        return urllib.parse.urljoin(base_url or "", image["src"].strip())
    return None


def _extract_first_article_image(html_text: str, base_url: str | None) -> str | None:
    soup = BeautifulSoup(html_text, "html.parser")
    containers = []
    for selector in ("article", "main", "[role='main']", ".article", ".post-content", ".entry-content", ".article-content"):
        containers.extend(soup.select(selector))
    containers.append(soup)

    for container in containers:
        for image in container.find_all("img"):
            candidate = _normalize_image_candidate(image, base_url)
            if candidate:
                return candidate
    return None


def _normalize_image_candidate(image, base_url: str | None) -> str | None:
    src = _pick_image_source(image)
    if not src:
        return None
    if src.startswith("data:"):
        return None

    text = " ".join(
        str(image.get(key) or "").lower()
        for key in ("alt", "class", "src", "data-src", "data-original", "data-srcset", "srcset")
    )
    if any(token in text for token in ("logo", "icon", "avatar", "sprite", "banner-google-news")):
        return None

    width = _safe_int(image.get("width"))
    height = _safe_int(image.get("height"))
    if width and width < 80:
        return None
    if height and height < 80:
        return None

    return urllib.parse.urljoin(base_url or "", src)


def _pick_image_source(image) -> str:
    for key in ("data-src", "data-original", "data-lazy-src", "src"):
        value = str(image.get(key) or "").strip()
        if value:
            return value

    for key in ("data-srcset", "srcset"):
        value = str(image.get(key) or "").strip()
        if value:
            first = value.split(",")[0].strip().split(" ")[0].strip()
            if first:
                return first
    return ""


def _safe_int(value: object) -> int | None:
    try:
        if value in (None, ""):
            return None
        return int(str(value).strip().replace("px", ""))
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: str) -> str | None:
    if not value:
        return None
    return parsedate_to_datetime(value).isoformat()


def _detect_location_hint(text_a: str, text_b: str, area: dict) -> str:
    merged = f"{text_a} {text_b}".lower()
    hints = []
    for value in area.values():
        if value.lower() in merged:
            hints.append(value)
    return ", ".join(hints)


def _score_severity(text: str, keywords: list[str]) -> int:
    merged = text.lower()
    score = 0
    for keyword in keywords:
        if keyword.lower() in merged:
            score += 1
    return score
