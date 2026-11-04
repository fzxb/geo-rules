"""Load and validate the build configuration (config/*.toml)."""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .util import BuildError

VALID_TYPES = ("domain", "ip")
VALID_FAMILIES = {
    "any": "any",
    "all": "any",
    "4": "4",
    "ipv4": "4",
    "6": "6",
    "ipv6": "6",
}
_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._/-]*$")


@dataclass(frozen=True)
class SourceConfig:
    """One upstream endpoint.

    ``url`` may contain ``{revision}`` (resolved release tag / commit sha) and
    ``{ref}`` (the configured git ref). Handlers may substitute further
    placeholders such as ``{asn}`` for their selector.
    """

    name: str
    kind: str
    url: str = ""
    repo: str | None = None
    ref: str | None = None
    revision: str | None = None
    url_fallback: str | None = None
    expect_min: int = 1
    allow_empty: bool = False
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RulesetConfig:
    name: str
    type: str
    description: str = ""
    sources: tuple[str, ...] = ()
    union: tuple[str, ...] = ()
    subtract: tuple[str, ...] = ()
    expect_min: int = 1
    family: str = "any"
    exclude_attrs: tuple[str, ...] = ()
    allow_regex: bool = False

    @property
    def dependencies(self) -> tuple[str, ...]:
        return self.union + self.subtract


@dataclass(frozen=True)
class Config:
    settings: dict[str, Any]
    sources: dict[str, SourceConfig]
    rulesets: tuple[RulesetConfig, ...]

    def source(self, name: str) -> SourceConfig:
        try:
            return self.sources[name]
        except KeyError:
            raise BuildError(f"unknown source {name!r}") from None

    def by_name(self) -> dict[str, RulesetConfig]:
        return {ruleset.name: ruleset for ruleset in self.rulesets}


def split_ref(ref: str) -> tuple[str, str]:
    """``dlc:cn`` -> (``dlc``, ``cn``); ``gfwlist`` -> (``gfwlist``, ``""``)."""
    endpoint, sep, selector = ref.partition(":")
    return endpoint, selector if sep else ""


def _source_from(name: str, raw: dict[str, Any]) -> SourceConfig:
    if not isinstance(raw, dict):
        raise BuildError(f"source {name!r}: must be a table")
    kind = raw.get("kind")
    if not kind:
        raise BuildError(f"source {name!r}: missing 'kind'")
    url = raw.get("url") or ""
    if not url and kind != "static":
        raise BuildError(f"source {name!r}: missing 'url'")
    known = {
        "kind",
        "url",
        "repo",
        "ref",
        "revision",
        "url_fallback",
        "expect_min",
        "allow_empty",
    }
    options = {key: value for key, value in raw.items() if key not in known}
    return SourceConfig(
        name=name,
        kind=str(kind),
        url=str(url),
        repo=raw.get("repo"),
        ref=raw.get("ref"),
        revision=raw.get("revision"),
        url_fallback=raw.get("url_fallback"),
        expect_min=int(raw.get("expect_min", 1)),
        allow_empty=bool(raw.get("allow_empty", False)),
        options=options,
    )


def _ruleset_from(raw: dict[str, Any]) -> RulesetConfig:
    name = raw.get("name")
    if not name or not isinstance(name, str):
        raise BuildError(f"ruleset without a valid 'name': {raw!r}")
    if not _NAME_RE.match(name):
        raise BuildError(f"ruleset name {name!r} must match {_NAME_RE.pattern}")
    # Names become output paths, so reject anything that can escape --out.
    if any(part in ("", ".", "..") for part in name.split("/")):
        raise BuildError(
            f"ruleset name {name!r} must not contain empty, '.' or '..' segments"
        )
    type_ = raw.get("type")
    if type_ not in VALID_TYPES:
        raise BuildError(f"ruleset {name!r}: type must be one of {VALID_TYPES}")
    sources = tuple(str(item) for item in raw.get("sources", ()))
    union = tuple(str(item) for item in raw.get("union", ()))
    subtract = tuple(str(item) for item in raw.get("subtract", ()))
    if not sources and not union:
        raise BuildError(f"ruleset {name!r}: needs 'sources' and/or 'union'")
    family_raw = str(raw.get("family", "any")).lower().removeprefix("ipv")
    family = VALID_FAMILIES.get(family_raw)
    if family is None:
        raise BuildError(f"ruleset {name!r}: family must be 4, 6 or any")
    return RulesetConfig(
        name=name,
        type=str(type_),
        description=str(raw.get("description", "")),
        sources=sources,
        union=union,
        subtract=subtract,
        expect_min=int(raw.get("expect_min", 1)),
        family=family,
        exclude_attrs=tuple(
            str(attr).strip().lstrip("@")
            for attr in raw.get("exclude_attrs", ())
            if str(attr).strip()
        ),
        allow_regex=bool(raw.get("allow_regex", False)),
    )


def load_config(config_dir: Path) -> Config:
    sources_path = config_dir / "sources.toml"
    rulesets_path = config_dir / "rulesets.toml"
    for path in (sources_path, rulesets_path):
        if not path.exists():
            raise BuildError(f"missing config file: {path}")

    with sources_path.open("rb") as handle:
        sources_raw = tomllib.load(handle)
    with rulesets_path.open("rb") as handle:
        rulesets_raw = tomllib.load(handle)

    settings = dict(sources_raw.get("settings", {}))
    sources = {
        name: _source_from(name, raw)
        for name, raw in sources_raw.get("sources", {}).items()
    }
    if not sources:
        raise BuildError("no sources configured")
    rulesets = tuple(_ruleset_from(raw) for raw in rulesets_raw.get("ruleset", ()))
    if not rulesets:
        raise BuildError("no rulesets configured")

    seen: set[str] = set()
    for ruleset in rulesets:
        if ruleset.name in seen:
            raise BuildError(f"duplicate ruleset {ruleset.name!r}")
        seen.add(ruleset.name)

    known = set(sources)
    for ruleset in rulesets:
        for ref in ruleset.sources:
            endpoint, _ = split_ref(ref)
            if endpoint not in known:
                raise BuildError(
                    f"ruleset {ruleset.name!r}: unknown source {endpoint!r}"
                )
        for dep in ruleset.union:
            if dep not in seen:
                raise BuildError(
                    f"ruleset {ruleset.name!r}: unknown union target {dep!r}"
                )
        for dep in ruleset.subtract:
            if dep not in seen:
                raise BuildError(
                    f"ruleset {ruleset.name!r}: unknown subtract target {dep!r}"
                )
        if ruleset.name in ruleset.dependencies:
            raise BuildError(
                f"ruleset {ruleset.name!r}: cannot reference itself in union/subtract"
            )

    return Config(settings=settings, sources=sources, rulesets=rulesets)


def build_order(rulesets: tuple[RulesetConfig, ...]) -> list[RulesetConfig]:
    """Topological order over ``union`` / ``subtract`` dependencies."""
    by_name = {ruleset.name: ruleset for ruleset in rulesets}
    state: dict[str, str] = {}
    order: list[RulesetConfig] = []

    def visit(name: str, stack: list[str]) -> None:
        current = state.get(name)
        if current == "done":
            return
        if current == "visiting":
            raise BuildError("union cycle: " + " -> ".join([*stack, name]))
        state[name] = "visiting"
        ruleset = by_name[name]
        for dep in ruleset.dependencies:
            visit(dep, stack + [name])
        state[name] = "done"
        order.append(ruleset)

    for ruleset in rulesets:
        visit(ruleset.name, [])
    return order


def select(rulesets: tuple[RulesetConfig, ...], only: set[str]) -> list[RulesetConfig]:
    """Keep the requested rulesets plus every transitive union dependency."""
    by_name = {ruleset.name: ruleset for ruleset in rulesets}
    keep: set[str] = set()

    def closure(name: str) -> None:
        if name in keep:
            return
        keep.add(name)
        for dep in by_name[name].dependencies:
            closure(dep)

    for name in only:
        if name not in by_name:
            raise BuildError(f"--only: unknown ruleset {name!r}")
        closure(name)
    return [ruleset for ruleset in build_order(rulesets) if ruleset.name in keep]
