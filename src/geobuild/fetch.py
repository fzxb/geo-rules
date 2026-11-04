"""HTTP fetching with a content cache, retries and revision pinning.

Design notes
------------
* Cache entries are keyed by the SHA-256 of the URL, and the payload hash is
  recorded in the manifest. That makes a build auditable after the fact.
* Sources that live in git are pinned to a resolved commit sha / release tag
  (``{revision}``). When the revision did not change the cached body is reused
  without any network traffic, even if the TTL expired.
* Anything that fails three times is a hard error: a partially updated ruleset
  is worse than no update at all.
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import SourceConfig
from .util import BuildError, log, sha256_bytes, utc_now

GITHUB_API = "https://api.github.com"
RETRYABLE = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass
class Fetched:
    url: str
    data: bytes
    sha256: str
    revision: str | None
    fetched_at: str
    status: str  # cache | download | not-modified


class Fetcher:
    def __init__(
        self,
        cache_dir: Path,
        user_agent: str,
        *,
        token: str | None = None,
        ttl: int = 6 * 3600,
        offline: bool = False,
        retries: int = 3,
        timeout: int = 90,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.objects = self.cache_dir / "objects"
        self.objects.mkdir(parents=True, exist_ok=True)
        self.user_agent = user_agent
        self.token = token or os.environ.get("GITHUB_TOKEN") or None
        self.ttl = ttl
        self.offline = offline
        self.retries = retries
        self.timeout = timeout
        self._api_cache: dict[str, Any] = {}
        self._revisions: dict[str, str | None] = {}
        self._revision_cache: dict[tuple[str, str], str] = {}

    # -- low level ---------------------------------------------------------

    def _headers(self, url: str, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"User-Agent": self.user_agent, "Accept-Encoding": "identity"}
        if self.token and url.startswith(GITHUB_API):
            headers["Authorization"] = f"Bearer {self.token}"
            headers["X-GitHub-Api-Version"] = "2022-11-28"
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self, url: str, headers: dict[str, str]
    ) -> tuple[int, bytes, dict[str, str], str]:
        if not url.startswith(("https://", "http://")):
            raise BuildError(f"refusing to fetch non-HTTP URL: {url}")
        attempt = 0
        while True:
            attempt += 1
            # Scheme is validated above; only http(s) can reach this point.
            request = urllib.request.Request(url, headers=headers)  # noqa: S310
            try:
                with urllib.request.urlopen(  # noqa: S310
                    request, timeout=self.timeout
                ) as response:
                    return (
                        int(response.status),
                        response.read(),
                        {key.lower(): value for key, value in response.headers.items()},
                        response.geturl(),
                    )
            except urllib.error.HTTPError as exc:
                if exc.code == 304:
                    return (
                        304,
                        b"",
                        {key.lower(): value for key, value in exc.headers.items()},
                        url,
                    )
                if exc.code in RETRYABLE and attempt < self.retries:
                    self._sleep(attempt, f"HTTP {exc.code} for {url}")
                    continue
                raise BuildError(
                    f"GET {url} failed: HTTP {exc.code} {exc.reason}"
                ) from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt < self.retries:
                    self._sleep(attempt, f"{exc} for {url}")
                    continue
                raise BuildError(f"GET {url} failed: {exc}") from None

    def _sleep(self, attempt: int, reason: str) -> None:
        delay = min(2**attempt, 10) + random.uniform(0, 0.5)
        log(f"{reason}; retrying in {delay:.1f}s ({attempt}/{self.retries})", "warn")
        time.sleep(delay)

    # -- cache -------------------------------------------------------------

    def _paths(self, url: str) -> tuple[Path, Path]:
        key = sha256_bytes(url.encode("utf-8"))
        return self.objects / key, self.objects / f"{key}.meta.json"

    def _load_meta(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    @staticmethod
    def _store_meta(path: Path, meta: dict[str, Any]) -> None:
        _ = path.write_text(json.dumps(meta), encoding="utf-8")

    def get(
        self, url: str, *, revision: str | None = None, max_age: int | None = None
    ) -> Fetched:
        max_age = self.ttl if max_age is None else max_age
        body_path, meta_path = self._paths(url)
        meta = self._load_meta(meta_path)

        if meta and body_path.exists():
            pinned = revision is not None and meta.get("revision") == revision
            fetched_ts = meta.get("fetched_at_ts")
            age = time.time() - (
                fetched_ts if isinstance(fetched_ts, (int, float)) else 0.0
            )
            fresh = revision is None and age < max_age
            if pinned or fresh:
                return Fetched(
                    url=url,
                    data=body_path.read_bytes(),
                    sha256=str(meta.get("sha256", "")),
                    revision=meta.get("revision"),
                    fetched_at=str(meta.get("fetched_at", "")),
                    status="cache",
                )

        if self.offline:
            raise BuildError(f"offline build: {url} is not in the cache")

        headers = self._headers(url)
        if meta and body_path.exists():
            if meta.get("etag"):
                headers["If-None-Match"] = str(meta["etag"])
            if meta.get("last_modified"):
                headers["If-Modified-Since"] = str(meta["last_modified"])

        http_status, body, response_headers, _ = self._request(url, headers)
        if http_status == 304 and meta and body_path.exists():
            meta["fetched_at"] = utc_now()
            meta["fetched_at_ts"] = time.time()
            if revision is not None:
                meta["revision"] = revision
            self._store_meta(meta_path, meta)
            return Fetched(
                url=url,
                data=body_path.read_bytes(),
                sha256=str(meta.get("sha256", "")),
                revision=meta.get("revision"),
                fetched_at=str(meta["fetched_at"]),
                status="not-modified",
            )

        if not body:
            raise BuildError(f"GET {url} returned an empty body")

        digest = sha256_bytes(body)
        note = "download"
        if meta and meta.get("sha256") == digest:
            # Same content, new URL/revision: keep the existing blob.
            note = "cache"
        else:
            _ = body_path.write_bytes(body)

        new_meta = {
            "url": url,
            "sha256": digest,
            "bytes": len(body),
            "etag": response_headers.get("etag", ""),
            "last_modified": response_headers.get("last-modified", ""),
            "fetched_at": utc_now(),
            "fetched_at_ts": time.time(),
            "revision": revision,
        }
        self._store_meta(meta_path, new_meta)
        return Fetched(
            url=url,
            data=body,
            sha256=digest,
            revision=revision,
            fetched_at=new_meta["fetched_at"],
            status=note,
        )

    # -- GitHub ------------------------------------------------------------

    def github(self, path: str) -> Any:
        if path in self._api_cache:
            return self._api_cache[path]
        url = GITHUB_API + path
        status, body, _, _ = self._request(
            url, self._headers(url, {"Accept": "application/vnd.github+json"})
        )
        if status != 200:
            raise BuildError(f"GitHub API {path}: HTTP {status}")
        try:
            payload = json.loads(body)
        except ValueError:
            raise BuildError(f"GitHub API {path}: invalid JSON") from None
        self._api_cache[path] = payload
        return payload

    def revision(self, source: SourceConfig) -> str | None:
        """Resolve ``{revision}`` for a source, or ``None`` when not applicable."""
        if source.name in self._revisions:
            return self._revisions[source.name]

        revision = source.revision
        if revision is None and source.repo and source.ref:
            cache_key = (source.repo, source.ref)
            try:
                if cache_key in self._revision_cache:
                    revision = self._revision_cache[cache_key]
                elif source.ref == "latest":
                    payload = self.github(f"/repos/{source.repo}/releases/latest")
                    revision = self._revision_cache[cache_key] = str(
                        payload["tag_name"]
                    )
                else:
                    payload = self.github(f"/repos/{source.repo}/commits/{source.ref}")
                    revision = self._revision_cache[cache_key] = str(payload["sha"])
            except (BuildError, KeyError, TypeError) as exc:
                log(f"cannot resolve revision for {source.name}: {exc}", "warn")
                revision = None
        self._revisions[source.name] = revision
        return revision
