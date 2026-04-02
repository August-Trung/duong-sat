from __future__ import annotations

import json
import random
import sqlite3
from datetime import date, timedelta


def seed_fake_data(conn: sqlite3.Connection, reset: bool = True) -> dict[str, int]:
    if reset:
        _reset_tables(conn)

    crossings = _build_crossings()
    crossing_id_map = _insert_crossings(conn, crossings)

    schedules = _build_schedules()
    _insert_schedules(conn, schedules)

    articles = _build_articles(crossings)
    _insert_articles(conn, articles)

    incidents = _build_incidents(crossings, crossing_id_map)
    _insert_incidents(conn, incidents)

    snapshots = _build_risk_snapshots(crossings, crossing_id_map)
    _insert_risk_snapshots(conn, snapshots)

    conn.commit()
    return {
        "crossings": len(crossings),
        "schedules": len(schedules),
        "articles": len(articles),
        "incidents": len(incidents),
        "risks": len(snapshots),
    }


def _reset_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM auth_sessions")
    conn.execute("DELETE FROM risk_snapshots")
    conn.execute("DELETE FROM incident_reports")
    conn.execute("DELETE FROM news_articles")
    conn.execute("DELETE FROM train_schedules")
    conn.execute("DELETE FROM crossings")


def _build_crossings() -> list[dict]:
    wards = [
        "Quang Vinh",
        "Tân Biên",
        "Long Bình",
        "Tam Hiệp",
        "Trảng Dài",
        "An Bình",
        "Phước Tân",
        "Hố Nai",
        "Bửu Long",
        "Tân Hòa",
        "Long Hưng",
        "Thống Nhất",
    ]
    road_names = [
        "Đường Võ Thị Sáu",
        "Đường Hà Huy Giáp",
        "Đường Đồng Khởi",
        "Đường Bùi Văn Hòa",
        "Đường Nguyễn Ái Quốc",
        "Đường Phạm Văn Thuận",
        "Đường Xa lộ Hà Nội",
        "Đường Phan Trung",
        "Đường Nguyễn Văn Trị",
        "Đường Trần Quốc Toản",
        "Đường 30/4",
        "Đường Hoàng Minh Chánh",
    ]
    name_templates = [
        "Đường ngang ga Biên Hòa",
        "Lối đi tự mở khu vực Hố Nai",
        "Đường ngang Long Bình",
        "Lối dân sinh Tam Hiệp",
        "Đường ngang Amata",
        "Giao cắt Phước Tân",
        "Lối mở Trảng Dài",
        "Đường ngang An Bình",
        "Giao cắt Bửu Long",
        "Lối đi tự mở Tân Hòa",
        "Đường ngang Long Hưng",
        "Lối đi dân sinh Thống Nhất",
        "Giao cắt Hố Nai 3",
        "Đường ngang cầu Ghềnh",
        "Lối đi dân sinh ga Dĩ An",
        "Đường ngang Long Khánh",
        "Lối mở khu công nghiệp Biên Hòa 1",
        "Giao cắt khu công nghiệp Amata",
        "Đường ngang Suối Linh",
        "Lối dân sinh Tân Mai",
        "Đường ngang Bình Đa",
        "Lối mở cầu Đồng Nai",
        "Đường ngang Hóa An",
        "Giao cắt ga Trảng Bom",
    ]
    barrier_types = ["co_gac", "tu_dong", "khong_co"]
    crossing_types = ["duong_ngang_hop_phap", "loi_di_tu_mo"]
    verification_statuses = ["verified", "surveyed", "draft"]
    district_for_ward = {
        "Quang Vinh": "Biên Hòa",
        "Tân Biên": "Biên Hòa",
        "Long Bình": "Biên Hòa",
        "Tam Hiệp": "Biên Hòa",
        "Trảng Dài": "Biên Hòa",
        "An Bình": "Biên Hòa",
        "Phước Tân": "Biên Hòa",
        "Hố Nai": "Trảng Bom",
        "Bửu Long": "Biên Hòa",
        "Tân Hòa": "Biên Hòa",
        "Long Hưng": "Biên Hòa",
        "Thống Nhất": "Biên Hòa",
    }

    rows: list[dict] = []
    for idx, name in enumerate(name_templates, start=1):
        ward = wards[(idx - 1) % len(wards)]
        district = district_for_ward[ward]
        address = f"{road_names[(idx - 1) % len(road_names)]}, {ward}"
        rows.append(
            {
                "code": f"BH-{idx:03d}",
                "name": name,
                "address": address,
                "ward": ward,
                "district": district,
                "city": "Đồng Nai",
                "latitude": round(10.88 + ((idx * 17) % 115) / 1000, 6),
                "longitude": round(106.77 + ((idx * 13) % 145) / 1000, 6),
                "crossing_type": crossing_types[idx % len(crossing_types)],
                "barrier_type": barrier_types[idx % len(barrier_types)],
                "manager_name": f"Tổ điều phối số {idx}",
                "manager_phone": f"0900{idx:06d}",
                "verification_status": verification_statuses[idx % len(verification_statuses)],
                "coordinate_source": "Dữ liệu mô phỏng",
                "source_reference": f"seed://crossings/{idx}",
                "verification_notes": "Bản ghi phục vụ xem trước UI với dữ liệu giả lập.",
                "surveyed_at": f"2026-03-{(idx % 27) + 1:02d}",
                "verified_at": f"2026-03-{((idx + 6) % 27) + 1:02d}" if idx % 3 != 0 else None,
                "notes": f"Mô tả vận hành mẫu cho {name.lower()}.",
            }
        )
    return rows


def _insert_crossings(conn: sqlite3.Connection, crossings: list[dict]) -> dict[str, int]:
    id_map: dict[str, int] = {}
    for row in crossings:
        conn.execute(
            """
            INSERT INTO crossings (
                code, name, address, ward, district, city, latitude, longitude,
                crossing_type, barrier_type, manager_name, manager_phone,
                verification_status, coordinate_source, source_reference,
                verification_notes, surveyed_at, verified_at, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                name = excluded.name,
                address = excluded.address,
                ward = excluded.ward,
                district = excluded.district,
                city = excluded.city,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                crossing_type = excluded.crossing_type,
                barrier_type = excluded.barrier_type,
                manager_name = excluded.manager_name,
                manager_phone = excluded.manager_phone,
                verification_status = excluded.verification_status,
                coordinate_source = excluded.coordinate_source,
                source_reference = excluded.source_reference,
                verification_notes = excluded.verification_notes,
                surveyed_at = excluded.surveyed_at,
                verified_at = excluded.verified_at,
                notes = excluded.notes,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                row["code"],
                row["name"],
                row["address"],
                row["ward"],
                row["district"],
                row["city"],
                row["latitude"],
                row["longitude"],
                row["crossing_type"],
                row["barrier_type"],
                row["manager_name"],
                row["manager_phone"],
                row["verification_status"],
                row["coordinate_source"],
                row["source_reference"],
                row["verification_notes"],
                row["surveyed_at"],
                row["verified_at"],
                row["notes"],
            ),
        )
        saved = conn.execute("SELECT id FROM crossings WHERE code = ?", (row["code"],)).fetchone()
        id_map[row["code"]] = saved["id"]
    return id_map


def _build_schedules() -> list[dict]:
    stations = ["Biên Hòa", "Dĩ An", "Long Khánh", "Sài Gòn"]
    route_specs = [
        ("Tuyến SE", "Sài Gòn - Hà Nội"),
        ("Tuyến SE", "Hà Nội - Sài Gòn"),
        ("Tuyến TN", "Biên Hòa - Sài Gòn"),
        ("Tuyến TN", "Sài Gòn - Biên Hòa"),
    ]
    rows: list[dict] = []
    base_time = 5 * 60 + 20
    for route_idx, (route_name, direction) in enumerate(route_specs):
        for station_idx, station_name in enumerate(stations):
            for trip_idx in range(1, 9):
                total_minutes = base_time + route_idx * 40 + station_idx * 18 + trip_idx * 47
                hours = (total_minutes // 60) % 24
                minutes = total_minutes % 60
                rows.append(
                    {
                        "source_name": "Dữ liệu mô phỏng",
                        "source_url": f"seed://schedules/{route_idx + 1}/{station_idx + 1}/{trip_idx}",
                        "route_name": route_name,
                        "direction": direction,
                        "station_name": station_name,
                        "km": 10 + station_idx * 18 + trip_idx,
                        "train_no": f"{'SE' if route_idx < 2 else 'TN'}{route_idx + 1}{trip_idx}",
                        "pass_time": f"{hours:02d}:{minutes:02d}",
                        "day_offset": 1 if total_minutes >= 24 * 60 else 0,
                        "raw_time_text": f"{hours:02d}:{minutes:02d}",
                    }
                )
    return rows


def _insert_schedules(conn: sqlite3.Connection, schedules: list[dict]) -> None:
    for row in schedules:
        conn.execute(
            """
            INSERT INTO train_schedules (
                source_name, source_url, route_name, direction, station_name, km,
                train_no, pass_time, day_offset, raw_time_text
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_url, route_name, direction, station_name, train_no, raw_time_text) DO UPDATE SET
                source_name = excluded.source_name,
                km = excluded.km,
                pass_time = excluded.pass_time,
                day_offset = excluded.day_offset
            """,
            (
                row["source_name"],
                row["source_url"],
                row["route_name"],
                row["direction"],
                row["station_name"],
                row["km"],
                row["train_no"],
                row["pass_time"],
                row["day_offset"],
                row["raw_time_text"],
            ),
        )


def _build_articles(crossings: list[dict]) -> list[dict]:
    rows: list[dict] = []
    publishers = ["VnExpress", "Tuổi Trẻ", "Báo Đồng Nai", "Thanh Niên", "Dân Trí"]
    today = date(2026, 4, 1)
    severity_plan = {}
    for idx, crossing in enumerate(crossings):
        if idx < 5:
            severity_plan[crossing["code"]] = (8, 2)
        elif idx < 11:
            severity_plan[crossing["code"]] = (4, 1)
        elif idx < 17:
            severity_plan[crossing["code"]] = (2, 0)
        else:
            severity_plan[crossing["code"]] = (1, 0)

    article_id = 1
    for idx, crossing in enumerate(crossings):
        article_count, severe_hits = severity_plan[crossing["code"]]
        for article_idx in range(article_count):
            is_severe = article_idx < severe_hits
            title_prefix = "Cảnh báo nguy cơ cao tại" if is_severe else "Theo dõi an toàn tại"
            rows.append(
                {
                    "source_name": "Dữ liệu mô phỏng",
                    "title": f"{title_prefix} {crossing['name']}",
                    "url": f"https://seed.local/articles/{article_id}",
                    "publisher": publishers[(idx + article_idx) % len(publishers)],
                    "published_at": str(today - timedelta(days=(idx + article_idx) % 15)),
                    "summary": (
                        f"Bản tin mô phỏng về {crossing['name']} tại {crossing['address']}, {crossing['district']}."
                    ),
                    "matched_query": crossing["name"],
                    "location_hint": f"{crossing['ward']}, {crossing['district']}",
                    "severity_score": 3 if is_severe else 1,
                }
            )
            article_id += 1
    return rows


def _insert_articles(conn: sqlite3.Connection, articles: list[dict]) -> None:
    for row in articles:
        conn.execute(
            """
            INSERT INTO news_articles (
                source_name, title, url, publisher, published_at, summary,
                matched_query, location_hint, severity_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                source_name = excluded.source_name,
                title = excluded.title,
                publisher = excluded.publisher,
                published_at = excluded.published_at,
                summary = excluded.summary,
                matched_query = excluded.matched_query,
                location_hint = excluded.location_hint,
                severity_score = excluded.severity_score
            """,
            (
                row["source_name"],
                row["title"],
                row["url"],
                row["publisher"],
                row["published_at"],
                row["summary"],
                row["matched_query"],
                row["location_hint"],
                row["severity_score"],
            ),
        )


def _build_incidents(crossings: list[dict], id_map: dict[str, int]) -> list[dict]:
    rng = random.Random(42)
    rows: list[dict] = []
    today = date(2026, 4, 1)

    for idx, crossing in enumerate(crossings[:14], start=1):
        incident_count = 2 if idx <= 5 else 1
        for incident_idx in range(incident_count):
            rows.append(
                {
                    "crossing_id": id_map[crossing["code"]],
                    "title": f"Sự cố mô phỏng #{idx}-{incident_idx + 1} tại {crossing['name']}",
                    "incident_date": str(today - timedelta(days=idx * 2 + incident_idx)),
                    "severity_level": ["very_high", "high", "medium"][min(incident_idx, 2)] if idx <= 5 else "medium",
                    "casualties": 1 if idx <= 4 and incident_idx == 0 else 0,
                    "injured_count": rng.randint(0, 3) if idx <= 9 else rng.randint(0, 1),
                    "description": (
                        f"Bản ghi sự cố mô phỏng phục vụ kiểm thử giao diện cho {crossing['name']}."
                    ),
                    "source_url": f"https://seed.local/incidents/{idx}-{incident_idx + 1}",
                }
            )
    return rows


def _insert_incidents(conn: sqlite3.Connection, incidents: list[dict]) -> None:
    conn.executemany(
        """
        INSERT INTO incident_reports (
            crossing_id, title, incident_date, severity_level, casualties,
            injured_count, description, source_url
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                row["crossing_id"],
                row["title"],
                row["incident_date"],
                row["severity_level"],
                row["casualties"],
                row["injured_count"],
                row["description"],
                row["source_url"],
            )
            for row in incidents
        ],
    )


def _build_risk_snapshots(crossings: list[dict], id_map: dict[str, int]) -> list[dict]:
    rows: list[dict] = []
    for idx, crossing in enumerate(crossings):
        if idx < 5:
            score = 160 - idx * 11
            level = "very_high"
            article_count = 8
            severe_hits = 6
            incident_count = 2
            casualties = 1 if idx < 3 else 0
            injured = 3
        elif idx < 11:
            score = 92 - (idx - 5) * 6
            level = "high"
            article_count = 4
            severe_hits = 2
            incident_count = 1
            casualties = 0
            injured = 1
        elif idx < 17:
            score = 56 - (idx - 11) * 4
            level = "medium"
            article_count = 2
            severe_hits = 0
            incident_count = 0
            casualties = 0
            injured = 0
        else:
            score = max(6, 24 - (idx - 17) * 3)
            level = "low"
            article_count = 1 if idx % 2 == 0 else 0
            severe_hits = 0
            incident_count = 0
            casualties = 0
            injured = 0

        station_keyword = _guess_station_keyword(crossing["name"], crossing["address"])
        evidence = {
            "article_count": article_count,
            "severe_article_hits": severe_hits,
            "schedule_count": 16 if station_keyword else 0,
            "incident_count": incident_count,
            "incident_casualties": casualties,
            "incident_injured": injured,
            "barrier_type": crossing["barrier_type"],
            "crossing_type": crossing["crossing_type"],
            "station_keyword": station_keyword,
        }
        rows.append(
            {
                "crossing_id": id_map[crossing["code"]],
                "score": score,
                "level": level,
                "evidence_json": json.dumps(evidence, ensure_ascii=False),
            }
        )
    return rows


def _insert_risk_snapshots(conn: sqlite3.Connection, snapshots: list[dict]) -> None:
    conn.executemany(
        """
        INSERT INTO risk_snapshots (crossing_id, score, level, evidence_json)
        VALUES (?, ?, ?, ?)
        """,
        [(row["crossing_id"], row["score"], row["level"], row["evidence_json"]) for row in snapshots],
    )


def _guess_station_keyword(name: str, address: str) -> str | None:
    text = f"{name} {address}".lower()
    if any(token in text for token in ["biên hòa", "bien hoa", "long bình", "long binh", "hố nai", "ho nai"]):
        return "Biên Hòa"
    if "dĩ an" in text or "di an" in text:
        return "Dĩ An"
    if "long khánh" in text or "long khanh" in text:
        return "Long Khánh"
    return None
