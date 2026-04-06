from __future__ import annotations

from csv import DictWriter
from datetime import datetime, timedelta, timezone
from io import StringIO
import json
import os
import secrets
import shutil
import sqlite3
from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from railway_crawler.db import ROLE_VALUES, hash_password, init_db, verify_password
from railway_crawler.news import resolve_article_assets
from railway_crawler.risk import compute_risk
from railway_crawler.scene3d import DEFAULT_OUTPUT_DIR, export_scene_bundle, read_scene_manifest, read_scene_tile


APP_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = str(APP_ROOT / "data" / "railway.db")
UPLOADS_ROOT = APP_ROOT / "data" / "uploads"
SESSION_HOURS = 12
GENERIC_ARTICLE_TOKENS = {
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

ROLE_PERMISSIONS = {
    "viewer": {
        "admin:view",
        "reports:view",
        "quality:view",
        "crossings:profile",
        "audit:view",
    },
    "reviewer": {
        "admin:view",
        "reports:view",
        "quality:view",
        "crossings:profile",
        "audit:view",
        "crossings:verify",
        "crossings:bulk",
        "images:upload",
        "images:delete",
    },
    "editor": {
        "admin:view",
        "reports:view",
        "quality:view",
        "crossings:profile",
        "audit:view",
        "crossings:create",
        "crossings:update",
        "crossings:bulk",
        "schedules:write",
        "incidents:write",
        "articles:write",
        "images:upload",
        "images:delete",
    },
    "admin": {
        "admin:view",
        "reports:view",
        "quality:view",
        "crossings:profile",
        "audit:view",
        "crossings:create",
        "crossings:update",
        "crossings:bulk",
        "crossings:delete",
        "crossings:import",
        "schedules:write",
        "schedules:delete",
        "incidents:write",
        "incidents:delete",
        "articles:write",
        "articles:delete",
        "images:upload",
        "images:delete",
        "users:manage",
    },
}


class LoginRequest(BaseModel):
    username: str
    password: str


class CrossingPayload(BaseModel):
    code: str
    name: str
    address: str | None = None
    ward: str | None = None
    district: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    crossing_type: str | None = None
    barrier_type: str | None = None
    manager_name: str | None = None
    manager_phone: str | None = None
    verification_status: str = "draft"
    coordinate_source: str | None = None
    source_reference: str | None = None
    verification_notes: str | None = None
    surveyed_at: str | None = None
    verified_at: str | None = None
    notes: str | None = None


class CrossingImportItem(CrossingPayload):
    pass


class SchedulePayload(BaseModel):
    source_name: str = "Admin"
    source_url: str = "manual"
    route_name: str
    direction: str
    station_name: str
    km: int | None = None
    train_no: str
    pass_time: str
    day_offset: int = 0
    raw_time_text: str | None = None


class IncidentPayload(BaseModel):
    crossing_id: int | None = None
    title: str
    incident_date: str | None = None
    severity_level: str | None = None
    casualties: int = 0
    injured_count: int = 0
    description: str | None = None
    source_url: str | None = None


class ArticlePayload(BaseModel):
    crossing_id: int | None = None
    source_name: str = "Admin"
    title: str
    url: str
    external_url: str | None = None
    image_url: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    summary: str | None = None
    matched_query: str | None = None
    location_hint: str | None = None
    severity_score: int = 0


class BulkActionPayload(BaseModel):
    ids: list[int] = Field(default_factory=list)
    action: str
    value: str | None = None


class UserPayload(BaseModel):
    username: str
    full_name: str
    role: str
    password: str | None = None
    is_active: bool = True


class CrossingImageOrderItem(BaseModel):
    id: int
    sort_order: int


class CrossingImageGalleryPayload(BaseModel):
    items: list[CrossingImageOrderItem] = Field(default_factory=list)
    cover_image_id: int | None = None


def create_app(database_path: str | None = None) -> FastAPI:
    app = FastAPI(
        title="Railway Risk API",
        version="0.3.0",
        description="API cho hệ thống quản lý điểm giao cắt đường sắt Biên Hòa.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    db_path = database_path or os.getenv("RAILWAY_DB_PATH", DEFAULT_DB_PATH)
    scene3d_osm_path = os.getenv("RAILWAY_SCENE3D_OSM_PATH")
    scene3d_gpkg_path = os.getenv("RAILWAY_SCENE3D_GPKG_PATH")
    scene3d_dem_path = os.getenv("RAILWAY_SCENE3D_DEM_PATH")
    UPLOADS_ROOT.mkdir(parents=True, exist_ok=True)
    _initialize_database(db_path)

    app.mount("/uploads", StaticFiles(directory=str(UPLOADS_ROOT)), name="uploads")

    def get_conn() -> sqlite3.Connection:
        return _connect(db_path)

    def current_user(
        authorization: str | None = Header(default=None),
        conn: sqlite3.Connection = Depends(get_conn),
    ):
        token = _extract_bearer_token(authorization)
        if not token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing token")

        row = conn.execute(
            """
            SELECT u.id, u.username, u.full_name, u.role, u.is_active
            FROM auth_sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token = ? AND s.expires_at > datetime('now')
            """,
            (token,),
        ).fetchone()
        if row is None or row["is_active"] != 1:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
        user = dict(row)
        user["permissions"] = sorted(ROLE_PERMISSIONS.get(user["role"], set()))
        return user

    def staff_user(user: dict = Depends(current_user)):
        if user["role"] not in ROLE_VALUES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff permission required")
        return user

    def require_permission(permission: str):
        def dependency(user: dict = Depends(staff_user)):
            if permission not in ROLE_PERMISSIONS.get(user["role"], set()):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
            return user

        return dependency

    @app.get("/api/health")
    def health():
        return {"status": "ok", "database": db_path}

    @app.get("/api/summary")
    def public_summary():
        conn = get_conn()
        crossings = _list_crossings(conn)
        incidents = _list_public_incidents(conn, limit=500)
        return {
            "total_crossings": len(crossings),
            "very_high_count": sum(1 for item in crossings if item.get("risk_level") == "very_high"),
            "high_count": sum(1 for item in crossings if item.get("risk_level") == "high"),
            "article_count": sum(int(item.get("article_count") or 0) for item in crossings),
            "incident_count": len(incidents),
        }

    @app.get("/api/layers")
    def public_layers():
        return {
            "riskLevels": [
                {"value": "very_high", "label": "Rất nguy hiểm"},
                {"value": "high", "label": "Nguy hiểm cao"},
                {"value": "medium", "label": "Trung bình"},
                {"value": "low", "label": "Thấp"},
            ],
            "barrierTypes": [
                {"value": "co_gac", "label": "Có gác"},
                {"value": "tu_dong", "label": "Tự động"},
                {"value": "can_gat", "label": "Cần gạt"},
                {"value": "khong_co", "label": "Không có rào chắn"},
            ],
        }

    @app.get("/api/crossings")
    def public_crossings(
        q: str | None = None,
        risk_level: str | None = None,
        barrier_type: str | None = None,
    ):
        conn = get_conn()
        return _list_crossings(conn, q=q, risk_level=risk_level, barrier_type=barrier_type)

    @app.get("/api/crossings/{crossing_id}")
    def public_crossing_detail(crossing_id: int):
        conn = get_conn()
        crossing = _crossing_detail(conn, crossing_id)
        if crossing is None or crossing.get("deleted_at"):
            raise HTTPException(status_code=404, detail="Crossing not found")
        return crossing

    @app.get("/api/schedules")
    def public_schedules(limit: int = Query(100, ge=1, le=500)):
        conn = get_conn()
        return _list_public_schedules(conn, limit=limit)

    @app.get("/api/incidents")
    def public_incidents(limit: int = Query(100, ge=1, le=500)):
        conn = get_conn()
        return _list_public_incidents(conn, limit=limit)

    @app.get("/api/scene3d/manifest")
    def scene3d_manifest():
        manifest_path = DEFAULT_OUTPUT_DIR / "manifest.json"
        if not manifest_path.exists():
            if not any([scene3d_osm_path, scene3d_gpkg_path, scene3d_dem_path]):
                raise HTTPException(status_code=404, detail="Scene 3D manifest chưa được tạo.")

            conn = get_conn()
            export_scene_bundle(
                conn=conn,
                output_dir=DEFAULT_OUTPUT_DIR,
                osm_path=scene3d_osm_path,
                gpkg_path=scene3d_gpkg_path,
                dem_path=scene3d_dem_path,
            )

        return read_scene_manifest(DEFAULT_OUTPUT_DIR)

    @app.get("/api/scene3d/tiles/{tile_id}")
    def scene3d_tile(tile_id: str):
        tile_path = DEFAULT_OUTPUT_DIR / "tiles" / f"{tile_id}.json"
        if not tile_path.exists():
            raise HTTPException(status_code=404, detail=f"Không tìm thấy tile scene3d '{tile_id}'.")
        return read_scene_tile(tile_id, DEFAULT_OUTPUT_DIR)

    @app.post("/api/auth/login")
    def login(payload: LoginRequest):
        conn = get_conn()
        user = conn.execute(
            """
            SELECT id, username, password_hash, full_name, role, is_active
            FROM users
            WHERE username = ?
            """,
            (payload.username,),
        ).fetchone()
        if user is None or user["is_active"] != 1 or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")

        token = secrets.token_urlsafe(32)
        expires_at = (datetime.now(timezone.utc) + timedelta(hours=SESSION_HOURS)).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "INSERT INTO auth_sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user["id"], token, expires_at),
        )
        conn.commit()
        profile = _serialize_user(user)
        profile["permissions"] = sorted(ROLE_PERMISSIONS.get(user["role"], set()))
        return {"token": token, "user": profile, "expires_at": expires_at}

    @app.post("/api/auth/logout", status_code=204)
    def logout(authorization: str | None = Header(default=None)):
        token = _extract_bearer_token(authorization)
        if token:
            conn = get_conn()
            conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
            conn.commit()
        return Response(status_code=204)

    @app.get("/api/auth/me")
    def me(user: dict = Depends(current_user)):
        return user

    @app.get("/api/admin/overview")
    def admin_overview(user: dict = Depends(require_permission("admin:view"))):
        conn = get_conn()
        overview = {
            "crossings": _list_crossings(conn),
            "schedules": _list_admin_schedules(conn),
            "incidents": _list_admin_incidents(conn),
            "articles": _list_admin_articles(conn),
            "users": _list_users(conn) if "users:manage" in user["permissions"] else [],
            "qualityAlerts": _data_quality_alerts(conn),
            "auditLogs": _list_audit_logs(conn, limit=30),
            "permissionMatrix": _permission_matrix(),
            "user": user,
        }
        return overview

    @app.get("/api/admin/quality-alerts")
    def admin_quality_alerts(user: dict = Depends(require_permission("quality:view"))):
        conn = get_conn()
        return _data_quality_alerts(conn)

    @app.get("/api/admin/audit-logs")
    def admin_audit_logs(limit: int = Query(50, ge=1, le=200), user: dict = Depends(require_permission("audit:view"))):
        conn = get_conn()
        return _list_audit_logs(conn, limit=limit)

    @app.get("/api/admin/crossings")
    def list_crossings_admin(
        q: str | None = None,
        risk_level: str | None = None,
        barrier_type: str | None = None,
        include_deleted: bool = False,
        user: dict = Depends(require_permission("admin:view")),
    ):
        conn = get_conn()
        return _list_crossings(conn, q=q, risk_level=risk_level, barrier_type=barrier_type, include_deleted=include_deleted)

    @app.post("/api/admin/crossings")
    def create_crossing_admin(payload: CrossingPayload, user: dict = Depends(require_permission("crossings:create"))):
        conn = get_conn()
        cursor = conn.execute(
            """
            INSERT INTO crossings (
                code, name, address, ward, district, city, latitude, longitude,
                crossing_type, barrier_type, manager_name, manager_phone,
                verification_status, coordinate_source, source_reference,
                verification_notes, surveyed_at, verified_at, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            _crossing_values(payload),
        )
        after = _crossing_detail(conn, cursor.lastrowid)
        _log_audit(conn, user, "crossing", cursor.lastrowid, "create", f"Tạo điểm giao cắt {payload.code}", None, after)
        conn.commit()
        return after

    @app.put("/api/admin/crossings/{crossing_id}")
    def update_crossing_admin(crossing_id: int, payload: CrossingPayload, user: dict = Depends(require_permission("crossings:update"))):
        conn = get_conn()
        _require_existing(conn, "crossings", crossing_id)
        before = _crossing_detail(conn, crossing_id)
        conn.execute(
            """
            UPDATE crossings
            SET
                code = ?, name = ?, address = ?, ward = ?, district = ?, city = ?, latitude = ?, longitude = ?,
                crossing_type = ?, barrier_type = ?, manager_name = ?, manager_phone = ?,
                verification_status = ?, coordinate_source = ?, source_reference = ?,
                verification_notes = ?, surveyed_at = ?, verified_at = ?, notes = ?,
                deleted_at = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            [*_crossing_values(payload), crossing_id],
        )
        after = _crossing_detail(conn, crossing_id)
        _log_audit(conn, user, "crossing", crossing_id, "update", f"Cập nhật điểm giao cắt {payload.code}", before, after)
        conn.commit()
        return after

    @app.delete("/api/admin/crossings/{crossing_id}")
    def delete_crossing_admin(crossing_id: int, user: dict = Depends(require_permission("crossings:delete"))):
        conn = get_conn()
        before = _crossing_detail(conn, crossing_id)
        if before is None:
            raise HTTPException(status_code=404, detail="Crossing not found")
        conn.execute("UPDATE crossings SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (crossing_id,))
        after = _crossing_detail(conn, crossing_id)
        _log_audit(conn, user, "crossing", crossing_id, "soft_delete", f"Ẩn điểm giao cắt {before['code']}", before, after)
        conn.commit()
        return {"status": "ok"}

    @app.post("/api/admin/crossings/import")
    def import_crossings_admin(payload: list[CrossingImportItem], user: dict = Depends(require_permission("crossings:import"))):
        conn = get_conn()
        imported = 0
        for item in payload:
            existing = conn.execute("SELECT id FROM crossings WHERE code = ?", (item.code,)).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE crossings
                    SET
                        name = ?, address = ?, ward = ?, district = ?, city = ?, latitude = ?, longitude = ?,
                        crossing_type = ?, barrier_type = ?, manager_name = ?, manager_phone = ?,
                        verification_status = ?, coordinate_source = ?, source_reference = ?,
                        verification_notes = ?, surveyed_at = ?, verified_at = ?, notes = ?,
                        deleted_at = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE code = ?
                    """,
                    [*_crossing_values(item)[1:], item.code],
                )
            else:
                conn.execute(
                    """
                    INSERT INTO crossings (
                        code, name, address, ward, district, city, latitude, longitude,
                        crossing_type, barrier_type, manager_name, manager_phone,
                        verification_status, coordinate_source, source_reference,
                        verification_notes, surveyed_at, verified_at, notes
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _crossing_values(item),
                )
            imported += 1
        _log_audit(conn, user, "crossing", None, "import", f"Import {imported} điểm giao cắt", None, {"imported": imported})
        conn.commit()
        return {"imported": imported}

    @app.post("/api/admin/crossings/bulk")
    def bulk_crossings_admin(payload: BulkActionPayload, user: dict = Depends(require_permission("crossings:bulk"))):
        conn = get_conn()
        if not payload.ids:
            raise HTTPException(status_code=400, detail="No rows selected")

        rows = conn.execute(
            f"SELECT * FROM crossings WHERE id IN ({','.join('?' for _ in payload.ids)})",
            payload.ids,
        ).fetchall()
        if not rows:
            raise HTTPException(status_code=404, detail="No crossings found")

        if payload.action == "set_verification_status":
            conn.execute(
                f"UPDATE crossings SET verification_status = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({','.join('?' for _ in payload.ids)})",
                [payload.value or "draft", *payload.ids],
            )
        elif payload.action == "assign_manager":
            conn.execute(
                f"UPDATE crossings SET manager_name = ?, updated_at = CURRENT_TIMESTAMP WHERE id IN ({','.join('?' for _ in payload.ids)})",
                [payload.value or "", *payload.ids],
            )
        elif payload.action == "soft_delete":
            if "crossings:delete" not in user["permissions"]:
                raise HTTPException(status_code=403, detail="Permission denied")
            conn.execute(
                f"UPDATE crossings SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id IN ({','.join('?' for _ in payload.ids)})",
                payload.ids,
            )
        elif payload.action == "restore":
            if "crossings:delete" not in user["permissions"]:
                raise HTTPException(status_code=403, detail="Permission denied")
            conn.execute(
                f"UPDATE crossings SET deleted_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id IN ({','.join('?' for _ in payload.ids)})",
                payload.ids,
            )
        elif payload.action == "export_csv":
            selected = [dict(row) for row in rows]
            return _csv_response("crossings-selected.csv", selected)
        else:
            raise HTTPException(status_code=400, detail="Unsupported bulk action")

        _log_audit(
            conn,
            user,
            "crossing",
            None,
            f"bulk:{payload.action}",
            f"Bulk action {payload.action} cho {len(payload.ids)} điểm giao cắt",
            {"ids": payload.ids},
            {"value": payload.value},
        )
        conn.commit()
        return {"status": "ok", "affected": len(payload.ids)}

    @app.get("/api/admin/crossings/{crossing_id}/profile")
    def crossing_profile(crossing_id: int, user: dict = Depends(require_permission("crossings:profile"))):
        conn = get_conn()
        crossing = _crossing_detail(conn, crossing_id)
        if crossing is None:
            raise HTTPException(status_code=404, detail="Crossing not found")
        crossing["quality_alerts"] = _quality_alerts_for_crossing(conn, crossing)
        crossing["audit_logs"] = _list_audit_logs(conn, limit=25, entity_type="crossing", entity_id=crossing_id)
        return crossing

    @app.post("/api/admin/crossings/{crossing_id}/images")
    async def upload_crossing_images_admin(
        crossing_id: int,
        files: list[UploadFile] = File(...),
        user: dict = Depends(require_permission("images:upload")),
    ):
        conn = get_conn()
        crossing = _crossing_detail(conn, crossing_id)
        if crossing is None:
            raise HTTPException(status_code=404, detail="Crossing not found")
        saved: list[dict] = []
        next_order = _next_image_sort_order(conn, crossing_id)
        cover_exists = conn.execute(
            "SELECT 1 FROM crossing_images WHERE crossing_id = ? AND is_cover = 1 LIMIT 1",
            (crossing_id,),
        ).fetchone() is not None
        for offset, upload in enumerate(files):
            image = await _store_crossing_image(
                conn,
                crossing_id=crossing_id,
                upload=upload,
                uploaded_by=user["id"],
                sort_order=next_order + offset,
                is_cover=not cover_exists and offset == 0,
            )
            saved.append(image)
        _log_audit(conn, user, "crossing_image", crossing_id, "upload", f"Tải {len(saved)} ảnh cho điểm {crossing['code']}", None, {"images": saved})
        conn.commit()
        return saved

    @app.put("/api/admin/crossings/{crossing_id}/images")
    def update_crossing_images_admin(
        crossing_id: int,
        payload: CrossingImageGalleryPayload,
        user: dict = Depends(require_permission("images:upload")),
    ):
        conn = get_conn()
        crossing = _crossing_detail(conn, crossing_id)
        if crossing is None:
            raise HTTPException(status_code=404, detail="Crossing not found")
        before = _get_crossing_images(conn, crossing_id)
        _update_crossing_image_gallery(conn, crossing_id, payload)
        after = _get_crossing_images(conn, crossing_id)
        _log_audit(conn, user, "crossing_image", crossing_id, "arrange", f"Cập nhật thứ tự ảnh cho điểm {crossing['code']}", {"images": before}, {"images": after})
        conn.commit()
        return after

    @app.delete("/api/admin/crossings/{crossing_id}/images/{image_id}")
    def delete_crossing_image_admin(
        crossing_id: int,
        image_id: int,
        user: dict = Depends(require_permission("images:delete")),
    ):
        conn = get_conn()
        image = _get_crossing_image(conn, image_id)
        if image["crossing_id"] != crossing_id:
            raise HTTPException(status_code=400, detail="Image does not belong to crossing")
        absolute_path = UPLOADS_ROOT / image["storage_path"]
        conn.execute("DELETE FROM crossing_images WHERE id = ?", (image_id,))
        if absolute_path.exists():
            absolute_path.unlink()
        _normalize_crossing_image_gallery(conn, crossing_id)
        _log_audit(conn, user, "crossing_image", image_id, "delete", f"Xóa ảnh {image['original_name']}", image, None)
        conn.commit()
        return {"status": "ok"}

    @app.post("/api/admin/schedules")
    def create_schedule_admin(payload: SchedulePayload, user: dict = Depends(require_permission("schedules:write"))):
        conn = get_conn()
        cursor = conn.execute(
            """
            INSERT INTO train_schedules (
                source_name, source_url, route_name, direction, station_name, km,
                train_no, pass_time, day_offset, raw_time_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.source_name,
                payload.source_url,
                payload.route_name,
                payload.direction,
                payload.station_name,
                payload.km,
                payload.train_no,
                payload.pass_time,
                payload.day_offset,
                payload.raw_time_text or payload.pass_time,
            ),
        )
        after = _get_schedule(conn, cursor.lastrowid)
        _log_audit(conn, user, "schedule", cursor.lastrowid, "create", f"Tạo lịch tàu {payload.train_no}", None, after)
        conn.commit()
        return after

    @app.put("/api/admin/schedules/{schedule_id}")
    def update_schedule_admin(schedule_id: int, payload: SchedulePayload, user: dict = Depends(require_permission("schedules:write"))):
        conn = get_conn()
        before = _get_schedule(conn, schedule_id)
        conn.execute(
            """
            UPDATE train_schedules
            SET source_name = ?, source_url = ?, route_name = ?, direction = ?, station_name = ?,
                km = ?, train_no = ?, pass_time = ?, day_offset = ?, raw_time_text = ?
            WHERE id = ?
            """,
            (
                payload.source_name,
                payload.source_url,
                payload.route_name,
                payload.direction,
                payload.station_name,
                payload.km,
                payload.train_no,
                payload.pass_time,
                payload.day_offset,
                payload.raw_time_text or payload.pass_time,
                schedule_id,
            ),
        )
        after = _get_schedule(conn, schedule_id)
        _log_audit(conn, user, "schedule", schedule_id, "update", f"Cập nhật lịch tàu {payload.train_no}", before, after)
        conn.commit()
        return after

    @app.delete("/api/admin/schedules/{schedule_id}")
    def delete_schedule_admin(schedule_id: int, user: dict = Depends(require_permission("schedules:delete"))):
        conn = get_conn()
        before = _get_schedule(conn, schedule_id)
        conn.execute("UPDATE train_schedules SET deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (schedule_id,))
        _log_audit(conn, user, "schedule", schedule_id, "soft_delete", f"Ẩn lịch tàu {before['train_no']}", before, None)
        conn.commit()
        return {"status": "ok"}

    @app.post("/api/admin/incidents")
    def create_incident_admin(payload: IncidentPayload, user: dict = Depends(require_permission("incidents:write"))):
        conn = get_conn()
        cursor = conn.execute(
            """
            INSERT INTO incident_reports (
                crossing_id, title, incident_date, severity_level, casualties,
                injured_count, description, source_url
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.crossing_id,
                payload.title,
                payload.incident_date,
                payload.severity_level,
                payload.casualties,
                payload.injured_count,
                payload.description,
                payload.source_url,
            ),
        )
        after = _get_incident(conn, cursor.lastrowid)
        _log_audit(conn, user, "incident", cursor.lastrowid, "create", f"Tạo sự cố {payload.title}", None, after)
        conn.commit()
        return after

    @app.put("/api/admin/incidents/{incident_id}")
    def update_incident_admin(incident_id: int, payload: IncidentPayload, user: dict = Depends(require_permission("incidents:write"))):
        conn = get_conn()
        before = _get_incident(conn, incident_id)
        conn.execute(
            """
            UPDATE incident_reports
            SET crossing_id = ?, title = ?, incident_date = ?, severity_level = ?, casualties = ?,
                injured_count = ?, description = ?, source_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                payload.crossing_id,
                payload.title,
                payload.incident_date,
                payload.severity_level,
                payload.casualties,
                payload.injured_count,
                payload.description,
                payload.source_url,
                incident_id,
            ),
        )
        after = _get_incident(conn, incident_id)
        _log_audit(conn, user, "incident", incident_id, "update", f"Cập nhật sự cố {payload.title}", before, after)
        conn.commit()
        return after

    @app.delete("/api/admin/incidents/{incident_id}")
    def delete_incident_admin(incident_id: int, user: dict = Depends(require_permission("incidents:delete"))):
        conn = get_conn()
        before = _get_incident(conn, incident_id)
        conn.execute("UPDATE incident_reports SET deleted_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (incident_id,))
        _log_audit(conn, user, "incident", incident_id, "soft_delete", f"Ẩn sự cố {before['title']}", before, None)
        conn.commit()
        return {"status": "ok"}

    @app.post("/api/admin/articles")
    def create_article_admin(payload: ArticlePayload, user: dict = Depends(require_permission("articles:write"))):
        conn = get_conn()
        cursor = conn.execute(
            """
            INSERT INTO news_articles (
                crossing_id, source_name, title, url, external_url, image_url, publisher,
                published_at, summary, matched_query, location_hint, severity_score
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.crossing_id,
                payload.source_name,
                payload.title,
                payload.url,
                payload.external_url,
                payload.image_url,
                payload.publisher,
                payload.published_at,
                payload.summary,
                payload.matched_query,
                payload.location_hint,
                payload.severity_score,
            ),
        )
        after = _get_article(conn, cursor.lastrowid)
        _log_audit(conn, user, "article", cursor.lastrowid, "create", f"Tạo bài viết {payload.title}", None, after)
        compute_risk(conn)
        conn.commit()
        return after

    @app.put("/api/admin/articles/{article_id}")
    def update_article_admin(article_id: int, payload: ArticlePayload, user: dict = Depends(require_permission("articles:write"))):
        conn = get_conn()
        before = _get_article(conn, article_id)
        conn.execute(
            """
            UPDATE news_articles
            SET crossing_id = ?, source_name = ?, title = ?, url = ?, external_url = ?, image_url = ?,
                publisher = ?, published_at = ?, summary = ?, matched_query = ?, location_hint = ?,
                severity_score = ?
            WHERE id = ?
            """,
            (
                payload.crossing_id,
                payload.source_name,
                payload.title,
                payload.url,
                payload.external_url,
                payload.image_url,
                payload.publisher,
                payload.published_at,
                payload.summary,
                payload.matched_query,
                payload.location_hint,
                payload.severity_score,
                article_id,
            ),
        )
        after = _get_article(conn, article_id)
        _log_audit(conn, user, "article", article_id, "update", f"Cập nhật bài viết {payload.title}", before, after)
        compute_risk(conn)
        conn.commit()
        return after

    @app.delete("/api/admin/articles/{article_id}")
    def delete_article_admin(article_id: int, user: dict = Depends(require_permission("articles:delete"))):
        conn = get_conn()
        before = _get_article(conn, article_id)
        conn.execute("DELETE FROM news_articles WHERE id = ?", (article_id,))
        _log_audit(conn, user, "article", article_id, "delete", f"Xóa bài viết {before['title']}", before, None)
        compute_risk(conn)
        conn.commit()
        return {"status": "ok"}

    @app.get("/api/admin/users")
    def list_users(user: dict = Depends(require_permission("users:manage"))):
        conn = get_conn()
        return _list_users(conn)

    @app.post("/api/admin/users")
    def create_user(payload: UserPayload, user: dict = Depends(require_permission("users:manage"))):
        conn = get_conn()
        if payload.role not in ROLE_VALUES:
            raise HTTPException(status_code=400, detail="Invalid role")
        cursor = conn.execute(
            """
            INSERT INTO users (username, password_hash, full_name, role, is_active, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                payload.username,
                hash_password(payload.password or "change-me-123"),
                payload.full_name,
                payload.role,
                1 if payload.is_active else 0,
            ),
        )
        row = _get_user(conn, cursor.lastrowid)
        _log_audit(conn, user, "user", cursor.lastrowid, "create", f"Tạo người dùng {payload.username}", None, row)
        conn.commit()
        return row

    @app.put("/api/admin/users/{user_id}")
    def update_user(user_id: int, payload: UserPayload, user: dict = Depends(require_permission("users:manage"))):
        conn = get_conn()
        _require_existing(conn, "users", user_id)
        before = _get_user(conn, user_id)
        conn.execute(
            """
            UPDATE users
            SET username = ?, full_name = ?, role = ?, is_active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (payload.username, payload.full_name, payload.role, 1 if payload.is_active else 0, user_id),
        )
        if payload.password:
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (hash_password(payload.password), user_id),
            )
        after = _get_user(conn, user_id)
        _log_audit(conn, user, "user", user_id, "update", f"Cập nhật người dùng {payload.username}", before, after)
        conn.commit()
        return after

    @app.get("/api/admin/reports/crossings.csv")
    def report_crossings_csv(user: dict = Depends(require_permission("reports:view"))):
        conn = get_conn()
        rows = _list_crossings(conn, include_deleted=True)
        return _csv_response("bao-cao-diem-giao-cat.csv", rows)

    @app.get("/api/admin/reports/quality.csv")
    def report_quality_csv(user: dict = Depends(require_permission("reports:view"))):
        conn = get_conn()
        return _csv_response("bao-cao-chat-luong-du-lieu.csv", _data_quality_alerts(conn))

    return app


def run() -> None:
    import uvicorn

    uvicorn.run(
        "railway_crawler.api:app",
        host=os.getenv("RAILWAY_API_HOST", "127.0.0.1"),
        port=int(os.getenv("RAILWAY_API_PORT", "8000")),
        reload=False,
    )


def _initialize_database(db_path: str) -> None:
    conn = _connect(db_path)
    try:
        try:
            init_db(conn)
        except sqlite3.OperationalError as error:
            if "unable to open database file" not in str(error).lower():
                raise
    finally:
        conn.close()


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return None
    return authorization[len(prefix) :].strip()


def _serialize_user(row: sqlite3.Row | dict) -> dict:
    data = dict(row)
    return {
        "id": data["id"],
        "username": data["username"],
        "full_name": data["full_name"],
        "role": data["role"],
        "is_active": bool(data.get("is_active", 1)),
    }


def _permission_matrix() -> dict[str, list[str]]:
    return {role: sorted(values) for role, values in ROLE_PERMISSIONS.items()}


def _latest_risk_cte() -> str:
    return """
    latest_risks AS (
        SELECT r.*
        FROM risk_snapshots r
        JOIN (
            SELECT crossing_id, MAX(id) AS latest_id
            FROM risk_snapshots
            GROUP BY crossing_id
        ) latest ON latest.latest_id = r.id
    )
    """


def _list_crossings(
    conn: sqlite3.Connection,
    q: str | None = None,
    risk_level: str | None = None,
    barrier_type: str | None = None,
    include_deleted: bool = False,
) -> list[dict]:
    latest = _latest_risk_cte()
    clauses = []
    params: list[object] = []

    if q:
        clauses.append(
            "("
            "lower(c.code) LIKE ? OR lower(c.name) LIKE ? OR COALESCE(lower(c.address), '') LIKE ? OR "
            "COALESCE(lower(c.ward), '') LIKE ? OR COALESCE(lower(c.district), '') LIKE ?"
            ")"
        )
        needle = f"%{q.lower()}%"
        params.extend([needle] * 5)

    if risk_level:
        clauses.append("lr.level = ?")
        params.append(risk_level)

    if barrier_type:
        clauses.append("c.barrier_type = ?")
        params.append(barrier_type)

    if not include_deleted:
        clauses.append("c.deleted_at IS NULL")

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        WITH {latest}
        SELECT
            c.id,
            c.code,
            c.name,
            c.address,
            c.ward,
            c.district,
            c.city,
            c.latitude,
            c.longitude,
            c.crossing_type,
            c.barrier_type,
            c.manager_name,
            c.manager_phone,
            c.verification_status,
            c.coordinate_source,
            c.source_reference,
            c.verification_notes,
            c.surveyed_at,
            c.verified_at,
            c.notes,
            c.deleted_at,
            COALESCE(lr.score, 0) AS risk_score,
            COALESCE(lr.level, 'unknown') AS risk_level,
            COALESCE(json_extract(lr.evidence_json, '$.article_count'), 0) AS article_count,
            COALESCE(json_extract(lr.evidence_json, '$.schedule_count'), 0) AS schedule_count
        FROM crossings c
        LEFT JOIN latest_risks lr ON lr.crossing_id = c.id
        {where_sql}
        ORDER BY CASE WHEN c.deleted_at IS NULL THEN 0 ELSE 1 END, risk_score DESC, c.code
        """,
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def _crossing_detail(conn: sqlite3.Connection, crossing_id: int) -> dict | None:
    latest = _latest_risk_cte()
    row = conn.execute(
        f"""
        WITH {latest}
        SELECT
            c.*,
            COALESCE(lr.score, 0) AS risk_score,
            COALESCE(lr.level, 'unknown') AS risk_level,
            COALESCE(lr.evidence_json, '{{}}') AS evidence_json
        FROM crossings c
        LEFT JOIN latest_risks lr ON lr.crossing_id = c.id
        WHERE c.id = ?
        """,
        (crossing_id,),
    ).fetchone()
    if row is None:
        return None

    crossing = dict(row)
    crossing["evidence"] = json.loads(crossing.pop("evidence_json"))
    crossing["schedules"] = _get_crossing_schedules(conn, crossing)
    crossing["articles"] = _get_crossing_articles(conn, crossing)
    crossing["incidents"] = _get_crossing_incidents(conn, crossing_id)
    crossing["images"] = _get_crossing_images(conn, crossing_id)
    return crossing


def _get_crossing_schedules(conn: sqlite3.Connection, crossing: dict) -> list[dict]:
    station_name = _guess_station(crossing)
    if not station_name:
        return []
    rows = conn.execute(
        """
        SELECT id, station_name, route_name, direction, train_no, pass_time, day_offset
        FROM train_schedules
        WHERE station_name = ? AND deleted_at IS NULL
        ORDER BY direction, pass_time
        LIMIT 20
        """,
        (station_name,),
    ).fetchall()
    return [_serialize_schedule_with_eta(dict(row)) for row in rows]


def _get_crossing_articles(conn: sqlite3.Connection, crossing: dict) -> list[dict]:
    params: list[object] = [crossing["id"]]
    clauses = []
    alias_tokens = []
    if crossing.get("alias_text"):
        alias_tokens.extend([part.strip() for part in str(crossing.get("alias_text")).split("|") if part.strip()])
    for token in _useful_article_tokens(
        [
            crossing.get("name"),
            crossing.get("address"),
            *alias_tokens,
            crossing.get("ward"),
            crossing.get("district"),
        ]
    ):
        if not token:
            continue
        clauses.append("(lower(title) LIKE ? OR lower(summary) LIKE ? OR lower(location_hint) LIKE ?)")
        needle = f"%{token.lower()}%"
        params.extend([needle, needle, needle])
    match_sql = " OR ".join(clauses)
    where_sql = "crossing_id = ?"
    if match_sql:
        where_sql += f" OR (crossing_id IS NULL AND ({match_sql}))"
    rows = conn.execute(
        """
        SELECT id, crossing_id, title, url, external_url, image_url, publisher, published_at, summary, severity_score
        FROM news_articles
        WHERE """
        + where_sql
        + """
        ORDER BY COALESCE(published_at, scraped_at) DESC
        LIMIT 8
        """,
        params,
    ).fetchall()
    articles = [dict(row) for row in rows]
    return [_enrich_article_record(conn, article) for article in articles]


def _enrich_article_record(conn: sqlite3.Connection, article: dict) -> dict:
    article_url = str(article.get("url") or "").strip()
    # Skip synchronous asset resolution for synthetic/local URLs so
    # the public detail page does not block on unreachable hosts.
    if not article_url.startswith("http://") and not article_url.startswith("https://"):
        return article
    if any(token in article_url for token in ["seed.local", "127.0.0.1", "localhost"]):
        return article

    needs_external = not str(article.get("external_url") or "").strip() or str(article.get("external_url") or "").startswith("https://news.google.com/")
    current_image = str(article.get("image_url") or "").strip()
    needs_image = (
        not current_image
        or current_image.startswith("data:image/")
        or "googleusercontent.com" in current_image
    )
    if not needs_external and not needs_image:
        return article

    try:
        assets = resolve_article_assets(article_url, timeout=4)
    except Exception:
        return article

    external_url = assets.get("external_url") or article.get("external_url")
    image_url = assets.get("image_url") or article.get("image_url")
    conn.execute(
        """
        UPDATE news_articles
        SET external_url = ?, image_url = ?
        WHERE url = ?
        """,
        (external_url, image_url, article_url),
    )
    conn.commit()
    article["external_url"] = external_url
    article["image_url"] = image_url
    return article


def _get_crossing_incidents(conn: sqlite3.Connection, crossing_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT *
        FROM incident_reports
        WHERE crossing_id = ? AND deleted_at IS NULL
        ORDER BY COALESCE(incident_date, created_at) DESC
        LIMIT 10
        """,
        (crossing_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _get_crossing_images(conn: sqlite3.Connection, crossing_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT ci.*, u.full_name AS uploaded_by_name
        FROM crossing_images ci
        LEFT JOIN users u ON u.id = ci.uploaded_by
        WHERE ci.crossing_id = ?
        ORDER BY ci.is_cover DESC, ci.sort_order ASC, ci.id ASC
        """,
        (crossing_id,),
    ).fetchall()
    return [_serialize_crossing_image(dict(row)) for row in rows]


def _get_crossing_image(conn: sqlite3.Connection, image_id: int) -> dict:
    row = conn.execute(
        """
        SELECT ci.*, u.full_name AS uploaded_by_name
        FROM crossing_images ci
        LEFT JOIN users u ON u.id = ci.uploaded_by
        WHERE ci.id = ?
        """,
        (image_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Image not found")
    return _serialize_crossing_image(dict(row))


def _serialize_crossing_image(row: dict) -> dict:
    row["url"] = f"/uploads/{row['storage_path'].replace(os.sep, '/')}"
    row["is_cover"] = bool(row.get("is_cover", 0))
    return row


def _crossing_values(payload: CrossingPayload | CrossingImportItem) -> list[object]:
    return [
        payload.code,
        payload.name,
        payload.address,
        payload.ward,
        payload.district,
        payload.city,
        payload.latitude,
        payload.longitude,
        payload.crossing_type,
        payload.barrier_type,
        payload.manager_name,
        payload.manager_phone,
        payload.verification_status,
        payload.coordinate_source,
        payload.source_reference,
        payload.verification_notes,
        payload.surveyed_at,
        payload.verified_at,
        payload.notes,
    ]


def _next_image_sort_order(conn: sqlite3.Connection, crossing_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order FROM crossing_images WHERE crossing_id = ?",
        (crossing_id,),
    ).fetchone()
    return int(row["next_order"])


async def _store_crossing_image(
    conn: sqlite3.Connection,
    crossing_id: int,
    upload: UploadFile,
    uploaded_by: int | None,
    sort_order: int,
    is_cover: bool,
) -> dict:
    suffix = Path(upload.filename or "").suffix.lower() or ".jpg"
    safe_name = f"{secrets.token_hex(12)}{suffix}"
    target_dir = UPLOADS_ROOT / "crossings" / str(crossing_id)
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_name
    with target_path.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)
    file_size = target_path.stat().st_size
    relative_path = target_path.relative_to(UPLOADS_ROOT)
    cursor = conn.execute(
        """
        INSERT INTO crossing_images (
            crossing_id, file_name, original_name, storage_path, mime_type,
            file_size, sort_order, is_cover, uploaded_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            crossing_id,
            safe_name,
            upload.filename or safe_name,
            str(relative_path),
            upload.content_type,
            file_size,
            sort_order,
            1 if is_cover else 0,
            uploaded_by,
        ),
    )
    if is_cover:
        _set_cover_image(conn, crossing_id, cursor.lastrowid)
    return _get_crossing_image(conn, cursor.lastrowid)


def _set_cover_image(conn: sqlite3.Connection, crossing_id: int, image_id: int | None) -> None:
    conn.execute("UPDATE crossing_images SET is_cover = 0 WHERE crossing_id = ?", (crossing_id,))
    if image_id is not None:
        conn.execute("UPDATE crossing_images SET is_cover = 1 WHERE crossing_id = ? AND id = ?", (crossing_id, image_id))


def _normalize_crossing_image_gallery(conn: sqlite3.Connection, crossing_id: int) -> None:
    ids = [
        row["id"]
        for row in conn.execute(
            "SELECT id FROM crossing_images WHERE crossing_id = ? ORDER BY is_cover DESC, sort_order ASC, id ASC",
            (crossing_id,),
        ).fetchall()
    ]
    for index, image_id in enumerate(ids):
        conn.execute("UPDATE crossing_images SET sort_order = ? WHERE id = ?", (index, image_id))
    cover_row = conn.execute(
        "SELECT id FROM crossing_images WHERE crossing_id = ? AND is_cover = 1 ORDER BY sort_order ASC, id ASC LIMIT 1",
        (crossing_id,),
    ).fetchone()
    if cover_row is None:
        first_row = conn.execute(
            "SELECT id FROM crossing_images WHERE crossing_id = ? ORDER BY sort_order ASC, id ASC LIMIT 1",
            (crossing_id,),
        ).fetchone()
        if first_row is not None:
            _set_cover_image(conn, crossing_id, first_row["id"])


def _update_crossing_image_gallery(conn: sqlite3.Connection, crossing_id: int, payload: CrossingImageGalleryPayload) -> None:
    current_rows = conn.execute(
        "SELECT id FROM crossing_images WHERE crossing_id = ?",
        (crossing_id,),
    ).fetchall()
    current_ids = {row["id"] for row in current_rows}
    for item in payload.items:
        if item.id not in current_ids:
            raise HTTPException(status_code=400, detail="Invalid image id in gallery update")
        conn.execute(
            "UPDATE crossing_images SET sort_order = ? WHERE crossing_id = ? AND id = ?",
            (item.sort_order, crossing_id, item.id),
        )
    if payload.cover_image_id is not None:
        if payload.cover_image_id not in current_ids:
            raise HTTPException(status_code=400, detail="Cover image does not belong to crossing")
        _set_cover_image(conn, crossing_id, payload.cover_image_id)
    _normalize_crossing_image_gallery(conn, crossing_id)


def _get_schedule(conn: sqlite3.Connection, schedule_id: int) -> dict:
    row = conn.execute("SELECT * FROM train_schedules WHERE id = ?", (schedule_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return dict(row)


def _get_incident(conn: sqlite3.Connection, incident_id: int) -> dict:
    row = conn.execute(
        """
        SELECT ir.*, c.name AS crossing_name
        FROM incident_reports ir
        LEFT JOIN crossings c ON c.id = ir.crossing_id
        WHERE ir.id = ?
        """,
        (incident_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return dict(row)


def _get_article(conn: sqlite3.Connection, article_id: int) -> dict:
    row = conn.execute(
        """
        SELECT na.*, c.name AS crossing_name
        FROM news_articles na
        LEFT JOIN crossings c ON c.id = na.crossing_id
        WHERE na.id = ?
        """,
        (article_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Article not found")
    return dict(row)


def _get_user(conn: sqlite3.Connection, user_id: int) -> dict:
    row = conn.execute(
        """
        SELECT id, username, full_name, role, is_active, created_at, updated_at
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return dict(row)


def _get_row_dict(conn: sqlite3.Connection, table_name: str, row_id: int) -> dict | None:
    row = conn.execute(f"SELECT * FROM {table_name} WHERE id = ?", (row_id,)).fetchone()
    return dict(row) if row is not None else None


def _list_users(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, username, full_name, role, is_active, created_at, updated_at
        FROM users
        ORDER BY role, username
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _list_admin_schedules(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT *
        FROM train_schedules
        ORDER BY CASE WHEN deleted_at IS NULL THEN 0 ELSE 1 END, station_name, direction, pass_time
        LIMIT 300
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _list_admin_articles(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT na.*, c.name AS crossing_name
        FROM news_articles na
        LEFT JOIN crossings c ON c.id = na.crossing_id
        ORDER BY COALESCE(na.published_at, na.scraped_at) DESC, na.id DESC
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _useful_article_tokens(tokens: list[object]) -> list[str]:
    seen: set[str] = set()
    useful: list[str] = []
    for token in tokens:
        value = str(token or "").strip()
        normalized = value.lower()
        if not value or len(normalized) < 4:
            continue
        if normalized.startswith("giao cắt "):
            normalized = normalized.replace("giao cắt ", "", 1).strip()
            value = value[9:].strip()
        if not value or normalized in GENERIC_ARTICLE_TOKENS:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        useful.append(value)
    return useful


def _list_public_schedules(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, source_name, route_name, direction, station_name, km, train_no, pass_time, day_offset, raw_time_text
        FROM train_schedules
        WHERE deleted_at IS NULL
        ORDER BY station_name, direction, pass_time
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [_serialize_schedule_with_eta(dict(row)) for row in rows]


def _serialize_schedule_with_eta(row: dict) -> dict:
    next_pass_at, eta_minutes = _next_schedule_occurrence(row["pass_time"], int(row.get("day_offset") or 0))
    row["next_pass_at"] = next_pass_at.isoformat() if next_pass_at else None
    row["eta_minutes"] = eta_minutes
    row["eta_label"] = _eta_label(eta_minutes)
    return row


def _next_schedule_occurrence(pass_time: str, day_offset: int) -> tuple[datetime | None, int | None]:
    try:
        hour_text, minute_text = pass_time.split(":", maxsplit=1)
        hour = int(hour_text)
        minute = int(minute_text)
    except (ValueError, AttributeError):
        return None, None

    now = datetime.now()
    candidate = now.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=day_offset)
    if candidate < now - timedelta(minutes=1):
        candidate += timedelta(days=1)
    eta_minutes = max(0, int((candidate - now).total_seconds() // 60))
    return candidate, eta_minutes


def _eta_label(eta_minutes: int | None) -> str | None:
    if eta_minutes is None:
        return None
    if eta_minutes <= 5:
        return "Sắp qua"
    if eta_minutes <= 30:
        return f"{eta_minutes} phút tới"
    if eta_minutes <= 120:
        return f"{eta_minutes} phút nữa"
    if eta_minutes < 24 * 60:
        return "Hôm nay"
    if eta_minutes < 48 * 60:
        return "Ngày mai"
    return f"+{eta_minutes // (24 * 60)} ngày"


def _list_admin_incidents(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT ir.*, c.name AS crossing_name
        FROM incident_reports ir
        LEFT JOIN crossings c ON c.id = ir.crossing_id
        ORDER BY CASE WHEN ir.deleted_at IS NULL THEN 0 ELSE 1 END, COALESCE(ir.incident_date, ir.created_at) DESC
        LIMIT 300
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _list_public_incidents(conn: sqlite3.Connection, limit: int = 100) -> list[dict]:
    rows = conn.execute(
        """
        SELECT ir.*, c.name AS crossing_name, c.code AS crossing_code
        FROM incident_reports ir
        LEFT JOIN crossings c ON c.id = ir.crossing_id
        WHERE ir.deleted_at IS NULL
        ORDER BY COALESCE(ir.incident_date, ir.created_at) DESC, ir.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def _list_audit_logs(
    conn: sqlite3.Connection,
    limit: int = 50,
    entity_type: str | None = None,
    entity_id: int | None = None,
) -> list[dict]:
    clauses = []
    params: list[object] = []
    if entity_type:
        clauses.append("entity_type = ?")
        params.append(entity_type)
    if entity_id is not None:
        clauses.append("entity_id = ?")
        params.append(entity_id)
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"""
        SELECT id, user_id, username, user_role, entity_type, entity_id, action, summary, created_at
        FROM audit_logs
        {where_sql}
        ORDER BY id DESC
        LIMIT ?
        """,
        [*params, limit],
    ).fetchall()
    return [dict(row) for row in rows]


def _log_audit(
    conn: sqlite3.Connection,
    user: dict,
    entity_type: str,
    entity_id: int | None,
    action: str,
    summary: str,
    before: dict | None,
    after: dict | None,
) -> None:
    conn.execute(
        """
        INSERT INTO audit_logs (
            user_id, username, user_role, entity_type, entity_id, action, summary, before_json, after_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user.get("id"),
            user.get("username"),
            user.get("role"),
            entity_type,
            entity_id,
            action,
            summary,
            json.dumps(before, ensure_ascii=False) if before is not None else None,
            json.dumps(after, ensure_ascii=False) if after is not None else None,
        ),
    )


def _data_quality_alerts(conn: sqlite3.Connection) -> list[dict]:
    alerts: list[dict] = []
    crossings = _list_crossings(conn, include_deleted=True)
    code_counts: dict[str, int] = {}
    for crossing in crossings:
        code_counts[crossing["code"]] = code_counts.get(crossing["code"], 0) + 1

    for crossing in crossings:
        alerts.extend(_quality_alerts_for_crossing(conn, crossing))

    for code, count in code_counts.items():
        if count > 1:
            alerts.append(
                {
                    "type": "duplicate_code",
                    "severity": "high",
                    "title": f"Mã điểm trùng lặp: {code}",
                    "crossing_id": None,
                    "detail": f"Có {count} bản ghi đang dùng cùng mã điểm.",
                }
            )

    return alerts[:200]


def _quality_alerts_for_crossing(conn: sqlite3.Connection, crossing: dict) -> list[dict]:
    alerts: list[dict] = []
    crossing_id = crossing["id"]

    if crossing.get("deleted_at"):
        alerts.append(
            {
                "type": "archived",
                "severity": "low",
                "title": f"{crossing['name']} đang bị ẩn",
                "crossing_id": crossing_id,
                "detail": "Bản ghi này đã bị ẩn và cần kiểm tra trước khi sử dụng lại.",
            }
        )
    if not crossing.get("latitude") or not crossing.get("longitude"):
        alerts.append(
            {
                "type": "missing_coordinates",
                "severity": "high",
                "title": f"{crossing['name']} thiếu tọa độ",
                "crossing_id": crossing_id,
                "detail": "Thiếu vĩ độ hoặc kinh độ nên không thể hiển thị đúng trên bản đồ.",
            }
        )
    if not crossing.get("manager_name"):
        alerts.append(
            {
                "type": "missing_manager",
                "severity": "medium",
                "title": f"{crossing['name']} chưa có người quản lý",
                "crossing_id": crossing_id,
                "detail": "Cần gán người phụ trách để thuận tiện cho vận hành và xác minh.",
            }
        )
    if crossing.get("verification_status") != "verified":
        alerts.append(
            {
                "type": "verification_pending",
                "severity": "medium",
                "title": f"{crossing['name']} chưa xác minh hoàn tất",
                "crossing_id": crossing_id,
                "detail": f"Trạng thái hiện tại: {_verification_status_label(crossing.get('verification_status'))}.",
            }
        )
    schedule_count = conn.execute(
        "SELECT COUNT(*) AS total FROM train_schedules WHERE deleted_at IS NULL AND station_name = ?",
        (_guess_station(crossing) or "",),
    ).fetchone()["total"]
    if not schedule_count:
        alerts.append(
            {
                "type": "missing_schedule",
                "severity": "medium",
                "title": f"{crossing['name']} chưa liên kết lịch tàu",
                "crossing_id": crossing_id,
                "detail": "Không tìm thấy lịch tàu tương ứng để phục vụ cảnh báo.",
            }
        )
    image_count = conn.execute(
        "SELECT COUNT(*) AS total FROM crossing_images WHERE crossing_id = ?",
        (crossing_id,),
    ).fetchone()["total"]
    if not image_count:
        alerts.append(
            {
                "type": "missing_images",
                "severity": "low",
                "title": f"{crossing['name']} chưa có ảnh hiện trường",
                "crossing_id": crossing_id,
                "detail": "Nên bổ sung ảnh hiện trường để hồ sơ điểm đầy đủ hơn.",
            }
        )
    return alerts


def _csv_response(filename: str, rows: list[dict]) -> StreamingResponse:
    buffer = StringIO()
    fieldnames = list(rows[0].keys()) if rows else ["message"]
    writer = DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    if rows:
        writer.writerows(rows)
    else:
        writer.writerow({"message": "Không có dữ liệu"})
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _verification_status_label(value: str | None) -> str:
    return {
        "draft": "Bản nháp",
        "surveyed": "Đã khảo sát",
        "verified": "Đã xác minh",
    }.get(value or "draft", value or "Bản nháp")


def _require_existing(conn: sqlite3.Connection, table_name: str, row_id: int) -> None:
    row = conn.execute(f"SELECT id FROM {table_name} WHERE id = ?", (row_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"{table_name} row not found")


def _guess_station(crossing: dict) -> str | None:
    merged = " ".join(
        filter(
            None,
            [
                crossing.get("name"),
                crossing.get("address"),
                crossing.get("ward"),
                crossing.get("district"),
                crossing.get("city"),
                crossing.get("alias_text"),
            ],
        )
    ).lower()
    if any(
        token in merged
        for token in [
            "biên hòa",
            "bien hoa",
            "long bình",
            "long binh",
            "hố nai",
            "ho nai",
            "tam hòa",
            "tam hoa",
            "tân biên",
            "tan bien",
            "tam hiệp",
            "tam hiep",
        ]
    ):
        return "Biên Hòa"
    if any(token in merged for token in ["dĩ an", "di an"]):
        return "Dĩ An"
    if any(token in merged for token in ["long khánh", "long khanh"]):
        return "Long Khánh"
    return None


app = create_app()
