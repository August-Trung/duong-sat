from __future__ import annotations

import re
import sqlite3

import requests
from bs4 import BeautifulSoup


TIME_RE = re.compile(r"^(?P<time>\d{2}:\d{2})(?:\s*\(ngày \+(?P<offset>\d+)\))?$")
REQUEST_HEADERS = {
    "User-Agent": "BienHoaRailWatch/0.1 (+https://giotaugiave.dsvn.vn/)",
    "Accept-Language": "vi,en;q=0.8",
}


def fetch_and_store_schedules(conn: sqlite3.Connection, config: dict) -> int:
    source_url = config["schedules"]["source_url"]
    monitored_stations = {str(item).strip() for item in config["schedules"]["stations"]}

    response = requests.get(source_url, timeout=30, headers=REQUEST_HEADERS)
    response.raise_for_status()
    response.encoding = response.encoding or "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    inserted = 0
    for route_name, direction, table in _iter_schedule_tables(soup):
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = [cell.get_text(" ", strip=True) for cell in rows[0].find_all(["th", "td"])]
        train_numbers = header_cells[2:]

        for row in rows[1:]:
            cells = [cell.get_text(" ", strip=True).replace("\xa0", " ") for cell in row.find_all(["th", "td"])]
            if len(cells) < 3:
                continue
            station_name = cells[0]
            if station_name not in monitored_stations:
                continue

            km = _safe_int(cells[1])
            for index, raw_value in enumerate(cells[2:]):
                clean_value = " ".join(raw_value.split())
                if not clean_value:
                    continue
                parsed = _parse_time(clean_value)
                if not parsed:
                    continue

                conn.execute(
                    """
                    INSERT OR IGNORE INTO train_schedules (
                        source_name, source_url, route_name, direction, station_name,
                        km, train_no, pass_time, day_offset, raw_time_text
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "Đường sắt Việt Nam",
                        source_url,
                        route_name,
                        direction,
                        station_name,
                        km,
                        train_numbers[index],
                        parsed["time"],
                        parsed["day_offset"],
                        clean_value,
                    ),
                )
                inserted += conn.execute("SELECT changes()").fetchone()[0]

    conn.commit()
    return inserted


def _iter_schedule_tables(soup: BeautifulSoup):
    tables = soup.find_all("table")
    for table in tables:
        first_row = table.find("tr")
        if not first_row:
            continue
        header_text = first_row.get_text(" ", strip=True)
        if "Tên Ga" not in header_text:
            continue

        heading = table.find_previous(["h3", "h4"])
        route_name = "Giờ tàu"
        direction = "unknown"
        if heading:
            route_name = heading.get_text(" ", strip=True)
            direction = route_name.replace("Chiều", "").strip()
        yield route_name, direction, table


def _parse_time(value: str) -> dict | None:
    match = TIME_RE.match(value)
    if not match:
        return None
    return {
        "time": match.group("time"),
        "day_offset": int(match.group("offset") or "0"),
    }


def _safe_int(value: str) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
