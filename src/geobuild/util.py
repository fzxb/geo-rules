"""Small helpers shared by the builder."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path


class BuildError(RuntimeError):
    """Fatal condition: nothing must be published when this is raised."""


def log(message: str, level: str = "info") -> None:
    tag = {"info": "INFO", "warn": "WARN", "error": "ERR "}.get(level, level.upper())
    print(f"{tag} {message}", file=sys.stderr, flush=True)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: object, *, indent: int | None = 2) -> None:
    """Atomically write deterministic JSON (no trailing spaces, LF newlines)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=indent)
        _ = handle.write("\n")
    os.replace(tmp, path)


def read_json(path: Path) -> object:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise BuildError(f"cannot read {path}: {exc}") from None


def month_placeholders(now: datetime | None = None) -> dict[str, str]:
    """Values for ``{year}`` / ``{month}`` style placeholders (UTC).

    Used by sources that publish dated files instead of git revisions, such as
    the monthly DB-IP country databases.
    """
    current = now or datetime.now(UTC)
    previous = current.replace(day=1) - timedelta(days=1)
    return {
        "year": current.strftime("%Y"),
        "month": current.strftime("%m"),
        "prev_year": previous.strftime("%Y"),
        "prev_month": previous.strftime("%m"),
    }


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def human_bytes(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if size < 1024 or unit == "GiB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GiB"


def human_int(value: int) -> str:
    return f"{value:,}"
