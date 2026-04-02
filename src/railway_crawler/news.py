from __future__ import annotations

from email.utils import parsedate_to_datetime
import html
import sqlite3
import urllib.parse
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup


def fetch_and_store_news(conn: sqlite3.Connection, config: dict) -> int:
    queries = config["news"]["queries"]
    language = config["news"]["language"]
    country = config["news"]["country"]
    edition = config["news"]["edition"]
    area = config["area"]
    matching = config["matching"]

    inserted = 0
    session = requests.Session()
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
            published_at = _parse_datetime(_get_text(item, "pubDate"))
            location_hint = _detect_location_hint(title, summary, area)
            severity_score = _score_severity(f"{title} {summary}", matching["severe_keywords"])

            conn.execute(
                """
                INSERT INTO news_articles (
                    source_name, title, url, publisher, published_at, summary,
                    matched_query, location_hint, severity_score
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(url) DO UPDATE SET
                    title = excluded.title,
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
