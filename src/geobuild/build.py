"""Assemble rule-sets from the configured sources."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .config import Config, RulesetConfig, SourceConfig, split_ref
from .domains import DomainSet, overlap
from .fetch import Fetcher
from .ips import IPSet, parse_network
from .origins import HANDLERS, Entry
from .util import BuildError, log, month_placeholders


@dataclass
class BuildResult:
    config: RulesetConfig
    rule: dict[str, list[str]]
    counts: dict[str, int]
    total: int
    rejects: dict[str, int]
    subtracted: int
    sources: list[str]
    domain_set: DomainSet | None = field(default=None, repr=False)
    ip_set: IPSet | None = field(default=None, repr=False)


class Builder:
    """Build context handed to origin handlers, plus the assembly logic."""

    def __init__(
        self,
        config: Config,
        fetcher: Fetcher,
        *,
        repository: str = "",
        version: str = "0.1.0",
    ) -> None:
        self.config = config
        self.fetcher = fetcher
        self.repository = repository
        self.version = version
        self._memo: dict[str, Any] = {}
        self._data: dict[str, bytes] = {}
        self.source_stats: dict[str, dict[str, Any]] = {}
        self.drops: Counter = Counter()
        self.drop_samples: dict[str, list[str]] = defaultdict(list)
        self.notes: list[str] = []
        self.checks: list[dict] = []
        self.results: dict[str, BuildResult] = {}

    # -- context API (used by origins handlers) ----------------------------

    def source(self, name: str) -> SourceConfig:
        return self.config.source(name)

    def revision(self, src: SourceConfig) -> str | None:
        return self.fetcher.revision(src)

    def _expand(self, template: str, src: SourceConfig) -> str:
        values = {
            "ref": src.ref or "",
            "revision": self.revision(src) or "",
            **month_placeholders(),
        }
        for key, value in values.items():
            template = template.replace("{" + key + "}", value)
        return template

    def url_for(self, src: SourceConfig) -> str:
        revision = self.revision(src)
        if "{revision}" in src.url and revision is None:
            if not src.url_fallback:
                raise BuildError(
                    f"{src.name}: cannot resolve '{{revision}}' and no url_fallback is configured"
                )
            return self._expand(src.url_fallback, src)
        return self._expand(src.url, src)

    def fallback_url(self, src: SourceConfig) -> str:
        if not src.url_fallback:
            raise BuildError(f"{src.name}: no url_fallback is configured")
        return self._expand(src.url_fallback, src)

    def fetch_url(self, url: str, src: SourceConfig) -> bytes:
        if url in self._data:
            return self._data[url]
        fetched = self.fetcher.get(url, revision=self.revision(src))
        self._data[url] = fetched.data
        self.source_stats[url] = {
            "source": src.name,
            "kind": src.kind,
            "url": url,
            "revision": fetched.revision,
            "sha256": fetched.sha256,
            "bytes": len(fetched.data),
            "fetched_at": fetched.fetched_at,
        }
        log(
            f"fetch {src.name}: {len(fetched.data)} bytes ({fetched.status}) sha256={fetched.sha256[:12]}"
        )
        return fetched.data

    def source_text(self, src: SourceConfig) -> bytes:
        return self.fetch_url(self.url_for(src), src)

    def memoize(self, key: str, factory: Callable[[], Any]) -> Any:
        if key not in self._memo:
            self._memo[key] = factory()
        return self._memo[key]

    def dropped(self, origin: str, reason: str, value: str = "") -> None:
        key = f"{origin}: {reason}"
        self.drops[key] += 1
        bucket = self.drop_samples[key]
        if value and len(bucket) < 3:
            bucket.append(value)

    def note(self, message: str, level: str = "warn") -> None:
        if message not in self.notes:
            self.notes.append(message)
            log(message, level)

    # -- assembly ----------------------------------------------------------

    def build(self, rulesets: list[RulesetConfig]) -> dict[str, BuildResult]:
        for ruleset in rulesets:
            self.results[ruleset.name] = self._build_one(ruleset)
        self._cross_checks()
        return self.results

    def _cross_checks(self) -> None:
        """Sanity checks that need more than one rule-set."""
        cn = self.results.get("domain/cn")
        gfw = self.results.get("domain/gfw")
        if cn is None or gfw is None or cn.domain_set is None or gfw.domain_set is None:
            return
        hits = overlap(gfw.domain_set, cn.domain_set)
        total = gfw.domain_set.total
        ratio = len(hits) / total if total else 0.0
        self.checks.append(
            {
                "name": "gfw-covered-by-cn",
                "rulesets": ["domain/gfw", "domain/cn"],
                "count": len(hits),
                "total": total,
                "ratio": round(ratio, 4),
                "samples": sorted(hits)[:10],
            }
        )
        # domain/cn intentionally ships the bare "cn" TLD (DLC does too), so
        # every blocked *.cn entry is "covered" by definition. What matters is
        # that gfw is evaluated first; the threshold reflects that.
        if ratio > 0.02:
            self.note(
                f"domain/cn covers {len(hits)}/{total} gfw entries ({ratio:.1%}); "
                "check that domain/gfw is matched before domain/cn"
            )

    def _build_one(self, ruleset: RulesetConfig) -> BuildResult:
        domains = DomainSet() if ruleset.type == "domain" else None
        ips = IPSet() if ruleset.type == "ip" else None
        used: list[str] = []

        for ref in ruleset.sources:
            endpoint, selector = split_ref(ref)
            src = self.config.source(endpoint)
            handler = HANDLERS.get(src.kind)
            if handler is None:
                raise BuildError(
                    f"{ruleset.name}: source {endpoint!r} has unknown kind {src.kind!r}"
                )
            excluded = set(ruleset.exclude_attrs)
            produced = 0
            for entry in handler(self, src, selector):
                produced += 1
                hit = entry.attrs & excluded
                if hit:
                    self.dropped(ref, f"excluded @{','.join(sorted(hit))}", entry.value)
                    continue
                self._add(entry, ref, ruleset, domains, ips)
            used.append(ref)
            if produced == 0:
                if src.allow_empty:
                    continue
                raise BuildError(f"{ruleset.name}: source {ref!r} produced no entries")
            if produced < src.expect_min:
                raise BuildError(
                    f"{ruleset.name}: source {ref!r} produced {produced} entries, "
                    f"expected >= {src.expect_min} (upstream probably broke or shrank)"
                )

        for dependency in ruleset.union:
            other = self.results.get(dependency)
            if other is None:
                raise BuildError(
                    f"{ruleset.name}: union target {dependency!r} was not built"
                )
            if other.config.type != ruleset.type:
                raise BuildError(
                    f"{ruleset.name}: union target {dependency!r} is {other.config.type}, "
                    f"expected {ruleset.type}"
                )
            if domains is not None and other.domain_set is not None:
                domains.update(other.domain_set)
            if ips is not None and other.ip_set is not None:
                ips.update(other.ip_set)
            used.append(dependency)

        removed = 0
        for dependency in ruleset.subtract:
            other = self.results.get(dependency)
            if other is None:
                raise BuildError(
                    f"{ruleset.name}: subtract target {dependency!r} was not built"
                )
            if other.config.type != ruleset.type:
                raise BuildError(
                    f"{ruleset.name}: subtract target {dependency!r} is "
                    f"{other.config.type}, expected {ruleset.type}"
                )
            if domains is not None and other.domain_set is not None:
                removed += domains.subtract(other.domain_set)
            elif ips is not None and other.ip_set is not None:
                removed += ips.subtract(other.ip_set)
            used.append(f"-{dependency}")

        rejects: dict[str, int] = {}
        if domains is not None:
            domains.minimize()
            rule = domains.to_rule()
            rejects = dict(domains.rejects)
            total = domains.total
        else:
            if ips is None:  # pragma: no cover - guarded by the type check
                raise BuildError(f"{ruleset.name}: ip rule-set without an ip set")
            rule = ips.to_rule()
            rejects = dict(ips.rejects)
            total = len(rule.get("ip_cidr") or [])

        if total == 0:
            raise BuildError(f"{ruleset.name}: produced an empty rule-set")
        if total < ruleset.expect_min:
            raise BuildError(
                f"{ruleset.name}: produced {total} entries, expected >= {ruleset.expect_min}"
            )

        counts = {key: len(value) for key, value in rule.items()}
        return BuildResult(
            config=ruleset,
            rule=rule,
            counts=counts,
            total=total,
            rejects=rejects,
            subtracted=removed,
            sources=used,
            domain_set=domains,
            ip_set=ips,
        )

    def _add(
        self,
        entry: Entry,
        ref: str,
        ruleset: RulesetConfig,
        domains: DomainSet | None,
        ips: IPSet | None,
    ) -> None:
        if entry.kind == "cidr":
            if ips is None:
                self.dropped(ref, "cidr inside a domain rule-set", entry.value)
                return
            if ruleset.family != "any":
                try:
                    version = parse_network(entry.value).version
                except ValueError:
                    version = 0
                if str(version) != ruleset.family:
                    self.dropped(ref, f"filtered: not IPv{ruleset.family}", entry.value)
                    return
            _ = ips.add(entry.value, origin=ref)
            return
        if domains is None:
            self.dropped(ref, f"{entry.kind} domain inside an ip rule-set", entry.value)
            return
        if entry.kind == "regex" and not ruleset.allow_regex:
            # domain_regex is an O(n) scan; only opt-in rule-sets may carry it.
            self.dropped(ref, "regex (not enabled for this rule-set)", entry.value)
            return
        _ = domains.add(entry.value, kind=entry.kind, origin=ref)
