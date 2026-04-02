from __future__ import annotations

import argparse
from pathlib import Path
import sys
import warnings

warnings.simplefilter("ignore")

from requests import RequestsDependencyWarning

from railway_crawler.config import load_config
from railway_crawler.db import connect, import_crossings_csv, init_db
from railway_crawler.news import fetch_and_store_news
from railway_crawler.risk import compute_risk, export_top_risks
from railway_crawler.schedule import fetch_and_store_schedules
from railway_crawler.seed import seed_fake_data
from railway_crawler.scene3d import export_scene_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Railway risk crawler for Bien Hoa.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db_parser = subparsers.add_parser("init-db", help="Create SQLite schema.")
    init_db_parser.add_argument("--db", required=True, help="Path to SQLite database.")

    import_parser = subparsers.add_parser("import-crossings", help="Import crossings from CSV.")
    import_parser.add_argument("--db", required=True)
    import_parser.add_argument("--csv", required=True)

    schedule_parser = subparsers.add_parser("fetch-schedules", help="Fetch official train schedules.")
    schedule_parser.add_argument("--db", required=True)
    schedule_parser.add_argument("--config", default=None)

    news_parser = subparsers.add_parser("fetch-news", help="Fetch related railway news.")
    news_parser.add_argument("--db", required=True)
    news_parser.add_argument("--config", default=None)

    risk_parser = subparsers.add_parser("compute-risk", help="Compute crossing risk snapshots.")
    risk_parser.add_argument("--db", required=True)

    refresh_parser = subparsers.add_parser("refresh-all", help="Run init, import, crawl, and score.")
    refresh_parser.add_argument("--db", required=True)
    refresh_parser.add_argument("--config", default=None)
    refresh_parser.add_argument("--csv", default=str(Path("data") / "crossings_template.csv"))

    export_parser = subparsers.add_parser("export-risk", help="Print top current risk rankings.")
    export_parser.add_argument("--db", required=True)
    export_parser.add_argument("--limit", type=int, default=10)

    seed_parser = subparsers.add_parser("seed-fake", help="Seed fake data for UI preview.")
    seed_parser.add_argument("--db", required=True)
    seed_parser.add_argument("--no-reset", action="store_true", help="Append instead of clearing domain tables first.")

    scene3d_parser = subparsers.add_parser("export-scene3d", help="Export 3D scene manifest and tile payloads.")
    scene3d_parser.add_argument("--db", required=True)
    scene3d_parser.add_argument("--out", default=str(Path("generated") / "scene3d"))
    scene3d_parser.add_argument("--tile-size", type=float, default=0.01)
    scene3d_parser.add_argument("--osm", default=None, help="Optional .osm XML file for real OSM features.")
    scene3d_parser.add_argument("--gpkg", default=None, help="Optional .gpkg vector source for real OSM features.")
    scene3d_parser.add_argument(
        "--dem",
        nargs="+",
        default=None,
        help="Optional one or more DEM files (.json, .asc, .grd, .tif, .tiff).",
    )

    return parser


def main() -> None:
    _configure_runtime()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init-db":
        conn = connect(args.db)
        init_db(conn)
        print(f"Initialized database: {args.db}")
        return

    if args.command == "import-crossings":
        conn = connect(args.db)
        init_db(conn)
        count = import_crossings_csv(conn, args.csv)
        print(f"Imported {count} crossings from {args.csv}")
        return

    if args.command == "fetch-schedules":
        conn = connect(args.db)
        init_db(conn)
        config = load_config(args.config)
        count = fetch_and_store_schedules(conn, config)
        print(f"Stored {count} schedule rows")
        return

    if args.command == "fetch-news":
        conn = connect(args.db)
        init_db(conn)
        config = load_config(args.config)
        count = fetch_and_store_news(conn, config)
        print(f"Stored or updated {count} news rows")
        return

    if args.command == "compute-risk":
        conn = connect(args.db)
        init_db(conn)
        count = compute_risk(conn)
        print(f"Created {count} risk snapshots")
        return

    if args.command == "refresh-all":
        conn = connect(args.db)
        init_db(conn)
        config = load_config(args.config)
        imported = import_crossings_csv(conn, args.csv)
        schedules = fetch_and_store_schedules(conn, config)
        news = fetch_and_store_news(conn, config)
        risks = compute_risk(conn)
        print(
            "Refresh completed: "
            f"crossings={imported}, schedules={schedules}, news={news}, risks={risks}"
        )
        return

    if args.command == "export-risk":
        conn = connect(args.db)
        rows = export_top_risks(conn, args.limit)
        for row in rows:
            print(
                f"{row['code']:7} | {row['name'][:35]:35} | "
                f"{row['score']:3} | {row['level']:9} | {row['district']}, {row['city']}"
            )
        return

    if args.command == "seed-fake":
        conn = connect(args.db)
        init_db(conn)
        summary = seed_fake_data(conn, reset=not args.no_reset)
        print(
            "Seeded fake data: "
            f"crossings={summary['crossings']}, "
            f"schedules={summary['schedules']}, "
            f"articles={summary['articles']}, "
            f"incidents={summary['incidents']}, "
            f"risks={summary['risks']}"
        )
        return

    if args.command == "export-scene3d":
        conn = connect(args.db)
        summary = export_scene_bundle(
            conn,
            output_dir=args.out,
            tile_size_degrees=args.tile_size,
            osm_path=args.osm,
            gpkg_path=args.gpkg,
            dem_path=args.dem,
        )
        print(
            "Exported 3D scene: "
            f"tiles={summary['tiles']}, "
            f"crossings={summary['crossings']}, "
            f"roads={summary['roads']}, "
            f"railways={summary['railways']}, "
            f"buildings={summary['buildings']}, "
            f"landuse={summary['landuse']}, "
            f"water={summary['water']}, "
            f"powerlines={summary['powerlines']}, "
            f"terrain={summary['terrain']}, "
            f"manifest={summary['manifest']}"
        )
        return


def _configure_runtime() -> None:
    warnings.simplefilter("ignore", RequestsDependencyWarning)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


if __name__ == "__main__":
    main()
