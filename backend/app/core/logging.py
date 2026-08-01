"""Logging setup.

Deliberately minimal for now: a single, readable format to stdout. This is
the one place logging gets configured, so structured logging (e.g. JSON
for production, correlation IDs per case) can be introduced later without
hunting down `logging.basicConfig` calls scattered around the app.
"""

import logging

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = logging.DEBUG if settings.environment == "development" else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
