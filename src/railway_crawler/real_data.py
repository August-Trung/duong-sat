from __future__ import annotations

from csv import DictReader, DictWriter
from datetime import datetime, timedelta
import json
import math
import shutil
from pathlib import Path
import sqlite3

from railway_crawler.db import init_db
from railway_crawler.risk import compute_risk
from railway_crawler.scene3d import parse_gpkg_osm, parse_osm_xml


DEFAULT_MARGIN_DEGREES = 0.035
DEFAULT_DEDUP_METERS = 35.0
REFERENCE_MATCH_METERS = 850.0
GENERIC_ROAD_KINDS: set[str] = set()
EXCLUDED_NAME_KEYWORDS = (
    "cầu vượt",
    "nút giao",
    "song hành",
)


def export_real_crossing_candidates(
    conn: sqlite3.Connection,
    *,
    output_path: str | Path,
    gpkg_path: str | Path | None = None,
    osm_path: str | Path | None = None,
    margin_degrees: float = DEFAULT_MARGIN_DEGREES,
    dedup_distance_meters: float = DEFAULT_DEDUP_METERS,
    cache_path: str | Path | None = None,
) -> dict[str, object]:
    if not gpkg_path and not osm_path:
        raise ValueError("Cần cung cấp --gpkg hoặc --osm để trích xuất điểm giao cắt thật.")

    area_bounds = _current_area_bounds(conn, margin_degrees)
    if area_bounds is None:
        raise ValueError("Không xác định được vùng làm việc từ DB hiện tại để khoanh khu vực crawl.")

    if gpkg_path:
        # Some Windows environments block creating extra sqlite cache files beside the repo.
        # Fall back to direct GPKG reads when cache creation is not available.
        try:
            osm_features = parse_gpkg_osm(gpkg_path, bbox=area_bounds, cache_path=cache_path)
        except sqlite3.OperationalError:
            osm_features = parse_gpkg_osm(gpkg_path, bbox=area_bounds, cache_path=None)
        source_label = f"gpkg:{Path(gpkg_path).name}"
    else:
        osm_features = parse_osm_xml(osm_path)
        source_label = f"osm:{Path(osm_path).name}"

    candidates = _extract_crossing_candidates(
        osm_features,
        city_hint=_guess_city_hint(conn),
        source_label=source_label,
        dedup_distance_meters=dedup_distance_meters,
    )

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    _write_crossing_candidates(output_file, candidates)

    summary_path = output_file.with_suffix(".summary.json")
    summary = {
      "count": len(candidates),
      "output": str(output_file),
      "format": output_file.suffix.lower() or ".csv",
      "source": source_label,
      "bbox": area_bounds,
      "sample": candidates[:5],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def export_incident_candidates_from_news(
    conn: sqlite3.Connection,
    *,
    output_path: str | Path,
    config: dict,
    days_back: int | None = None,
    apply_to_db: bool = False,
) -> dict[str, object]:
    window_days = days_back or int(config.get("news", {}).get("days_back", 365))
    candidates = _derive_incident_candidates(conn, config, window_days)

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding="utf-8")

    inserted = 0
    if apply_to_db:
        inserted = _store_incident_candidates(conn, candidates)

    return {
        "count": len(candidates),
        "inserted": inserted,
        "output": str(output_file),
        "days_back": window_days,
    }


def build_trial_database(
    *,
    source_db_path: str | Path,
    target_db_path: str | Path,
    crossings_source_path: str | Path,
) -> dict[str, object]:
    source_db = Path(source_db_path)
    target_db = Path(target_db_path)
    target_db.parent.mkdir(parents=True, exist_ok=True)
    reference_crossings = _load_reference_crossings(source_db)
    shutil.copy2(source_db, target_db)

    conn = sqlite3.connect(target_db, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        init_db(conn)
        _reset_trial_domain_tables(conn)
        rows = _load_crossing_candidates_file(Path(crossings_source_path))
        rows = _enrich_candidates_with_reference(rows, reference_crossings)
        _insert_crossing_candidates(conn, rows)
        risks = compute_risk(conn)
        conn.commit()
        counts = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM crossings) AS crossings_count,
                (SELECT COUNT(*) FROM train_schedules WHERE deleted_at IS NULL) AS schedules_count,
                (SELECT COUNT(*) FROM news_articles) AS articles_count,
                (SELECT COUNT(*) FROM incident_reports WHERE deleted_at IS NULL) AS incidents_count,
                (SELECT COUNT(*) FROM risk_snapshots) AS risk_count
            """
        ).fetchone()
        return {
            "target_db": str(target_db),
            "imported_crossings": len(rows),
            "computed_risks": risks,
            "counts": dict(counts),
        }
    finally:
        conn.close()


def _current_area_bounds(conn: sqlite3.Connection, margin_degrees: float) -> dict[str, float] | None:
    row = conn.execute(
        """
        SELECT
            MIN(longitude) AS west,
            MIN(latitude) AS south,
            MAX(longitude) AS east,
            MAX(latitude) AS north
        FROM crossings
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
        """
    ).fetchone()
    if row is None or any(row[key] is None for key in ("west", "south", "east", "north")):
        return None
    return {
        "west": float(row["west"]) - margin_degrees,
        "south": float(row["south"]) - margin_degrees,
        "east": float(row["east"]) + margin_degrees,
        "north": float(row["north"]) + margin_degrees,
    }


def _guess_city_hint(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        """
        SELECT city, COUNT(*) AS total
        FROM crossings
        WHERE city IS NOT NULL AND TRIM(city) <> ''
        GROUP BY city
        ORDER BY total DESC, city ASC
        LIMIT 1
        """
    ).fetchone()
    return str(row["city"]) if row and row["city"] else "Đồng Nai"


def _derive_incident_candidates(conn: sqlite3.Connection, config: dict, days_back: int) -> list[dict]:
    threshold = datetime.utcnow() - timedelta(days=days_back)
    rows = conn.execute(
        """
        SELECT id, title, url, published_at, summary, location_hint, severity_score
        FROM news_articles
        WHERE COALESCE(published_at, scraped_at) >= ?
        ORDER BY COALESCE(published_at, scraped_at) DESC, id DESC
        """,
        (threshold.isoformat(),),
    ).fetchall()
    crossings = [dict(row) for row in conn.execute("SELECT id, code, name, ward, district, city FROM crossings").fetchall()]
    keywords = [str(item).lower() for item in config.get("matching", {}).get("crossing_keywords", [])]
    severe_keywords = [str(item).lower() for item in config.get("matching", {}).get("severe_keywords", [])]
    area_tokens = [
        str(config.get("area", {}).get("city") or "").strip().lower(),
        str(config.get("area", {}).get("province") or "").strip().lower(),
    ]
    area_tokens = [token for token in area_tokens if token]

    candidates: list[dict] = []
    for row in rows:
        article = dict(row)
        merged = " ".join(str(article.get(key) or "") for key in ("title", "summary", "location_hint")).lower()
        if not any(keyword in merged for keyword in keywords):
            continue
        if area_tokens and not any(token in merged for token in area_tokens):
            continue
        match = _best_crossing_match(crossings, merged)
        severity_level = _incident_severity(article, severe_keywords)
        candidates.append(
            {
                "crossing_id": match["id"] if match else None,
                "crossing_code": match["code"] if match else None,
                "crossing_name": match["name"] if match else None,
                "title": article["title"],
                "incident_date": _normalize_date(article.get("published_at")),
                "severity_level": severity_level,
                "casualties": 0,
                "injured_count": 0,
                "description": article.get("summary"),
                "source_url": article["url"],
                "confidence_score": match["score"] if match else _fallback_incident_confidence(article, area_tokens),
                "evidence": {
                    "location_hint": article.get("location_hint"),
                    "severity_score": article.get("severity_score", 0),
                    "matched_crossing": bool(match),
                },
            }
        )
    return candidates


def _extract_crossing_candidates(
    osm_features: dict,
    *,
    city_hint: str,
    source_label: str,
    dedup_distance_meters: float,
) -> list[dict]:
    roads = osm_features.get("roads", [])
    railways = [
        feature
        for feature in osm_features.get("railways", [])
        if feature.get("kind") in {"rail", "light_rail", "tram", "subway", "construction", None}
        and "đường sắt đô thị" not in str(feature.get("name") or "").lower()
    ]

    raw_hits: list[dict] = []
    for railway in railways:
        rail_points = railway.get("centerline") or []
        if len(rail_points) < 2:
            continue
        for road in roads:
            road_points = road.get("centerline") or []
            if len(road_points) < 2:
                continue
            if not _polyline_bounds_overlap(rail_points, road_points):
                continue
            for segment_hit in _polyline_intersections(road_points, rail_points):
                raw_hits.append(
                    {
                        "longitude": round(segment_hit["longitude"], 7),
                        "latitude": round(segment_hit["latitude"], 7),
                        "road": road,
                        "railway": railway,
                    }
                )

    deduped = _deduplicate_hits(raw_hits, dedup_distance_meters)
    candidates: list[dict] = []
    for index, hit in enumerate(deduped, start=1):
        road = hit["road"]
        railway = hit["railway"]
        road_name = road.get("name") or road.get("kind") or "Đường chưa rõ tên"
        if not _is_useful_crossing_candidate(road, road_name):
            continue
        rail_name = railway.get("name") or "Tuyến đường sắt"
        crossing_type = _classify_crossing_type(road.get("kind"))
        code = f"REAL-BH-{index:03d}"
        candidates.append(
            {
                "code": code,
                "name": f"Giao cắt {road_name}",
                "address": road_name,
                "ward": None,
                "district": None,
                "city": city_hint,
                "latitude": hit["latitude"],
                "longitude": hit["longitude"],
                "crossing_type": crossing_type,
                "barrier_type": None,
                "manager_name": None,
                "manager_phone": None,
                "verification_status": "surveyed",
                "coordinate_source": "OSM/GPKG thực tế",
                "source_reference": _source_reference(source_label, road, railway),
                "alias_text": _alias_text_from_candidate(road_name, rail_name),
                "reference_crossing_code": None,
                "verification_notes": (
                    "Ứng viên giao cắt được trích xuất tự động từ giao điểm hình học giữa đường bộ "
                    "và đường sắt trong dữ liệu OSM/GPKG. Cần kiểm tra thực địa trước khi thay thế dữ liệu mẫu."
                ),
                "surveyed_at": None,
                "verified_at": None,
                "notes": f"Tự động suy ra từ {road_name} giao với {rail_name}.",
            }
        )
    return candidates


def _reset_trial_domain_tables(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM auth_sessions")
    conn.execute("DELETE FROM audit_logs")
    conn.execute("DELETE FROM risk_snapshots")
    conn.execute("DELETE FROM incident_reports")
    conn.execute("DELETE FROM crossing_images")
    conn.execute("DELETE FROM crossings")
    conn.commit()


def _load_crossing_candidates_file(path: Path) -> list[dict]:
    if path.suffix.lower() == ".json":
        return json.loads(path.read_text(encoding="utf-8"))

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(DictReader(handle))


def _insert_crossing_candidates(conn: sqlite3.Connection, rows: list[dict]) -> None:
    for row in rows:
        conn.execute(
            """
            INSERT INTO crossings (
                code, name, address, ward, district, city, latitude, longitude,
                crossing_type, barrier_type, manager_name, manager_phone,
                verification_status, coordinate_source, source_reference,
                alias_text, reference_crossing_code, verification_notes, surveyed_at, verified_at, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row.get("code"),
                row.get("name"),
                row.get("address"),
                row.get("ward"),
                row.get("district"),
                row.get("city"),
                _to_float(row.get("latitude")),
                _to_float(row.get("longitude")),
                row.get("crossing_type"),
                row.get("barrier_type"),
                row.get("manager_name"),
                row.get("manager_phone"),
                row.get("verification_status") or "surveyed",
                row.get("coordinate_source"),
                row.get("source_reference"),
                row.get("alias_text"),
                row.get("reference_crossing_code"),
                row.get("verification_notes"),
                row.get("surveyed_at"),
                row.get("verified_at"),
                row.get("notes"),
            ),
        )


def _to_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _best_crossing_match(crossings: list[dict], merged_text: str) -> dict | None:
    best: dict | None = None
    second_score = -1
    for crossing in crossings:
        score = 0
        name = str(crossing.get("name") or "").strip().lower()
        address = str(crossing.get("address") or "").strip().lower()
        alias_text = str(crossing.get("alias_text") or "").strip().lower()
        ward = str(crossing.get("ward") or "").strip().lower()
        district = str(crossing.get("district") or "").strip().lower()
        city = str(crossing.get("city") or "").strip().lower()

        if name and name in merged_text:
            score += 5
        if address and address in merged_text:
            score += 4
        if alias_text:
            for alias in [part.strip() for part in alias_text.split("|") if part.strip()]:
                if alias in merged_text:
                    score += 3
        if ward and ward in merged_text:
            score += 2
        if district and district in merged_text:
            score += 2
        if city and city in merged_text:
            score += 1

        if score > (best["score"] if best else -1):
            second_score = best["score"] if best else -1
            best = {**crossing, "score": score}
        elif score > second_score:
            second_score = score

    if not best or best["score"] < 5:
        return None
    if second_score >= best["score"]:
        return None
    return best


def _incident_severity(article: dict, severe_keywords: list[str]) -> str:
    merged = " ".join(str(article.get(key) or "") for key in ("title", "summary")).lower()
    severe_hits = sum(1 for keyword in severe_keywords if keyword in merged)
    if severe_hits >= 2 or int(article.get("severity_score") or 0) >= 3:
        return "very_high"
    if severe_hits >= 1 or int(article.get("severity_score") or 0) >= 2:
        return "high"
    return "medium"


def _fallback_incident_confidence(article: dict, area_tokens: list[str]) -> int:
    merged = " ".join(str(article.get(key) or "") for key in ("title", "summary", "location_hint")).lower()
    score = 0
    for token in area_tokens:
        if token in merged:
            score += 2
    if "đường sắt" in merged or "tau hoa" in merged or "tàu hỏa" in merged:
        score += 2
    if "tai nạn" in merged or "va chạm" in merged:
        score += 2
    return score


def _normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return value[:10]


def _store_incident_candidates(conn: sqlite3.Connection, candidates: list[dict]) -> int:
    inserted = 0
    for item in candidates:
        existing = conn.execute(
            "SELECT id FROM incident_reports WHERE source_url = ? LIMIT 1",
            (item["source_url"],),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE incident_reports
                SET
                    crossing_id = ?,
                    title = ?,
                    incident_date = ?,
                    severity_level = ?,
                    casualties = ?,
                    injured_count = ?,
                    description = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    item["crossing_id"],
                    item["title"],
                    item["incident_date"],
                    item["severity_level"],
                    item["casualties"],
                    item["injured_count"],
                    item["description"],
                    existing["id"],
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO incident_reports (
                    crossing_id, title, incident_date, severity_level, casualties,
                    injured_count, description, source_url
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["crossing_id"],
                    item["title"],
                    item["incident_date"],
                    item["severity_level"],
                    item["casualties"],
                    item["injured_count"],
                    item["description"],
                    item["source_url"],
                ),
            )
            inserted += 1
    conn.commit()
    return inserted


def _write_crossing_candidates(output_path: Path, rows: list[dict]) -> None:
    suffix = output_path.suffix.lower()
    if suffix == ".json":
        output_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return

    fieldnames = [
        "code",
        "name",
        "address",
        "ward",
        "district",
        "city",
        "latitude",
        "longitude",
        "crossing_type",
        "barrier_type",
        "manager_name",
        "manager_phone",
        "verification_status",
        "coordinate_source",
        "source_reference",
        "verification_notes",
        "surveyed_at",
        "verified_at",
        "notes",
    ]
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _polyline_bounds_overlap(a_points: list[dict], b_points: list[dict]) -> bool:
    a = _bounds_for_points(a_points)
    b = _bounds_for_points(b_points)
    return not (a["east"] < b["west"] or a["west"] > b["east"] or a["north"] < b["south"] or a["south"] > b["north"])


def _bounds_for_points(points: list[dict]) -> dict[str, float]:
    return {
        "west": min(point["longitude"] for point in points),
        "south": min(point["latitude"] for point in points),
        "east": max(point["longitude"] for point in points),
        "north": max(point["latitude"] for point in points),
    }


def _polyline_intersections(a_points: list[dict], b_points: list[dict]) -> list[dict[str, float]]:
    intersections: list[dict[str, float]] = []
    for a_start, a_end in zip(a_points, a_points[1:]):
        for b_start, b_end in zip(b_points, b_points[1:]):
            point = _segment_intersection(a_start, a_end, b_start, b_end)
            if point is not None:
                intersections.append(point)
    return intersections


def _segment_intersection(
    a_start: dict,
    a_end: dict,
    b_start: dict,
    b_end: dict,
) -> dict[str, float] | None:
    x1, y1 = a_start["longitude"], a_start["latitude"]
    x2, y2 = a_end["longitude"], a_end["latitude"]
    x3, y3 = b_start["longitude"], b_start["latitude"]
    x4, y4 = b_end["longitude"], b_end["latitude"]

    denominator = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denominator) < 1e-12:
        return None

    det_a = x1 * y2 - y1 * x2
    det_b = x3 * y4 - y3 * x4
    px = (det_a * (x3 - x4) - (x1 - x2) * det_b) / denominator
    py = (det_a * (y3 - y4) - (y1 - y2) * det_b) / denominator

    if not (_point_on_segment(px, py, x1, y1, x2, y2) and _point_on_segment(px, py, x3, y3, x4, y4)):
        return None

    return {"longitude": px, "latitude": py}


def _point_on_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> bool:
    epsilon = 1e-9
    return (
        min(x1, x2) - epsilon <= px <= max(x1, x2) + epsilon
        and min(y1, y2) - epsilon <= py <= max(y1, y2) + epsilon
    )


def _deduplicate_hits(raw_hits: list[dict], threshold_meters: float) -> list[dict]:
    deduped: list[dict] = []
    for hit in raw_hits:
        if any(_distance_meters(hit, kept) <= threshold_meters for kept in deduped):
            continue
        deduped.append(hit)
    deduped.sort(key=lambda item: (item["latitude"], item["longitude"]))
    return deduped


def _distance_meters(a: dict, b: dict) -> float:
    lon1 = math.radians(a["longitude"])
    lat1 = math.radians(a["latitude"])
    lon2 = math.radians(b["longitude"])
    lat2 = math.radians(b["latitude"])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    term = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371000 * (2 * math.atan2(math.sqrt(term), math.sqrt(max(0.0, 1 - term))))


def _classify_crossing_type(road_kind: str | None) -> str:
    if road_kind in {"service", "residential", "path", "footway", "track", "unclassified"}:
        return "loi_di_tu_mo"
    return "duong_ngang_hop_phap"


def _source_reference(source_label: str, road: dict, railway: dict) -> str:
    road_ref = road.get("osmWayId") or road.get("id")
    rail_ref = railway.get("osmWayId") or railway.get("id")
    return f"{source_label};road={road_ref};rail={rail_ref}"


def _is_useful_crossing_candidate(road: dict, road_name: str) -> bool:
    kind = str(road.get("kind") or "").strip().lower()
    normalized_name = road_name.strip().lower()
    # Keep broad coverage for public trial data. Generic OSM ways are still
    # accepted so news/articles can be mapped when possible; only obviously
    # non-crossing records are filtered out here.
    if kind in {"steps", "corridor", "platform"}:
        return False
    if normalized_name in {"steps", "corridor", "platform"}:
        return False
    return not any(keyword in normalized_name for keyword in EXCLUDED_NAME_KEYWORDS)


def _alias_text_from_candidate(road_name: str, rail_name: str) -> str:
    aliases = {road_name.strip()}
    if rail_name:
        aliases.add(rail_name.strip())
    return " | ".join(sorted(alias for alias in aliases if alias))


def _load_reference_crossings(source_db: Path) -> list[dict]:
    conn = sqlite3.connect(source_db)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT code, name, address, ward, district, city, latitude, longitude
            FROM crossings
            WHERE latitude IS NOT NULL AND longitude IS NOT NULL
            ORDER BY code
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def _enrich_candidates_with_reference(rows: list[dict], reference_crossings: list[dict]) -> list[dict]:
    enriched: list[dict] = []
    for row in rows:
        best_reference = None
        best_distance = None
        for reference in reference_crossings:
            distance = _distance_meters(row, reference)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_reference = reference

        if best_reference and best_distance is not None and best_distance <= REFERENCE_MATCH_METERS:
            row = {**row}
            row["ward"] = row.get("ward") or best_reference.get("ward")
            row["district"] = row.get("district") or best_reference.get("district")
            row["city"] = row.get("city") or best_reference.get("city")
            row["reference_crossing_code"] = best_reference.get("code")
            row["alias_text"] = _merge_alias_text(
                row.get("alias_text"),
                best_reference.get("name"),
                best_reference.get("address"),
            )
            if _is_generic_name(row.get("name")):
                row["name"] = best_reference.get("name") or row["name"]
            if _is_generic_name(row.get("address")):
                row["address"] = best_reference.get("address") or row["address"]
        enriched.append(row)
    return enriched


def _merge_alias_text(current: str | None, *extra_tokens: object) -> str:
    aliases = {part.strip() for part in str(current or "").split("|") if part.strip()}
    for token in extra_tokens:
        value = str(token or "").strip()
        if value:
            aliases.add(value)
    return " | ".join(sorted(aliases))


def _is_generic_name(value: object) -> bool:
    text = str(value or "").strip().lower()
    return not text or text in GENERIC_ROAD_KINDS or any(keyword in text for keyword in EXCLUDED_NAME_KEYWORDS)
