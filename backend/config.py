from __future__ import annotations

import os
from dataclasses import dataclass

EXPOSED_RESPONSE_HEADERS = (
    "Content-Disposition",
    "X-Original-Size",
    "X-Processed-Size",
    "X-Compression-Ratio",
    "X-Compression-Mode",
    "X-Compression-Strategy",
    "X-Compression-Profile",
    "X-Document-Type",
    "X-Text-Priority",
    "X-Batch-Compression",
    "X-Page-Count",
    "X-Output-Count",
    "X-Requested-Target-KB",
    "X-Target-Achieved",
    "X-Tool",
)


@dataclass(frozen=True)
class AppConfig:
    max_content_length: int
    cors_origins: str | tuple[str, ...]


def load_app_config() -> AppConfig:
    raw_origins = os.getenv("CORS_ORIGINS", "*").strip()
    parsed_origins: str | tuple[str, ...]
    if raw_origins == "*":
        parsed_origins = "*"
    else:
        parsed_origins = tuple(item.strip() for item in raw_origins.split(",") if item.strip())

    return AppConfig(
        max_content_length=50 * 1024 * 1024,
        cors_origins=parsed_origins,
    )
