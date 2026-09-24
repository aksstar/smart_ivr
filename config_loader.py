"""Centralized configuration loader for Smart IVR.

Reads GCP project, location, BigQuery table, and Vertex AI Search settings
from `config.json` (git-ignored) or environment variables so that no
project IDs or locations are hardcoded in source files.
"""

import json
import os
from typing import Any, Dict

_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def _load_config() -> Dict[str, Any]:
    cfg: Dict[str, Any] = {}
    if os.path.exists(_CONFIG_PATH):
        try:
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}

    for key, val in cfg.items():
        if val and not os.getenv(key):
            os.environ[key] = str(val)
    return cfg


_CFG = _load_config()

GOOGLE_CLOUD_PROJECT: str = os.getenv(
    "GOOGLE_CLOUD_PROJECT", _CFG.get("GOOGLE_CLOUD_PROJECT", "")
)
GOOGLE_CLOUD_PROJECT_NUMBER: str = os.getenv(
    "GOOGLE_CLOUD_PROJECT_NUMBER", _CFG.get("GOOGLE_CLOUD_PROJECT_NUMBER", GOOGLE_CLOUD_PROJECT)
)
GOOGLE_CLOUD_LOCATION: str = os.getenv(
    "GOOGLE_CLOUD_LOCATION", _CFG.get("GOOGLE_CLOUD_LOCATION", "")
)
GOOGLE_GENAI_USE_VERTEXAI: str = os.getenv(
    "GOOGLE_GENAI_USE_VERTEXAI", _CFG.get("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")
)
BQ_DATASET: str = os.getenv("BQ_DATASET", _CFG.get("BQ_DATASET", "movielens"))
BQ_TABLE: str = os.getenv("BQ_TABLE", _CFG.get("BQ_TABLE", "customer_bookings"))
BQ_BOOKINGS_TABLE: str = (
    f"{GOOGLE_CLOUD_PROJECT}.{BQ_DATASET}.{BQ_TABLE}"
    if GOOGLE_CLOUD_PROJECT
    else f"{BQ_DATASET}.{BQ_TABLE}"
)
SEARCH_LOCATION: str = os.getenv(
    "SEARCH_LOCATION", _CFG.get("SEARCH_LOCATION", "global")
)
SEARCH_ENGINE_ID: str = os.getenv(
    "SEARCH_ENGINE_ID", _CFG.get("SEARCH_ENGINE_ID", "")
)
