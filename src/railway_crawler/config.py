from __future__ import annotations

from pathlib import Path
import tomllib


DEFAULT_CONFIG = {
    "area": {"city": "Biên Hòa", "province": "Đồng Nai"},
    "news": {
        "language": "vi",
        "country": "VN",
        "edition": "VN:vi",
        "days_back": 365,
        "queries": [
            "Biên Hòa đường sắt tai nạn",
            "Đồng Nai đường sắt tai nạn",
            "Biên Hòa đường ngang đường sắt",
            "Đồng Nai tàu hỏa va chạm",
        ],
    },
    "schedules": {
        "source_url": "https://giotaugiave.dsvn.vn/",
        "stations": ["Biên Hòa", "Dĩ An", "Long Khánh", "Sài Gòn"],
    },
    "matching": {
        "crossing_keywords": ["đường ngang", "lối đi tự mở", "gác chắn", "tàu hỏa", "đường sắt"],
        "severe_keywords": ["tử vong", "nghiêm trọng", "va chạm", "tai nạn", "lật xe"],
    },
}


def load_config(config_path: str | None) -> dict:
    if not config_path:
        return DEFAULT_CONFIG

    path = Path(config_path)
    with path.open("rb") as handle:
        loaded = tomllib.load(handle)

    return deep_merge(DEFAULT_CONFIG, loaded)


def deep_merge(base: dict, override: dict) -> dict:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
