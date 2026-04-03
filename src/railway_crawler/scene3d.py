from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
import sqlite3
import struct
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy
import tifffile


DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "generated" / "scene3d"

ROAD_WIDTHS = {
    "motorway": 28,
    "trunk": 24,
    "primary": 18,
    "secondary": 14,
    "tertiary": 12,
    "residential": 10,
    "service": 8,
    "unclassified": 9,
}

RAIL_WIDTHS = {
    "rail": 5.5,
    "light_rail": 4.8,
    "tram": 4.2,
    "subway": 5.0,
    "construction": 4.8,
}

LANDUSE_COLORS = {
    "residential": "#d9dbc7",
    "industrial": "#cec8bc",
    "commercial": "#dad6c8",
    "forest": "#8cad74",
    "grass": "#9fc07f",
    "meadow": "#a9c984",
    "farmland": "#b8c47b",
    "railway": "#bbb5a9",
}

WATER_COLORS = {
    "river": "#77a9d8",
    "stream": "#77a9d8",
    "canal": "#6fa2d4",
    "pond": "#7ab7e6",
    "lake": "#72b1e0",
    "reservoir": "#72b1e0",
    "basin": "#72b1e0",
    "water": "#72b1e0",
}

ROAD_RANKS = {
    "motorway": 0,
    "trunk": 1,
    "primary": 2,
    "secondary": 3,
    "tertiary": 4,
    "residential": 5,
    "service": 6,
    "unclassified": 7,
}

BUILDING_KIND_STYLES = {
    "apartments": {"height": 28, "wall": "#f5f4ef", "roof": "#e6e2d8"},
    "residential": {"height": 14, "wall": "#f7f5ef", "roof": "#e9e4d9"},
    "house": {"height": 11, "wall": "#f8f6f1", "roof": "#e1ddd2"},
    "detached": {"height": 10, "wall": "#faf7f1", "roof": "#e4dfd3"},
    "commercial": {"height": 20, "wall": "#f2f1ec", "roof": "#ddd8cc"},
    "retail": {"height": 16, "wall": "#f6f4ed", "roof": "#ded8cb"},
    "office": {"height": 24, "wall": "#f1f3f4", "roof": "#d6dde0"},
    "industrial": {"height": 18, "wall": "#ece7de", "roof": "#d5cec3"},
    "warehouse": {"height": 16, "wall": "#efebe2", "roof": "#d2cbbb"},
    "school": {"height": 15, "wall": "#f7f5ef", "roof": "#d8d2c5"},
    "hospital": {"height": 22, "wall": "#f4f6f8", "roof": "#d7dde2"},
    "civic": {"height": 18, "wall": "#f3f1eb", "roof": "#d8d1c3"},
    "yes": {"height": 12, "wall": "#f6f4ee", "roof": "#e0dbcf"},
    "building": {"height": 12, "wall": "#f6f4ee", "roof": "#e0dbcf"},
}


@dataclass
class TileFeatureCounts:
    crossings: int = 0
    roads: int = 0
    railways: int = 0
    buildings: int = 0
    landuse: int = 0
    water: int = 0
    powerlines: int = 0
    landmarks: int = 0


def export_scene_bundle(
    conn: sqlite3.Connection,
    output_dir: str | Path | None = None,
    tile_size_degrees: float = 0.01,
    osm_path: str | Path | None = None,
    gpkg_path: str | Path | None = None,
    dem_path: str | Path | None = None,
) -> dict:
    output_root = Path(output_dir or DEFAULT_OUTPUT_DIR)
    tiles_dir = output_root / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)

    crossings = _load_crossings(conn)
    scene_bbox = _expand_bounds(_bounds_from_crossings(crossings), margin=0.06)
    if gpkg_path:
        osm_features = parse_gpkg_osm(gpkg_path, bbox=scene_bbox, cache_path=output_root / "gpkg_subset_cache.sqlite")
    elif osm_path:
        osm_features = parse_osm_xml(osm_path)
    else:
        osm_features = _empty_osm_features()
    dem = parse_dem(dem_path) if dem_path else None
    manifest, buckets = _build_manifest(crossings, osm_features, dem, tile_size_degrees)

    written_tiles = []
    for tile in manifest["tiles"]:
        tile_path = tiles_dir / f"{tile['id']}.json"
        payload = _build_tile_payload(tile, buckets.get(tile["id"], {}), dem)
        tile_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written_tiles.append(tile_path)

    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "output_dir": str(output_root),
        "manifest": str(manifest_path),
        "tiles": len(written_tiles),
        "crossings": len(crossings),
        "roads": len(osm_features["roads"]),
        "railways": len(osm_features["railways"]),
        "buildings": len(osm_features["buildings"]),
        "landuse": len(osm_features["landuse"]),
        "water": len(osm_features["water"]),
        "powerlines": len(osm_features["powerlines"]),
        "terrain": bool(dem),
        "osm_source": str(osm_path) if osm_path else None,
        "gpkg_source": str(gpkg_path) if gpkg_path else None,
        "dem_source": str(dem_path) if dem_path else None,
    }


def read_scene_manifest(output_dir: str | Path | None = None) -> dict:
    manifest_path = Path(output_dir or DEFAULT_OUTPUT_DIR) / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def read_scene_tile(tile_id: str, output_dir: str | Path | None = None) -> dict:
    tile_path = Path(output_dir or DEFAULT_OUTPUT_DIR) / "tiles" / f"{tile_id}.json"
    return json.loads(tile_path.read_text(encoding="utf-8"))


def parse_osm_xml(osm_path: str | Path) -> dict:
    osm_file = Path(osm_path)
    root = ET.fromstring(osm_file.read_text(encoding="utf-8"))

    nodes = {}
    power_nodes = {}

    for node in root.findall("node"):
        node_id = node.attrib.get("id")
        if not node_id:
            continue
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in node.findall("tag")}
        record = {
            "id": node_id,
            "longitude": float(node.attrib["lon"]),
            "latitude": float(node.attrib["lat"]),
            "tags": tags,
        }
        nodes[node_id] = record
        if tags.get("power") in {"tower", "pole"}:
            power_nodes[node_id] = record

    way_geometries = {}
    roads = []
    railways = []
    buildings = []
    landuse = []
    water = []
    powerlines = []

    for way in root.findall("way"):
        way_id = way.attrib.get("id")
        refs = [nd.attrib["ref"] for nd in way.findall("nd") if nd.attrib.get("ref") in nodes]
        if len(refs) < 2 or not way_id:
            continue

        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in way.findall("tag")}
        coordinates = [nodes[ref] for ref in refs]
        way_geometries[way_id] = {"refs": refs, "coords": coordinates, "tags": tags}

        road = _road_from_osm_way(way_id, coordinates, tags)
        if road:
            roads.append(road)

        railway = _railway_from_osm_way(way_id, coordinates, tags)
        if railway:
            railways.append(railway)

        building = _building_from_osm_way(way_id, coordinates, tags)
        if building:
            buildings.append(building)

        landuse_feature = _landuse_from_osm_way(way_id, coordinates, tags)
        if landuse_feature:
            landuse.append(landuse_feature)

        water_feature = _water_from_osm_way(way_id, coordinates, tags)
        if water_feature:
            water.append(water_feature)

        powerline = _powerline_from_osm_way(way_id, coordinates, tags, power_nodes)
        if powerline:
            powerlines.append(powerline)

    for relation in root.findall("relation"):
        relation_id = relation.attrib.get("id")
        if not relation_id:
            continue
        tags = {tag.attrib["k"]: tag.attrib["v"] for tag in relation.findall("tag")}
        if tags.get("type") != "multipolygon":
            continue

        if "building" in tags:
            building_kind = tags.get("building", "yes")
            style = _building_style(building_kind)
            building = _polygon_feature_from_relation(
                relation,
                way_geometries,
                tags,
                feature_type="building",
                default_kind=building_kind,
                color=style["wall"],
            )
            if building:
                building["heightMeters"] = _safe_float(tags.get("height")) or style["height"]
                building["wallColor"] = style["wall"]
                building["roofColor"] = style["roof"]
                buildings.append(building)

        landuse_feature = _landuse_from_relation(relation, way_geometries, tags)
        if landuse_feature:
            landuse.append(landuse_feature)

        water_feature = _water_from_relation(relation, way_geometries, tags)
        if water_feature:
            water.append(water_feature)

    return {
        "roads": roads,
        "railways": railways,
        "buildings": buildings,
        "landuse": landuse,
        "water": water,
        "powerlines": powerlines,
        "bounds": _bounds_from_features(
            roads=roads,
            railways=railways,
            buildings=buildings,
            landuse=landuse,
            water=water,
            powerlines=powerlines,
        ),
    }


def parse_gpkg_osm(gpkg_path: str | Path, bbox: dict | None = None, cache_path: str | Path | None = None) -> dict:
    gpkg_file = Path(gpkg_path)
    conn = _prepare_gpkg_subset_cache(gpkg_file, bbox, Path(cache_path)) if cache_path else sqlite3.connect(gpkg_file)
    conn.row_factory = sqlite3.Row
    try:
        roads = list(_iter_gpkg_roads(conn, bbox, from_cache=bool(cache_path)))
        railways = list(_iter_gpkg_railways(conn, bbox, from_cache=bool(cache_path)))
        buildings = list(_iter_gpkg_buildings(conn, bbox, from_cache=bool(cache_path)))
        landuse = list(_iter_gpkg_polygons(conn, "gis_osm_landuse_a_free", bbox, feature_type="landuse", from_cache=bool(cache_path)))
        water_polygons = list(_iter_gpkg_polygons(conn, "gis_osm_water_a_free", bbox, feature_type="water", from_cache=bool(cache_path)))
        waterways = list(_iter_gpkg_waterways(conn, bbox, from_cache=bool(cache_path)))
        water = [*water_polygons, *waterways]
    finally:
        conn.close()

    return {
        "roads": roads,
        "railways": railways,
        "buildings": buildings,
        "landuse": landuse,
        "water": water,
        "powerlines": [],
        "bounds": _bounds_from_features(
            roads=roads,
            railways=railways,
            buildings=buildings,
            landuse=landuse,
            water=water,
            powerlines=[],
        ),
    }


def parse_dem(dem_path: str | Path | list[str] | list[Path] | tuple[str | Path, ...]) -> dict:
    dem_files = _normalize_dem_paths(dem_path)
    if not dem_files:
        raise ValueError("No DEM files were provided")

    parsed = [_parse_single_dem(path) for path in dem_files]
    if len(parsed) == 1:
        return parsed[0]
    return _merge_dem_tiles(parsed)


def _normalize_dem_paths(dem_path: str | Path | list[str] | list[Path] | tuple[str | Path, ...]) -> list[Path]:
    if dem_path is None:
        return []

    items: list[str | Path]
    if isinstance(dem_path, (list, tuple, set)):
        items = list(dem_path)
    else:
        text = str(dem_path)
        path_candidate = Path(text)
        if os.pathsep in text and not path_candidate.exists():
            items = [part for part in text.split(os.pathsep) if part.strip()]
        elif "," in text and not path_candidate.exists():
            items = [part for part in text.split(",") if part.strip()]
        else:
            items = [dem_path]

    files: list[Path] = []
    for item in items:
        path = Path(item)
        if path.is_dir():
            files.extend(sorted(path.glob("*.tif")))
            files.extend(sorted(path.glob("*.tiff")))
            files.extend(sorted(path.glob("*.asc")))
            files.extend(sorted(path.glob("*.grd")))
            files.extend(sorted(path.glob("*.json")))
        else:
            files.append(path)
    return files


def _parse_single_dem(dem_file: Path) -> dict:
    suffix = dem_file.suffix.lower()
    if suffix == ".json":
        return parse_dem_json(dem_file)
    if suffix in {".asc", ".grd"}:
        return parse_dem_ascii_grid(dem_file)
    if suffix in {".tif", ".tiff"}:
        return parse_dem_geotiff(dem_file)
    raise ValueError(f"Unsupported DEM format: {dem_file.suffix}")


def _prepare_gpkg_subset_cache(gpkg_path: Path, bbox: dict | None, cache_path: Path) -> sqlite3.Connection:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    source_stat = gpkg_path.stat()
    bbox_json = json.dumps(bbox or {}, sort_keys=True)

    if cache_path.exists():
        cache_conn = sqlite3.connect(cache_path)
        cache_conn.row_factory = sqlite3.Row
        try:
            metadata = dict(cache_conn.execute("SELECT key, value FROM metadata").fetchall())
            if (
                metadata.get("source_path") == str(gpkg_path)
                and metadata.get("source_size") == str(source_stat.st_size)
                and metadata.get("source_mtime_ns") == str(source_stat.st_mtime_ns)
                and metadata.get("bbox") == bbox_json
            ):
                return cache_conn
        except sqlite3.Error:
            pass
        cache_conn.close()
        cache_path.unlink(missing_ok=True)

    cache_conn = sqlite3.connect(cache_path)
    cache_conn.row_factory = sqlite3.Row
    _init_gpkg_subset_cache(cache_conn)

    source_conn = sqlite3.connect(gpkg_path)
    source_conn.row_factory = sqlite3.Row
    try:
        _populate_gpkg_subset_cache(source_conn, cache_conn, bbox)
    finally:
        source_conn.close()

    cache_conn.executemany(
        "INSERT INTO metadata (key, value) VALUES (?, ?)",
        [
            ("source_path", str(gpkg_path)),
            ("source_size", str(source_stat.st_size)),
            ("source_mtime_ns", str(source_stat.st_mtime_ns)),
            ("bbox", bbox_json),
        ],
    )
    cache_conn.commit()
    return cache_conn


def _init_gpkg_subset_cache(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE roads (
            fid INTEGER PRIMARY KEY,
            osm_id TEXT,
            fclass TEXT,
            name TEXT,
            ref TEXT,
            geom BLOB NOT NULL,
            west REAL NOT NULL,
            south REAL NOT NULL,
            east REAL NOT NULL,
            north REAL NOT NULL
        );

        CREATE TABLE railways (
            fid INTEGER PRIMARY KEY,
            osm_id TEXT,
            fclass TEXT,
            name TEXT,
            geom BLOB NOT NULL,
            west REAL NOT NULL,
            south REAL NOT NULL,
            east REAL NOT NULL,
            north REAL NOT NULL
        );

        CREATE TABLE buildings (
            fid INTEGER PRIMARY KEY,
            osm_id TEXT,
            fclass TEXT,
            name TEXT,
            type TEXT,
            geom BLOB NOT NULL,
            west REAL NOT NULL,
            south REAL NOT NULL,
            east REAL NOT NULL,
            north REAL NOT NULL
        );

        CREATE TABLE landuse (
            fid INTEGER PRIMARY KEY,
            osm_id TEXT,
            fclass TEXT,
            name TEXT,
            geom BLOB NOT NULL,
            west REAL NOT NULL,
            south REAL NOT NULL,
            east REAL NOT NULL,
            north REAL NOT NULL
        );

        CREATE TABLE water_polygons (
            fid INTEGER PRIMARY KEY,
            osm_id TEXT,
            fclass TEXT,
            name TEXT,
            geom BLOB NOT NULL,
            west REAL NOT NULL,
            south REAL NOT NULL,
            east REAL NOT NULL,
            north REAL NOT NULL
        );

        CREATE TABLE waterways (
            fid INTEGER PRIMARY KEY,
            osm_id TEXT,
            fclass TEXT,
            width REAL,
            name TEXT,
            geom BLOB NOT NULL,
            west REAL NOT NULL,
            south REAL NOT NULL,
            east REAL NOT NULL,
            north REAL NOT NULL
        );

        CREATE INDEX idx_roads_bbox ON roads (west, east, south, north);
        CREATE INDEX idx_railways_bbox ON railways (west, east, south, north);
        CREATE INDEX idx_buildings_bbox ON buildings (west, east, south, north);
        CREATE INDEX idx_landuse_bbox ON landuse (west, east, south, north);
        CREATE INDEX idx_water_polygons_bbox ON water_polygons (west, east, south, north);
        CREATE INDEX idx_waterways_bbox ON waterways (west, east, south, north);
        """
    )
    conn.commit()


def _populate_gpkg_subset_cache(source_conn: sqlite3.Connection, cache_conn: sqlite3.Connection, bbox: dict | None) -> None:
    specs = [
        ("gis_osm_roads_free", "roads", ["fid", "osm_id", "fclass", "name", "ref", "geom"]),
        ("gis_osm_railways_free", "railways", ["fid", "osm_id", "fclass", "name", "geom"]),
        ("gis_osm_buildings_a_free", "buildings", ["fid", "osm_id", "fclass", "name", "type", "geom"]),
        ("gis_osm_landuse_a_free", "landuse", ["fid", "osm_id", "fclass", "name", "geom"]),
        ("gis_osm_water_a_free", "water_polygons", ["fid", "osm_id", "fclass", "name", "geom"]),
        ("gis_osm_waterways_free", "waterways", ["fid", "osm_id", "fclass", "width", "name", "geom"]),
    ]

    for source_table, cache_table, columns in specs:
        sql = f"SELECT {', '.join(columns)} FROM {source_table}"
        placeholders = ", ".join(["?"] * (len(columns) + 4))
        insert_sql = f"INSERT INTO {cache_table} VALUES ({placeholders})"
        batch = []
        for row in source_conn.execute(sql):
            geometry = _decode_gpkg_geometry(row["geom"])
            if not geometry or not _bounds_intersect(geometry.get("bounds"), bbox):
                continue
            bounds = geometry["bounds"]
            batch.append(tuple(row[column] for column in columns) + (bounds["west"], bounds["south"], bounds["east"], bounds["north"]))
            if len(batch) >= 5000:
                cache_conn.executemany(insert_sql, batch)
                batch.clear()
        if batch:
            cache_conn.executemany(insert_sql, batch)
        cache_conn.commit()


def _bbox_sql_where(prefix: str = "") -> str:
    if prefix:
        prefix = f"{prefix}."
    return f"WHERE {prefix}east >= ? AND {prefix}west <= ? AND {prefix}north >= ? AND {prefix}south <= ?"


def _bbox_params(bbox: dict | None) -> tuple[float, float, float, float]:
    target = bbox or {"west": -180.0, "south": -90.0, "east": 180.0, "north": 90.0}
    return (target["west"], target["east"], target["south"], target["north"])


def _iter_gpkg_roads(conn: sqlite3.Connection, bbox: dict | None, from_cache: bool = False):
    if from_cache:
        query = f"""
            SELECT fid, osm_id, fclass, name, ref, geom
            FROM roads
            {_bbox_sql_where()}
        """
    else:
        query = """
            SELECT fid, osm_id, fclass, name, ref, geom
            FROM gis_osm_roads_free
        """
    for row in conn.execute(query, _bbox_params(bbox) if from_cache else ()):
        geometry = _decode_gpkg_geometry(row["geom"])
        if not geometry or geometry["type"] != "LineString":
            continue
        if not _bounds_intersect(geometry["bounds"], bbox):
            continue
        coordinates = _coords_to_points(geometry["coordinates"])
        road = {
            "id": f"gpkg-road-{row['fid']}",
            "source": "gpkg",
            "osmWayId": row["osm_id"],
            "kind": row["fclass"] or "unclassified",
            "rank": ROAD_RANKS.get(row["fclass"] or "unclassified", 99),
            "name": row["name"] or row["ref"],
            "surface": None,
            "lanes": None,
            "widthMeters": ROAD_WIDTHS.get(row["fclass"] or "unclassified", 9),
            "centerline": coordinates,
            "labelAnchor": _label_anchor(coordinates),
        }
        yield road


def _iter_gpkg_railways(conn: sqlite3.Connection, bbox: dict | None, from_cache: bool = False):
    if from_cache:
        query = f"""
            SELECT fid, osm_id, fclass, name, geom
            FROM railways
            {_bbox_sql_where()}
        """
    else:
        query = """
            SELECT fid, osm_id, fclass, name, geom
            FROM gis_osm_railways_free
        """
    for row in conn.execute(query, _bbox_params(bbox) if from_cache else ()):
        geometry = _decode_gpkg_geometry(row["geom"])
        if not geometry or geometry["type"] != "LineString":
            continue
        if not _bounds_intersect(geometry["bounds"], bbox):
            continue
        coordinates = _coords_to_points(geometry["coordinates"])
        railway_type = row["fclass"] or "rail"
        yield {
            "id": f"gpkg-railway-{row['fid']}",
            "source": "gpkg",
            "osmWayId": row["osm_id"],
            "kind": railway_type,
            "name": row["name"],
            "gauge": None,
            "widthMeters": RAIL_WIDTHS.get(railway_type, 4.8),
            "centerline": coordinates,
            "labelAnchor": _label_anchor(coordinates),
        }


def _iter_gpkg_buildings(conn: sqlite3.Connection, bbox: dict | None, from_cache: bool = False):
    if from_cache:
        query = f"""
            SELECT fid, osm_id, fclass, name, type, geom
            FROM buildings
            {_bbox_sql_where()}
        """
    else:
        query = """
            SELECT fid, osm_id, fclass, name, type, geom
            FROM gis_osm_buildings_a_free
        """
    for row in conn.execute(query, _bbox_params(bbox) if from_cache else ()):
        geometry = _decode_gpkg_geometry(row["geom"])
        if not geometry or geometry["type"] not in {"Polygon", "MultiPolygon"}:
            continue
        if not _bounds_intersect(geometry["bounds"], bbox):
            continue
        for polygon_index, polygon in enumerate(_geometry_polygons(geometry)):
            exterior, holes = polygon
            if len(exterior) < 3:
                continue
            feature_id = f"gpkg-building-{row['fid']}-{polygon_index}"
            building_kind = row["type"] or row["fclass"] or "building"
            building_style = _building_style(building_kind)
            yield {
                "id": feature_id,
                "source": "gpkg",
                "osmWayId": row["osm_id"],
                "kind": building_kind,
                "name": row["name"],
                "heightMeters": building_style["height"],
                "levels": None,
                "roofColor": building_style["roof"],
                "wallColor": building_style["wall"],
                "footprint": _coords_to_points(exterior, include_elevation=False),
                "holes": [_coords_to_points(ring, include_elevation=False) for ring in holes],
            }


def _iter_gpkg_polygons(conn: sqlite3.Connection, table_name: str, bbox: dict | None, *, feature_type: str, from_cache: bool = False):
    source_table = {
        "gis_osm_landuse_a_free": "landuse",
        "gis_osm_water_a_free": "water_polygons",
    }.get(table_name, table_name)
    query = (
        f"SELECT fid, osm_id, fclass, name, geom FROM {source_table} {_bbox_sql_where()}"
        if from_cache
        else f"SELECT fid, osm_id, fclass, name, geom FROM {table_name}"
    )
    color_map = LANDUSE_COLORS if feature_type == "landuse" else WATER_COLORS
    height = 0.4 if feature_type == "landuse" else 0.08

    for row in conn.execute(query, _bbox_params(bbox) if from_cache else ()):
        geometry = _decode_gpkg_geometry(row["geom"])
        if not geometry or geometry["type"] not in {"Polygon", "MultiPolygon"}:
            continue
        if not _bounds_intersect(geometry["bounds"], bbox):
            continue
        for polygon_index, polygon in enumerate(_geometry_polygons(geometry)):
            exterior, holes = polygon
            if len(exterior) < 3:
                continue
            kind = row["fclass"] or feature_type
            yield {
                "id": f"gpkg-{feature_type}-{row['fid']}-{polygon_index}",
                "source": "gpkg",
                "osmWayId": row["osm_id"],
                "kind": kind,
                "name": row["name"],
                "geometryType": "polygon",
                "heightMeters": height,
                "color": color_map.get(kind, "#a7bd8e" if feature_type == "landuse" else "#72b1e0"),
                "footprint": _coords_to_points(exterior, include_elevation=False),
                "holes": [_coords_to_points(ring, include_elevation=False) for ring in holes],
            }


def _iter_gpkg_waterways(conn: sqlite3.Connection, bbox: dict | None, from_cache: bool = False):
    if from_cache:
        query = f"""
            SELECT fid, osm_id, fclass, width, name, geom
            FROM waterways
            {_bbox_sql_where()}
        """
    else:
        query = """
            SELECT fid, osm_id, fclass, width, name, geom
            FROM gis_osm_waterways_free
        """
    for row in conn.execute(query, _bbox_params(bbox) if from_cache else ()):
        geometry = _decode_gpkg_geometry(row["geom"])
        if not geometry or geometry["type"] != "LineString":
            continue
        if not _bounds_intersect(geometry["bounds"], bbox):
            continue
        coordinates = _coords_to_points(geometry["coordinates"])
        kind = row["fclass"] or "water"
        yield {
            "id": f"gpkg-waterway-{row['fid']}",
            "source": "gpkg",
            "osmWayId": row["osm_id"],
            "kind": kind,
            "name": row["name"],
            "geometryType": "line",
            "lineWidthMeters": float(row["width"] or (8 if kind in {"river", "canal"} else 4)),
            "centerline": coordinates,
            "color": WATER_COLORS.get(kind, "#72b1e0"),
            "labelAnchor": _label_anchor(coordinates),
        }


def _decode_gpkg_geometry(blob: bytes | None) -> dict | None:
    if not blob or len(blob) < 8 or blob[0:2] != b"GP":
        return None

    flags = blob[3]
    envelope_code = (flags >> 1) & 0b111
    little_endian = (flags & 1) == 1
    endian = "<" if little_endian else ">"
    offset = 8

    bounds = None
    if envelope_code == 1:
        min_x, max_x, min_y, max_y = struct.unpack_from(f"{endian}4d", blob, offset)
        bounds = {"west": min_x, "south": min_y, "east": max_x, "north": max_y}
        offset += 32
    elif envelope_code == 2:
        min_x, max_x, min_y, max_y, _, _ = struct.unpack_from(f"{endian}6d", blob, offset)
        bounds = {"west": min_x, "south": min_y, "east": max_x, "north": max_y}
        offset += 48
    elif envelope_code in {3, 4}:
        values = struct.unpack_from(f"{endian}8d", blob, offset)
        bounds = {"west": values[0], "south": values[2], "east": values[1], "north": values[3]}
        offset += 64

    geometry, _ = _parse_wkb(blob, offset)
    geometry["bounds"] = bounds or _bounds_from_geometry(geometry)
    return geometry


def _parse_wkb(blob: bytes, offset: int) -> tuple[dict, int]:
    byte_order = blob[offset]
    endian = "<" if byte_order == 1 else ">"
    geom_type = struct.unpack_from(f"{endian}I", blob, offset + 1)[0]
    cursor = offset + 5

    if geom_type == 2:
        count = struct.unpack_from(f"{endian}I", blob, cursor)[0]
        cursor += 4
        coordinates = []
        for _ in range(count):
            x, y = struct.unpack_from(f"{endian}2d", blob, cursor)
            cursor += 16
            coordinates.append((x, y))
        return {"type": "LineString", "coordinates": coordinates}, cursor

    if geom_type == 3:
        ring_count = struct.unpack_from(f"{endian}I", blob, cursor)[0]
        cursor += 4
        rings = []
        for _ in range(ring_count):
            point_count = struct.unpack_from(f"{endian}I", blob, cursor)[0]
            cursor += 4
            ring = []
            for _ in range(point_count):
                x, y = struct.unpack_from(f"{endian}2d", blob, cursor)
                cursor += 16
                ring.append((x, y))
            rings.append(ring)
        return {"type": "Polygon", "coordinates": rings}, cursor

    if geom_type == 5:
        line_count = struct.unpack_from(f"{endian}I", blob, cursor)[0]
        cursor += 4
        coordinates = []
        for _ in range(line_count):
            line, cursor = _parse_wkb(blob, cursor)
            coordinates.extend(line["coordinates"])
        return {"type": "LineString", "coordinates": coordinates}, cursor

    if geom_type == 6:
        polygon_count = struct.unpack_from(f"{endian}I", blob, cursor)[0]
        cursor += 4
        polygons = []
        for _ in range(polygon_count):
            polygon, cursor = _parse_wkb(blob, cursor)
            polygons.append(polygon["coordinates"])
        return {"type": "MultiPolygon", "coordinates": polygons}, cursor

    return {"type": "Unknown", "coordinates": []}, len(blob)


def _bounds_from_geometry(geometry: dict) -> dict | None:
    points = []
    if geometry["type"] == "LineString":
        points = geometry["coordinates"]
    elif geometry["type"] == "Polygon":
        for ring in geometry["coordinates"]:
            points.extend(ring)
    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            for ring in polygon:
                points.extend(ring)

    if not points:
        return None

    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {"west": min(xs), "south": min(ys), "east": max(xs), "north": max(ys)}


def _geometry_polygons(geometry: dict) -> list[tuple[list[tuple[float, float]], list[list[tuple[float, float]]]]]:
    if geometry["type"] == "Polygon":
        rings = geometry["coordinates"]
        return [(rings[0], rings[1:])] if rings else []
    if geometry["type"] == "MultiPolygon":
        polygons = []
        for polygon in geometry["coordinates"]:
            if polygon:
                polygons.append((polygon[0], polygon[1:]))
        return polygons
    return []


def _coords_to_points(coordinates: list[tuple[float, float]], include_elevation: bool = True) -> list[dict]:
    points = []
    for longitude, latitude in coordinates:
        point = {"longitude": round(longitude, 7), "latitude": round(latitude, 7)}
        if include_elevation:
            point["elevation"] = 0
        points.append(point)
    if points and points[0] == points[-1]:
        return points[:-1]
    return points


def _bounds_intersect(bounds: dict | None, bbox: dict | None) -> bool:
    if not bounds or not bbox:
        return True
    return not (
        bounds["east"] < bbox["west"]
        or bounds["west"] > bbox["east"]
        or bounds["north"] < bbox["south"]
        or bounds["south"] > bbox["north"]
    )


def parse_dem_json(dem_path: str | Path) -> dict:
    dem_file = Path(dem_path)
    data = json.loads(dem_file.read_text(encoding="utf-8"))
    return {
        "bounds": data["bounds"],
        "width": int(data["width"]),
        "height": int(data["height"]),
        "elevations": data["elevations"],
        "units": data.get("units", "meters"),
        "sourceFormat": "json-grid",
    }


def parse_dem_ascii_grid(dem_path: str | Path) -> dict:
    dem_file = Path(dem_path)
    lines = [line.strip() for line in dem_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    header = {}
    data_start = 0

    for index, line in enumerate(lines):
        parts = line.split()
        if len(parts) != 2:
            data_start = index
            break
        key = parts[0].lower()
        if key not in {"ncols", "nrows", "xllcorner", "yllcorner", "cellsize", "nodata_value"}:
            data_start = index
            break
        header[key] = float(parts[1])
        data_start = index + 1

    required = {"ncols", "nrows", "xllcorner", "yllcorner", "cellsize"}
    if not required.issubset(header):
        raise ValueError(f"Invalid ASCII grid header in {dem_file}")

    width = int(header["ncols"])
    height = int(header["nrows"])
    west = header["xllcorner"]
    south = header["yllcorner"]
    cellsize = header["cellsize"]
    nodata = header.get("nodata_value", -9999)

    rows = []
    for line in lines[data_start:]:
        values = [float(value) for value in line.split()]
        if values:
            rows.append([0 if value == nodata else value for value in values])

    if len(rows) != height:
        raise ValueError(f"ASCII grid row count mismatch in {dem_file}")

    return {
        "bounds": {
            "west": west,
            "south": south,
            "east": west + (width * cellsize),
            "north": south + (height * cellsize),
        },
        "width": width,
        "height": height,
        "elevations": rows,
        "units": "meters",
        "sourceFormat": "ascii-grid",
    }


def parse_dem_geotiff(dem_path: str | Path) -> dict:
    dem_file = Path(dem_path)
    with tifffile.TiffFile(dem_file) as tif:
        page = tif.pages[0]
        elevations = page.asarray().astype(numpy.float32)
        pixel_scale = page.tags.get("ModelPixelScaleTag")
        tiepoint = page.tags.get("ModelTiepointTag")
        nodata = page.tags.get("GDAL_NODATA") or page.tags.get(42113)

        if pixel_scale is None or tiepoint is None:
            raise ValueError(f"GeoTIFF is missing georeference tags: {dem_file}")

        scale_x = float(pixel_scale.value[0])
        scale_y = float(pixel_scale.value[1])
        tie = tiepoint.value
        west = float(tie[3])
        north = float(tie[4])
        height, width = elevations.shape
        east = west + (scale_x * (width - 1))
        south = north - (scale_y * (height - 1))

        nodata_value = None if nodata is None else float(nodata.value if hasattr(nodata, "value") else nodata)
        if nodata_value is not None:
            elevations[elevations == nodata_value] = 0

    return {
        "bounds": {
            "west": west,
            "south": south,
            "east": east,
            "north": north,
        },
        "width": width,
        "height": height,
        "elevations": elevations,
        "units": "meters",
        "sourceFormat": "geotiff",
        "cellSizeX": scale_x,
        "cellSizeY": scale_y,
    }


def _merge_dem_tiles(dems: list[dict]) -> dict:
    if not dems:
        raise ValueError("No DEM tiles to merge")
    if len(dems) == 1:
        return dems[0]

    west = min(item["bounds"]["west"] for item in dems)
    south = min(item["bounds"]["south"] for item in dems)
    east = max(item["bounds"]["east"] for item in dems)
    north = max(item["bounds"]["north"] for item in dems)
    cell_size_x = min(
        item.get("cellSizeX") or ((item["bounds"]["east"] - item["bounds"]["west"]) / max(item["width"] - 1, 1))
        for item in dems
    )
    cell_size_y = min(
        item.get("cellSizeY") or ((item["bounds"]["north"] - item["bounds"]["south"]) / max(item["height"] - 1, 1))
        for item in dems
    )

    width = int(round((east - west) / cell_size_x)) + 1
    height = int(round((north - south) / cell_size_y)) + 1
    merged = numpy.zeros((height, width), dtype=numpy.float32)

    for dem in dems:
        tile = numpy.asarray(dem["elevations"], dtype=numpy.float32)
        row_offset = int(round((north - dem["bounds"]["north"]) / cell_size_y))
        col_offset = int(round((dem["bounds"]["west"] - west) / cell_size_x))
        tile_height, tile_width = tile.shape
        merged[row_offset : row_offset + tile_height, col_offset : col_offset + tile_width] = tile

    return {
        "bounds": {
            "west": west,
            "south": south,
            "east": east,
            "north": north,
        },
        "width": width,
        "height": height,
        "elevations": merged,
        "units": "meters",
        "sourceFormat": "merged-geotiff",
        "cellSizeX": cell_size_x,
        "cellSizeY": cell_size_y,
    }


def _empty_osm_features() -> dict:
    return {
        "roads": [],
        "railways": [],
        "buildings": [],
        "landuse": [],
        "water": [],
        "powerlines": [],
        "bounds": None,
    }


def _road_from_osm_way(way_id: str, coordinates: list[dict], tags: dict) -> dict | None:
    if "highway" not in tags or len(coordinates) < 2:
        return None
    highway_type = tags.get("highway", "unclassified")
    return {
        "id": f"osm-road-{way_id}",
        "source": "osm",
        "osmWayId": way_id,
        "kind": highway_type,
        "rank": ROAD_RANKS.get(highway_type, 99),
        "name": tags.get("name") or tags.get("ref"),
        "surface": tags.get("surface"),
        "lanes": tags.get("lanes"),
        "widthMeters": ROAD_WIDTHS.get(highway_type, 9),
        "centerline": [_point_record(point) for point in coordinates],
        "labelAnchor": _label_anchor(coordinates),
    }


def _railway_from_osm_way(way_id: str, coordinates: list[dict], tags: dict) -> dict | None:
    railway_type = tags.get("railway")
    if not railway_type or len(coordinates) < 2:
        return None
    return {
        "id": f"osm-railway-{way_id}",
        "source": "osm",
        "osmWayId": way_id,
        "kind": railway_type,
        "name": tags.get("name") or tags.get("ref"),
        "gauge": tags.get("gauge"),
        "widthMeters": RAIL_WIDTHS.get(railway_type, 4.8),
        "centerline": [_point_record(point) for point in coordinates],
        "labelAnchor": _label_anchor(coordinates),
    }


def _building_from_osm_way(way_id: str, coordinates: list[dict], tags: dict) -> dict | None:
    if "building" not in tags:
        return None
    ring = _closed_ring(coordinates)
    if len(ring) < 4:
        return None

    building_kind = tags.get("building", "yes")
    levels = _safe_float(tags.get("building:levels"))
    height = _safe_float(tags.get("height")) or (levels * 3.4 if levels else _building_style(building_kind)["height"])
    if height <= 0:
        height = _building_style(building_kind)["height"]

    building_style = _building_style(building_kind)

    return {
        "id": f"osm-building-{way_id}",
        "source": "osm",
        "osmWayId": way_id,
        "kind": building_kind,
        "name": tags.get("name"),
        "heightMeters": round(height, 2),
        "levels": levels,
        "roofColor": building_style["roof"],
        "wallColor": building_style["wall"],
        "footprint": [_point_record(point, include_elevation=False) for point in ring[:-1]],
        "holes": [],
    }


def _landuse_from_osm_way(way_id: str, coordinates: list[dict], tags: dict) -> dict | None:
    kind = tags.get("landuse") or tags.get("leisure")
    if not kind:
        return None
    return _polygon_feature_from_way(
        way_id,
        coordinates,
        tags,
        feature_type="landuse",
        default_kind=kind,
        color=LANDUSE_COLORS.get(kind, "#a7bd8e"),
        min_height=0.4,
    )


def _water_from_osm_way(way_id: str, coordinates: list[dict], tags: dict) -> dict | None:
    kind = _water_kind(tags)
    if not kind:
        return None

    if "waterway" in tags and not _is_closed_way(coordinates):
        return {
            "id": f"osm-water-{way_id}",
            "source": "osm",
            "osmWayId": way_id,
            "kind": kind,
            "name": tags.get("name"),
            "geometryType": "line",
            "lineWidthMeters": 8 if tags.get("waterway") in {"river", "canal"} else 4,
            "centerline": [_point_record(point) for point in coordinates],
            "color": WATER_COLORS.get(kind, "#72b1e0"),
            "labelAnchor": _label_anchor(coordinates),
        }

    return _polygon_feature_from_way(
        way_id,
        coordinates,
        tags,
        feature_type="water",
        default_kind=kind,
        color=WATER_COLORS.get(kind, "#72b1e0"),
        min_height=0.08,
    )


def _landuse_from_relation(relation: ET.Element, way_geometries: dict, tags: dict) -> dict | None:
    kind = tags.get("landuse") or tags.get("leisure")
    if not kind:
        return None
    return _polygon_feature_from_relation(
        relation,
        way_geometries,
        tags,
        feature_type="landuse",
        default_kind=kind,
        color=LANDUSE_COLORS.get(kind, "#a7bd8e"),
        min_height=0.4,
    )


def _water_from_relation(relation: ET.Element, way_geometries: dict, tags: dict) -> dict | None:
    kind = _water_kind(tags)
    if not kind:
        return None
    return _polygon_feature_from_relation(
        relation,
        way_geometries,
        tags,
        feature_type="water",
        default_kind=kind,
        color=WATER_COLORS.get(kind, "#72b1e0"),
        min_height=0.08,
    )


def _polygon_feature_from_way(
    way_id: str,
    coordinates: list[dict],
    tags: dict,
    *,
    feature_type: str,
    default_kind: str,
    color: str,
    min_height: float = 0.0,
) -> dict | None:
    ring = _closed_ring(coordinates)
    if len(ring) < 4:
        return None
    return {
        "id": f"osm-{feature_type}-{way_id}",
        "source": "osm",
        "osmWayId": way_id,
        "kind": default_kind,
        "name": tags.get("name"),
        "geometryType": "polygon",
        "heightMeters": min_height,
        "color": color,
        "footprint": [_point_record(point, include_elevation=False) for point in ring[:-1]],
        "holes": [],
    }


def _polygon_feature_from_relation(
    relation: ET.Element,
    way_geometries: dict,
    tags: dict,
    *,
    feature_type: str,
    default_kind: str,
    color: str,
    min_height: float = 0.0,
) -> dict | None:
    relation_id = relation.attrib["id"]
    outer_segments = []
    inner_segments = []

    for member in relation.findall("member"):
        if member.attrib.get("type") != "way":
            continue
        ref = member.attrib.get("ref")
        if ref not in way_geometries:
            continue
        coords = way_geometries[ref]["coords"]
        role = member.attrib.get("role", "outer")
        if role == "inner":
            inner_segments.append(coords)
        else:
            outer_segments.append(coords)

    outer_ring = _merge_ring_segments(outer_segments)
    if len(outer_ring) < 4:
        return None

    holes = []
    for inner in inner_segments:
        ring = _merge_ring_segments([inner])
        if len(ring) >= 4:
            holes.append([_point_record(point, include_elevation=False) for point in ring[:-1]])

    feature = {
        "id": f"osm-{feature_type}-relation-{relation_id}",
        "source": "osm",
        "osmRelationId": relation_id,
        "kind": default_kind,
        "name": tags.get("name"),
        "geometryType": "polygon",
        "heightMeters": min_height,
        "color": color,
        "footprint": [_point_record(point, include_elevation=False) for point in outer_ring[:-1]],
        "holes": holes,
    }
    if feature_type == "building":
        levels = _safe_float(tags.get("building:levels"))
        height = _safe_float(tags.get("height")) or (levels * 3.4 if levels else 14)
        feature["heightMeters"] = round(height, 2)
        feature["levels"] = levels
    return feature


def _powerline_from_osm_way(way_id: str, coordinates: list[dict], tags: dict, power_nodes: dict) -> dict | None:
    if tags.get("power") not in {"line", "minor_line"} or len(coordinates) < 2:
        return None

    towers = []
    for point in coordinates:
        if point["id"] in power_nodes:
            towers.append(
                {
                    "id": f"tower-{point['id']}",
                    "longitude": round(point["longitude"], 7),
                    "latitude": round(point["latitude"], 7),
                    "elevation": 0,
                    "heightMeters": 42 if point["tags"].get("power") == "tower" else 18,
                }
            )

    if len(towers) < 2:
        towers = [
            {
                "id": f"tower-{way_id}-{index}",
                "longitude": round(point["longitude"], 7),
                "latitude": round(point["latitude"], 7),
                "elevation": 0,
                "heightMeters": 38,
            }
            for index, point in enumerate((coordinates[0], coordinates[-1]), start=1)
        ]

    return {
        "id": f"osm-powerline-{way_id}",
        "source": "osm",
        "osmWayId": way_id,
        "kind": tags.get("power"),
        "name": tags.get("name"),
        "voltageClass": tags.get("voltage", "unknown"),
        "assetRef": "power_tower_lattice_a",
        "towers": towers,
        "wires": [
            {
                "id": f"wire-{way_id}-1",
                "points": [
                    {
                        "longitude": round(point["longitude"], 7),
                        "latitude": round(point["latitude"], 7),
                        "elevation": 32,
                    }
                    for point in coordinates
                ],
            }
        ],
    }


def _label_anchor(coordinates: list[dict]) -> dict | None:
    if len(coordinates) < 2:
        return None
    mid = len(coordinates) // 2
    prev_point = coordinates[max(0, mid - 1)]
    next_point = coordinates[min(len(coordinates) - 1, mid)]
    angle = math.degrees(
        math.atan2(
            next_point["latitude"] - prev_point["latitude"],
            next_point["longitude"] - prev_point["longitude"],
        )
    )
    return {
        "longitude": round(next_point["longitude"], 7),
        "latitude": round(next_point["latitude"], 7),
        "angleDegrees": round(angle, 3),
    }


def _building_style(kind: str | None) -> dict:
    normalized = (kind or "building").lower()
    if normalized in BUILDING_KIND_STYLES:
        return BUILDING_KIND_STYLES[normalized]

    if any(token in normalized for token in ("school", "college", "university")):
        return BUILDING_KIND_STYLES["school"]
    if any(token in normalized for token in ("hospital", "clinic", "medical")):
        return BUILDING_KIND_STYLES["hospital"]
    if any(token in normalized for token in ("office", "government", "public")):
        return BUILDING_KIND_STYLES["office"]
    if any(token in normalized for token in ("warehouse", "depot", "factory", "industrial")):
        return BUILDING_KIND_STYLES["industrial"]
    if any(token in normalized for token in ("shop", "retail", "mall", "supermarket")):
        return BUILDING_KIND_STYLES["retail"]
    if any(token in normalized for token in ("apartment", "apartments")):
        return BUILDING_KIND_STYLES["apartments"]
    if any(token in normalized for token in ("house", "residential", "detached")):
        return BUILDING_KIND_STYLES["residential"]

    return BUILDING_KIND_STYLES["building"]


def _water_kind(tags: dict) -> str | None:
    return (
        tags.get("water")
        or tags.get("waterway")
        or ("water" if tags.get("natural") == "water" else None)
        or ("reservoir" if tags.get("landuse") in {"reservoir", "basin"} else None)
    )


def _is_closed_way(points: list[dict]) -> bool:
    return bool(points) and points[0]["id"] == points[-1]["id"]


def _closed_ring(points: list[dict]) -> list[dict]:
    if not points:
        return []
    if _is_closed_way(points):
        return points
    return [*points, points[0]]


def _merge_ring_segments(segments: list[list[dict]]) -> list[dict]:
    if not segments:
        return []

    merged = list(segments[0])
    remaining = [list(segment) for segment in segments[1:]]

    while remaining:
        last_id = merged[-1]["id"]
        matched_index = None
        matched_segment = None

        for index, segment in enumerate(remaining):
            if segment[0]["id"] == last_id:
                matched_index = index
                matched_segment = segment[1:]
                break
            if segment[-1]["id"] == last_id:
                matched_index = index
                matched_segment = list(reversed(segment[:-1]))
                break

        if matched_index is None:
            break

        merged.extend(matched_segment)
        remaining.pop(matched_index)

    return _closed_ring(merged)


def _bounds_from_features(
    *,
    roads: list[dict],
    railways: list[dict],
    buildings: list[dict],
    landuse: list[dict],
    water: list[dict],
    powerlines: list[dict],
) -> dict | None:
    longitudes = []
    latitudes = []

    def append_points(points: list[dict]) -> None:
        for point in points:
            longitudes.append(point["longitude"])
            latitudes.append(point["latitude"])

    for road in roads:
        append_points(road["centerline"])

    for railway in railways:
        append_points(railway["centerline"])

    for polygon_group in (buildings, landuse, water):
        for feature in polygon_group:
            if feature.get("geometryType") == "line":
                append_points(feature["centerline"])
                continue
            append_points(feature["footprint"])
            for hole in feature.get("holes", []):
                append_points(hole)

    for powerline in powerlines:
        append_points(powerline["towers"])
        for wire in powerline["wires"]:
            append_points(wire["points"])

    if not longitudes or not latitudes:
        return None

    return {
        "west": min(longitudes),
        "south": min(latitudes),
        "east": max(longitudes),
        "north": max(latitudes),
    }


def _load_crossings(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
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
            c.barrier_type,
            c.crossing_type,
            c.manager_name,
            COALESCE(r.score, 0) AS risk_score,
            COALESCE(r.level, 'unknown') AS risk_level
        FROM crossings c
        LEFT JOIN (
            SELECT rs.*
            FROM risk_snapshots rs
            JOIN (
                SELECT crossing_id, MAX(id) AS latest_id
                FROM risk_snapshots
                GROUP BY crossing_id
            ) latest ON latest.latest_id = rs.id
        ) r ON r.crossing_id = c.id
        WHERE c.latitude IS NOT NULL AND c.longitude IS NOT NULL
        ORDER BY c.id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def _build_manifest(
    crossings: list[dict], osm_features: dict, dem: dict | None, tile_size_degrees: float
) -> tuple[dict, dict[str, dict]]:
    bounds = _merge_bounds(_bounds_from_crossings(crossings), osm_features.get("bounds"), dem["bounds"] if dem else None)
    generated_at = datetime.now(timezone.utc).isoformat()
    source_stats = _source_stats(crossings, osm_features)

    if not bounds:
        return (
            {
                "version": 4,
                "generatedAt": generated_at,
                "sceneHash": _scene_hash(tile_size_degrees, bounds=None, source_stats=source_stats, dem=dem),
                "coordinateSystem": "EPSG:4326",
                "tileSizeDegrees": tile_size_degrees,
                "bounds": None,
                "center": None,
                "terrain": None,
                "stats": source_stats,
                "assetCatalog": _asset_catalog(),
                "sources": _source_flags(crossings, osm_features, dem),
                "tiles": [],
            },
            {},
        )

    buckets = _bucketize_features(crossings, osm_features, tile_size_degrees)
    tiles = []

    for tile_id, bucket in sorted(buckets.items()):
        tile_x, tile_y = [int(part) for part in tile_id.split("_")[1:]]
        west = tile_x * tile_size_degrees
        south = tile_y * tile_size_degrees
        east = west + tile_size_degrees
        north = south + tile_size_degrees

        counts = TileFeatureCounts(
            crossings=len(bucket["crossings"]),
            roads=len(bucket["roads"]),
            railways=len(bucket["railways"]),
            buildings=len(bucket["buildings"]),
            landuse=len(bucket["landuse"]),
            water=len(bucket["water"]),
            powerlines=len(bucket["powerlines"]),
            landmarks=len(bucket["landmarks"]),
        )
        tiles.append(
            {
                "id": tile_id,
                "url": f"tiles/{tile_id}.json",
                "bounds": {"west": west, "south": south, "east": east, "north": north},
                "center": {
                    "longitude": round((west + east) / 2, 6),
                    "latitude": round((south + north) / 2, 6),
                },
                "featureCounts": asdict(counts),
            }
        )

    return (
        {
            "version": 4,
            "generatedAt": generated_at,
            "sceneHash": _scene_hash(tile_size_degrees, bounds=bounds, source_stats=source_stats, dem=dem),
            "coordinateSystem": "EPSG:4326",
            "tileSizeDegrees": tile_size_degrees,
            "bounds": bounds,
            "center": {
                "longitude": round((bounds["west"] + bounds["east"]) / 2, 6),
                "latitude": round((bounds["south"] + bounds["north"]) / 2, 6),
            },
            "stats": source_stats,
            "terrain": {
                "available": bool(dem),
                "bounds": dem["bounds"] if dem else None,
                "width": dem["width"] if dem else 0,
                "height": dem["height"] if dem else 0,
                "sourceFormat": dem["sourceFormat"] if dem else None,
            },
            "assetCatalog": _asset_catalog(),
            "sources": _source_flags(crossings, osm_features, dem),
            "tiles": tiles,
        },
        buckets,
    )


def _source_flags(crossings: list[dict], osm_features: dict, dem: dict | None) -> dict:
    return {
        "crossings": bool(crossings),
        "osmRoads": bool(osm_features.get("roads")),
        "osmRailways": bool(osm_features.get("railways")),
        "osmBuildings": bool(osm_features.get("buildings")),
        "osmLanduse": bool(osm_features.get("landuse")),
        "osmWater": bool(osm_features.get("water")),
        "osmPowerlines": bool(osm_features.get("powerlines")),
        "dem": bool(dem),
    }


def _source_stats(crossings: list[dict], osm_features: dict) -> dict:
    return {
        "crossings": len(crossings),
        "roads": len(osm_features.get("roads", [])),
        "railways": len(osm_features.get("railways", [])),
        "buildings": len(osm_features.get("buildings", [])),
        "landuse": len(osm_features.get("landuse", [])),
        "water": len(osm_features.get("water", [])),
        "powerlines": len(osm_features.get("powerlines", [])),
    }


def _scene_hash(tile_size_degrees: float, *, bounds: dict | None, source_stats: dict, dem: dict | None) -> str:
    payload = {
        "tileSizeDegrees": tile_size_degrees,
        "bounds": bounds,
        "stats": source_stats,
        "terrain": {
            "available": bool(dem),
            "bounds": dem["bounds"] if dem else None,
            "width": dem["width"] if dem else 0,
            "height": dem["height"] if dem else 0,
            "sourceFormat": dem["sourceFormat"] if dem else None,
        },
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:16]


def _bucketize_features(crossings: list[dict], osm_features: dict, tile_size_degrees: float) -> dict[str, dict]:
    buckets: dict[str, dict] = {}

    def ensure_bucket(tile_id: str) -> dict:
        if tile_id not in buckets:
            buckets[tile_id] = {
                "crossings": [],
                "roads": [],
                "railways": [],
                "buildings": [],
                "landuse": [],
                "water": [],
                "powerlines": [],
                "landmarks": [],
            }
        return buckets[tile_id]

    def bucket_linear(features: list[dict], key: str, point_getter) -> None:
        for feature in features:
            for tile_id in _tile_ids_for_points(point_getter(feature), tile_size_degrees):
                ensure_bucket(tile_id)[key].append(feature)

    for crossing in crossings:
        tile_id = _tile_id(crossing["longitude"], crossing["latitude"], tile_size_degrees)
        bucket = ensure_bucket(tile_id)
        bucket["crossings"].append(crossing)
        if crossing["risk_level"] == "very_high":
            bucket["landmarks"].append(_landmark_for_crossing(crossing))

    bucket_linear(osm_features.get("roads", []), "roads", lambda feature: feature["centerline"])
    bucket_linear(osm_features.get("railways", []), "railways", lambda feature: feature["centerline"])

    for key in ("buildings", "landuse", "water"):
        for feature in osm_features.get(key, []):
            points = _feature_points(feature)
            for tile_id in _tile_ids_for_points(points, tile_size_degrees):
                ensure_bucket(tile_id)[key].append(feature)

    for powerline in osm_features.get("powerlines", []):
        points = [*powerline["towers"]]
        for wire in powerline["wires"]:
            points.extend(wire["points"])
        for tile_id in _tile_ids_for_points(points, tile_size_degrees):
            ensure_bucket(tile_id)["powerlines"].append(powerline)

    return buckets


def _build_tile_payload(tile: dict, bucket: dict, dem: dict | None) -> dict:
    bounds = tile["bounds"]
    tile_crossings = bucket.get("crossings", [])
    tile_roads = bucket.get("roads", [])
    tile_railways = bucket.get("railways", [])
    tile_buildings = bucket.get("buildings", [])
    tile_landuse = bucket.get("landuse", [])
    tile_water = bucket.get("water", [])
    tile_powerlines = bucket.get("powerlines", [])
    tile_landmarks = bucket.get("landmarks", [])

    return {
        "version": 4,
        "tile": {"id": tile["id"], "bounds": bounds},
        "terrain": _terrain_patch_for_bounds(dem, bounds),
        "crossings": [
            {
                "id": item["id"],
                "code": item["code"],
                "name": item["name"],
                "longitude": item["longitude"],
                "latitude": item["latitude"],
                "riskLevel": item["risk_level"],
                "riskScore": item["risk_score"],
                "barrierType": item["barrier_type"],
                "crossingType": item["crossing_type"],
                "label": item["name"],
            }
            for item in tile_crossings
        ],
        "roads": tile_roads,
        "railways": tile_railways,
        "buildings": tile_buildings,
        "landuse": tile_landuse,
        "water": tile_water,
        "powerlines": tile_powerlines,
        "landmarks": tile_landmarks,
    }


def _terrain_patch_for_bounds(dem: dict | None, bounds: dict) -> dict | None:
    if not dem:
        return None

    west = dem["bounds"]["west"]
    south = dem["bounds"]["south"]
    east = dem["bounds"]["east"]
    north = dem["bounds"]["north"]
    width = dem["width"]
    height = dem["height"]

    if width < 2 or height < 2:
        return dem

    def clamp_index(value: float, start: float, end: float, size: int) -> int:
        ratio = (value - start) / (end - start or 1)
        return max(0, min(size - 1, round(ratio * (size - 1))))

    west_idx = clamp_index(bounds["west"], west, east, width)
    east_idx = clamp_index(bounds["east"], west, east, width)
    south_idx = clamp_index(bounds["south"], south, north, height)
    north_idx = clamp_index(bounds["north"], south, north, height)

    row_start = max(0, min(height - 1, height - 1 - north_idx))
    row_end = max(0, min(height - 1, height - 1 - south_idx))
    col_start = min(west_idx, east_idx)
    col_end = max(west_idx, east_idx)

    if row_end <= row_start:
        row_end = min(height - 1, row_start + 1)
    if col_end <= col_start:
        col_end = min(width - 1, col_start + 1)

    if hasattr(dem["elevations"], "__getitem__") and hasattr(dem["elevations"], "shape"):
        raw_elevations = dem["elevations"][row_start : row_end + 1, col_start : col_end + 1]
        elevations = raw_elevations.tolist()
    else:
        elevations = [row[col_start : col_end + 1] for row in dem["elevations"][row_start : row_end + 1]]
    patch_west = west + ((east - west) * (col_start / (width - 1)))
    patch_east = west + ((east - west) * (col_end / (width - 1)))
    north_ratio = 1 - (row_start / (height - 1))
    south_ratio = 1 - (row_end / (height - 1))
    patch_north = south + ((north - south) * north_ratio)
    patch_south = south + ((north - south) * south_ratio)

    return {
        "bounds": {
            "west": patch_west,
            "south": patch_south,
            "east": patch_east,
            "north": patch_north,
        },
        "width": len(elevations[0]) if elevations else 0,
        "height": len(elevations),
        "elevations": elevations,
        "units": dem["units"],
        "sourceFormat": dem["sourceFormat"],
    }


def _bounds_from_crossings(crossings: list[dict]) -> dict | None:
    if not crossings:
        return None
    lats = [item["latitude"] for item in crossings]
    lngs = [item["longitude"] for item in crossings]
    return {
        "west": min(lngs),
        "south": min(lats),
        "east": max(lngs),
        "north": max(lats),
    }


def _expand_bounds(bounds: dict | None, margin: float) -> dict | None:
    if not bounds:
        return None
    return {
        "west": bounds["west"] - margin,
        "south": bounds["south"] - margin,
        "east": bounds["east"] + margin,
        "north": bounds["north"] + margin,
    }


def _merge_bounds(*bounds_list: dict | None) -> dict | None:
    valid = [bounds for bounds in bounds_list if bounds]
    if not valid:
        return None
    return {
        "west": min(bounds["west"] for bounds in valid),
        "south": min(bounds["south"] for bounds in valid),
        "east": max(bounds["east"] for bounds in valid),
        "north": max(bounds["north"] for bounds in valid),
    }


def _tile_id(longitude: float, latitude: float, tile_size_degrees: float) -> str:
    tile_x = math.floor(longitude / tile_size_degrees)
    tile_y = math.floor(latitude / tile_size_degrees)
    return f"z0_{tile_x}_{tile_y}"


def _tile_ids_for_points(points: list[dict], tile_size_degrees: float) -> set[str]:
    return {_tile_id(point["longitude"], point["latitude"], tile_size_degrees) for point in points}


def _feature_intersects_bounds(points: list[dict], bounds: dict) -> bool:
    return any(
        bounds["south"] <= point["latitude"] < bounds["north"]
        and bounds["west"] <= point["longitude"] < bounds["east"]
        for point in points
    )


def _feature_points(feature: dict) -> list[dict]:
    if feature.get("geometryType") == "line":
        return list(feature["centerline"])
    points = [*feature["footprint"]]
    for hole in feature.get("holes", []):
        points.extend(hole)
    return points


def _landmark_for_crossing(crossing: dict) -> dict:
    return {
        "id": f"landmark-{crossing['id']}",
        "kind": "risk_crossing_beacon",
        "assetRef": "crossing_warning_beacon",
        "longitude": crossing["longitude"],
        "latitude": crossing["latitude"],
        "elevation": 0,
        "scale": 1.0,
    }


def _asset_catalog() -> list[dict]:
    return [
        {
            "id": "power_tower_lattice_a",
            "category": "power",
            "modelPath": "assets/power_tower_lattice_a.glb",
            "lod": {"near": 0, "mid": 400, "far": 1200},
        },
        {
            "id": "crossing_warning_beacon",
            "category": "rail",
            "modelPath": "assets/crossing_warning_beacon.glb",
            "lod": {"near": 0, "mid": 200, "far": 600},
        },
    ]


def _point_record(point: dict, include_elevation: bool = True) -> dict:
    data = {
        "longitude": round(point["longitude"], 7),
        "latitude": round(point["latitude"], 7),
    }
    if include_elevation:
        data["elevation"] = 0
    return data


def _safe_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None
