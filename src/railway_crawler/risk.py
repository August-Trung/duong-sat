from __future__ import annotations

import json
import sqlite3

GENERIC_LOCATION_TOKENS = {
    "bien hoa",
    "biên hòa",
    "dong nai",
    "đồng nai",
    "residential",
    "service",
    "footway",
    "path",
    "track",
    "unclassified",
}


def compute_risk(conn: sqlite3.Connection) -> int:
    crossings = conn.execute("SELECT * FROM crossings ORDER BY code").fetchall()
    if not crossings:
        return 0

    inserted = 0
    for crossing in crossings:
        evidence = _build_evidence(conn, crossing)
        score = _score_crossing(crossing, evidence)
        level = _risk_level(score)

        conn.execute(
            """
            INSERT INTO risk_snapshots (crossing_id, score, level, evidence_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                crossing["id"],
                score,
                level,
                json.dumps(evidence, ensure_ascii=False),
            ),
        )
        inserted += 1

    conn.commit()
    return inserted


def export_top_risks(conn: sqlite3.Connection, limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            c.code,
            c.name,
            c.district,
            c.city,
            r.score,
            r.level,
            r.calculated_at
        FROM risk_snapshots r
        JOIN crossings c ON c.id = r.crossing_id
        JOIN (
            SELECT crossing_id, MAX(id) AS latest_id
            FROM risk_snapshots
            GROUP BY crossing_id
        ) latest ON latest.latest_id = r.id
        ORDER BY r.score DESC, c.code
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def _build_evidence(conn: sqlite3.Connection, crossing: sqlite3.Row) -> dict:
    alias_tokens = [part.strip() for part in str(crossing["alias_text"] or "").split("|") if part.strip()] if "alias_text" in crossing.keys() else []
    location_tokens = _useful_location_tokens(
        [crossing["name"], crossing["address"], *alias_tokens, crossing["ward"], crossing["district"]]
    )
    where_clauses = []
    params = []
    for token in location_tokens:
        if not token:
            continue
        where_clauses.append("(lower(title) LIKE ? OR lower(summary) LIKE ? OR lower(location_hint) LIKE ?)")
        like = f"%{token.lower()}%"
        params.extend([like, like, like])

    article_count = 0
    severe_sum = 0
    if where_clauses:
        query = (
            "SELECT COUNT(*) AS article_count, COALESCE(SUM(severity_score), 0) AS severe_sum "
            "FROM news_articles WHERE " + " OR ".join(where_clauses)
        )
        row = conn.execute(query, params).fetchone()
        article_count = row["article_count"]
        severe_sum = row["severe_sum"]

    station_keyword = _guess_station_keyword(crossing["name"])
    schedule_count = 0
    if station_keyword:
        row = conn.execute(
            """
            SELECT COUNT(*) AS schedule_count
            FROM train_schedules
            WHERE station_name = ?
            """,
            (station_keyword,),
        ).fetchone()
        schedule_count = row["schedule_count"]

    incident_row = conn.execute(
        """
        SELECT
            COUNT(*) AS incident_count,
            COALESCE(SUM(casualties), 0) AS total_casualties,
            COALESCE(SUM(injured_count), 0) AS total_injured
        FROM incident_reports
        WHERE crossing_id = ?
        """,
        (crossing["id"],),
    ).fetchone()

    return {
        "article_count": article_count,
        "severe_article_hits": severe_sum,
        "schedule_count": schedule_count,
        "incident_count": incident_row["incident_count"],
        "incident_casualties": incident_row["total_casualties"],
        "incident_injured": incident_row["total_injured"],
        "barrier_type": crossing["barrier_type"],
        "crossing_type": crossing["crossing_type"],
        "station_keyword": station_keyword,
    }


def _useful_location_tokens(tokens: list[object]) -> list[str]:
    seen: set[str] = set()
    useful: list[str] = []
    for token in tokens:
        value = str(token or "").strip()
        normalized = value.lower()
        if not value or len(normalized) < 4:
            continue
        if normalized in GENERIC_LOCATION_TOKENS:
            continue
        if normalized.startswith("giao cắt "):
            normalized = normalized.replace("giao cắt ", "", 1).strip()
            value = value[9:].strip()
        if not value or normalized in GENERIC_LOCATION_TOKENS:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        useful.append(value)
    return useful


def _guess_station_keyword(crossing_name: str) -> str | None:
    text = crossing_name.lower()
    if "biên hòa" in text or "bien hoa" in text:
        return "Biên Hòa"
    if "long bình" in text or "long binh" in text or "hố nai" in text or "ho nai" in text:
        return "Biên Hòa"
    if "dĩ an" in text or "di an" in text:
        return "Dĩ An"
    if "long khánh" in text or "long khanh" in text:
        return "Long Khánh"
    return None


def _score_crossing(crossing: sqlite3.Row, evidence: dict) -> int:
    score = 0
    score += evidence["article_count"] * 8
    score += evidence["severe_article_hits"] * 15
    score += min(evidence["schedule_count"], 20)
    score += evidence["incident_count"] * 20
    score += evidence["incident_casualties"] * 40
    score += evidence["incident_injured"] * 15

    if crossing["barrier_type"] == "khong_co":
        score += 25
    elif crossing["barrier_type"] == "tu_dong":
        score += 10

    if crossing["crossing_type"] == "loi_di_tu_mo":
        score += 30

    return score


def _risk_level(score: int) -> str:
    if score >= 100:
        return "very_high"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"
