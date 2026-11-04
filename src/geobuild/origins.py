"""Upstream parsers ("kinds").

Every handler yields :class:`Entry` objects and never mutates the rule-set
itself. Anything that cannot be represented *safely* is reported through
``ctx.dropped()`` instead of being guessed at, so the manifest always tells the
truth about what was skipped and why.
"""

from __future__ import annotations

import base64
import binascii
import csv
import gzip
import io
import ipaddress
import json
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any, Protocol

from .config import SourceConfig
from .domains import InvalidDomain, covered_by, normalize_domain
from .ips import Network
from .util import BuildError, log


class OriginContext(Protocol):
    """The slice of :class:`geobuild.build.Builder` that handlers may use."""

    def source_text(self, src: SourceConfig) -> bytes: ...

    def fetch_url(self, url: str, src: SourceConfig) -> bytes: ...

    def url_for(self, src: SourceConfig) -> str: ...

    def fallback_url(self, src: SourceConfig) -> str: ...

    def memoize(self, key: str, factory: Callable[[], Any]) -> Any: ...

    def dropped(self, origin: str, reason: str, value: str = "") -> None: ...

    def note(self, message: str, level: str = "warn") -> None: ...


@dataclass(frozen=True)
class Entry:
    """A single upstream rule, already normalised to a rule-set primitive."""

    kind: str  # "suffix" | "exact" | "cidr"
    value: str
    origin: str = ""
    attrs: frozenset[str] = frozenset()


def _json(payload: bytes, label: str) -> dict:
    try:
        parsed = json.loads(payload)
    except ValueError as exc:
        raise BuildError(f"{label}: invalid JSON ({exc})") from None
    if not isinstance(parsed, dict):
        raise BuildError(f"{label}: expected a JSON object")
    return parsed


# ---------------------------------------------------------------------------
# domain-list-community
# ---------------------------------------------------------------------------

_NAME_RE = re.compile(r"^  - name: (.*)$")
_LENGTH_RE = re.compile(r"^    length: (\d+)$")
_ITEM_RE = re.compile(r"^      - (.*)$")


def _unquote(raw: str) -> str:
    text = raw.strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        try:
            return str(json.loads(text))
        except ValueError:
            if "\\" in text:
                log(f"dlc: cannot unescape YAML scalar: {text[:80]}", "warn")
            return text[1:-1]
    return text


def parse_dlc_plain_yaml(text: str) -> dict[str, list[str]]:
    """Parse ``dlc.dat_plain.yml``.

    The file is machine generated and fully flattened (``include:`` already
    resolved), but attributes are kept inline as a trailing ``:@attr1,@attr2``
    suffix on each rule (see :func:`split_dlc_rule`). We consume it instead of
    re-implementing geosite's include semantics.
    """
    lists: dict[str, list[str]] = {}
    declared: dict[str, int] = {}
    current: str | None = None

    for lineno, line in enumerate(text.splitlines(), 1):
        stripped = line.rstrip()
        if not stripped or stripped.startswith("#") or stripped == "lists:":
            continue
        match = _NAME_RE.match(stripped)
        if match:
            name = _unquote(match.group(1))
            if name in lists:
                raise BuildError(f"dlc: duplicate list {name!r} at line {lineno}")
            lists[name] = []
            current = name
            continue
        match = _LENGTH_RE.match(stripped)
        if match:
            if current is None:
                raise BuildError(f"dlc: length without list at line {lineno}")
            declared[current] = int(match.group(1))
            continue
        if stripped == "    rules:":
            continue
        match = _ITEM_RE.match(stripped)
        if match:
            if current is None:
                raise BuildError(f"dlc: rule without list at line {lineno}")
            lists[current].append(_unquote(match.group(1)))
            continue
        raise BuildError(f"dlc: unexpected line {lineno}: {stripped[:120]!r}")

    for name, expected in declared.items():
        actual = len(lists[name])
        if actual != expected:
            raise BuildError(
                f"dlc: list {name!r} declares {expected} rules but parsed {actual}"
            )
    return lists


def split_dlc_rule(rule: str) -> tuple[str, str, set[str]]:
    """Split ``full:example.com:@ads,@telemetry`` into (kind, value, attrs)."""
    body, _, attrs_raw = rule.partition(":@")
    kind, separator, value = body.partition(":")
    if not separator:
        kind, value = "domain", body
    attrs = (
        {attr.lstrip("@") for attr in attrs_raw.split(",") if attr}
        if attrs_raw
        else set()
    )
    return kind, value, attrs


def load_dlc(ctx: OriginContext, src: SourceConfig, selector: str) -> Iterator[Entry]:
    lists = ctx.memoize(
        "dlc", lambda: parse_dlc_plain_yaml(ctx.source_text(src).decode("utf-8"))
    )
    name, _, wanted_raw = selector.strip().partition("@")
    wanted = wanted_raw.lstrip("@")

    if name == "*":
        if not wanted:
            raise BuildError("dlc: '*' requires an attribute, e.g. 'dlc:*@cn'")
        # Ad lists are excluded: an ad domain that happens to be tagged @cn
        # should stay in domain/ads, not become a direct-routing entry.
        names = sorted(n for n in lists if not n.startswith("category-ads"))
        origin = f"dlc:*@{wanted}"
    else:
        if name not in lists:
            raise BuildError(f"dlc: list {name!r} does not exist")
        names = [name]
        origin = f"dlc:{name}{'@' + wanted if wanted else ''}"

    for list_name in names:
        for rule in lists[list_name]:
            kind, value, attrs = split_dlc_rule(rule)
            if wanted and wanted not in attrs:
                continue
            if kind == "domain":
                yield Entry("suffix", value, origin, frozenset(attrs))
            elif kind == "full":
                yield Entry("exact", value, origin, frozenset(attrs))
            elif kind == "regexp":
                ctx.dropped(origin, "regexp", value)
            elif kind == "include":
                raise BuildError(
                    f"dlc: list {list_name!r} still contains include directives"
                )
            else:
                ctx.dropped(origin, f"rule type {kind}", value)


# ---------------------------------------------------------------------------
# gfwlist (AutoProxy / AdBlock syntax)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AdblockRule:
    """One reduced AdBlock line.

    ``subdomain_only`` records a ``*.example.com`` pattern: it matches
    subdomains of ``example.com`` but *not* ``example.com`` itself. A rule-set
    has no such matcher, so the caller must decide how to widen it and say so.
    ``path_scoped`` records a rule that was narrowed to a single URL.
    """

    kind: str
    value: str
    subdomain_only: bool = False
    path_scoped: bool = False


def _parse_adblock_rule(raw: str) -> AdblockRule | None:
    """Reduce one AdBlock-style line to a domain or CIDR token."""
    text = raw.strip()
    if not text or text.startswith("!"):
        return None
    if text.startswith("/"):
        # AdBlock regexps always start with "/". Neither form (delimited or
        # not) can be expressed in a rule-set; the caller records the drop.
        return AdblockRule("regexp", text)
    if text.startswith("||"):
        text = text[2:]
    elif text.startswith("|"):
        text = text[1:]

    lowered = text.lower()
    for scheme in ("https://", "http://", "ftp://", "ws" + "://", "wss" + "://"):
        if lowered.startswith(scheme):
            text = text[len(scheme) :]
            break

    path_scoped = False
    cut = len(text)
    for separator in ("/", "?", "#", "|", "^"):
        index = text.find(separator)
        if index < 0:
            continue
        if separator in ("/", "?", "#") and index > 0:
            path_scoped = True
        cut = min(cut, index)
    text = text[:cut].strip()
    if not text:
        return None

    subdomain_only = text.startswith("*.")
    while text.startswith("*."):
        text = text[2:]
    if "*" in text:
        # Keep the original glob instead of widening it to its parent domain:
        # "fbcdn*.akamaihd.net" must not turn into "akamaihd.net".
        return AdblockRule("regex", _glob_to_regex(text))

    try:
        ipaddress.ip_network(text, strict=False)
    except ValueError:
        pass
    else:
        return AdblockRule("cidr", text)
    return AdblockRule("suffix", text, subdomain_only, path_scoped)


def _glob_to_regex(glob: str) -> str:
    """Translate an AdBlock glob into an anchored domain regex.

    ``*`` is the only wildcard in AdBlock and matches any string (including
    dots); everything else is taken literally.
    """
    return "^" + ".*".join(re.escape(part) for part in glob.split("*")) + "$"


# Lookarounds and backreferences are not supported by Go's RE2, so a pattern
# that needs them can never be compiled by sing-box.
_RE2_UNSUPPORTED = re.compile(r"\(\?|\\[1-9]")


def domain_regex_from_url(pattern: str) -> str | None:
    """Map a URL-anchored AutoProxy regex onto the domain it constrains.

    Only patterns starting with an explicit ``^http(s)://`` anchor are
    accepted: those constrain the host, which is the part a rule-set can see.
    Anything else (path-only, query-only, lookarounds, backreferences) returns
    ``None`` and is reported as a drop instead of being guessed at.
    """
    body = pattern.strip()
    if body.startswith("/") and body.endswith("/") and len(body) > 2:
        body = body[1:-1]
    body = body.replace("\\/", "/")
    for prefix in ("^https?://", "^http://", "^https://", "^ftp://"):
        if body.startswith(prefix):
            body = body[len(prefix) :]
            break
    else:
        return None
    if not body or _RE2_UNSUPPORTED.search(body):
        return None
    # A literal "/" means the pattern constrains the path; the rule-set only
    # ever sees the host, so such a pattern would be dead weight.
    if "/" in re.sub(r"\[[^\]]*\]", "", body):
        return None
    try:
        re.compile(body)
    except re.error:
        return None
    return body


def load_gfwlist(
    ctx: OriginContext, src: SourceConfig, _selector: str
) -> Iterator[Entry]:
    # 同一份列表同时喂给 domain/gfw 和 ip/gfw，只解析一次，避免 drops 重复计数
    entries = ctx.memoize(f"gfwlist:{src.name}", lambda: list(_parse_gfwlist(ctx, src)))
    return iter(entries)


def _parse_gfwlist(ctx: OriginContext, src: SourceConfig) -> Iterator[Entry]:
    raw = ctx.source_text(src)
    if raw.lstrip().startswith(b"[AutoProxy"):
        text = raw.decode("utf-8", "replace")
    else:
        try:
            text = base64.b64decode(raw).decode("utf-8", "replace")
        except (binascii.Error, ValueError):
            text = raw.decode("utf-8", "replace")

    allowed: set[str] = set()
    allowed_subdomains: set[str] = set()
    blocked: list[AdblockRule] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith(("!", "[")):
            continue
        if line.startswith("@@"):
            parsed = _parse_adblock_rule(line[2:])
            if parsed is None:
                ctx.dropped("gfwlist:allow", "unparsable", line)
                continue
            if parsed.kind != "suffix":
                ctx.dropped("gfwlist:allow", parsed.kind, parsed.value)
                continue
            if parsed.path_scoped:
                # "allow this one URL" cannot be carved out of a host-level
                # block, so the block has to win.
                ctx.dropped("gfwlist:allow", "scoped to a URL path", parsed.value)
                continue
            try:
                domain = normalize_domain(parsed.value)
            except InvalidDomain as exc:
                ctx.dropped("gfwlist:allow", str(exc).split(":")[0], parsed.value)
                continue
            if parsed.subdomain_only:
                # "@@||*.example.com" exempts subdomains but not the apex.
                allowed_subdomains.add(domain)
            else:
                allowed.add(domain)
            continue
        parsed = _parse_adblock_rule(line)
        if parsed is None:
            ctx.dropped("gfwlist", "unparsable", line)
            continue
        blocked.append(parsed)

    def is_allowed(domain: str) -> bool:
        if allowed and covered_by(domain, allowed):
            return True
        return any(
            domain != parent and covered_by(domain, {parent})
            for parent in allowed_subdomains
        )

    blocked_suffixes: set[str] = set()
    for rule in blocked:
        if rule.kind != "suffix":
            continue
        try:
            blocked_suffixes.add(normalize_domain(rule.value))
        except InvalidDomain:
            continue

    narrowed = [
        allow
        for allow in sorted(allowed)
        if any(
            allow != suffix and allow.endswith("." + suffix)
            for suffix in blocked_suffixes
        )
    ]
    for allow in narrowed:
        # AutoProxy can carve a subdomain out of a blocked suffix; a rule-set
        # cannot express that, so the block wins and the exception is recorded.
        ctx.dropped("gfwlist", "@@ exception narrower than block", allow)
    if narrowed:
        ctx.note(
            f"gfwlist: {len(narrowed)} @@ exceptions are narrower than their blocked "
            "suffix and stay proxied (rule-set has no negation)",
            level="info",
        )

    stuck_wildcards = sorted(
        allow
        for allow in allowed_subdomains
        if allow in blocked_suffixes
        or any(allow.endswith("." + suffix) for suffix in blocked_suffixes)
    )
    if stuck_wildcards:
        ctx.note(
            f"gfwlist: {len(stuck_wildcards)} @@ wildcard exception(s) only cover "
            "subdomains; a rule-set cannot express that, so they stay proxied "
            f"({', '.join(stuck_wildcards[:3])})",
            level="info",
        )

    widened_subdomains = sorted({rule.value for rule in blocked if rule.subdomain_only})
    widened_paths = sorted(
        {rule.value for rule in blocked if rule.path_scoped and rule.kind == "suffix"}
    )
    if widened_subdomains:
        ctx.note(
            f"gfwlist: {len(widened_subdomains)} subdomain wildcard block rule(s) are "
            "matched at host level, i.e. widened to the parent domain "
            f"({', '.join(widened_subdomains[:3])})"
        )
    if widened_paths:
        ctx.note(
            f"gfwlist: {len(widened_paths)} URL-path block rule(s) are matched at host "
            f"level ({', '.join(widened_paths[:3])})"
        )

    for rule in blocked:
        if rule.kind == "cidr":
            yield Entry("cidr", rule.value, "gfwlist")
            continue
        if rule.kind == "regex":
            # Glob rules keep their exact meaning; no parent-domain widening.
            yield Entry("regex", rule.value, "gfwlist")
            continue
        if rule.kind == "regexp":
            mapped = domain_regex_from_url(rule.value)
            if mapped is None:
                ctx.dropped(
                    "gfwlist", "regexp (cannot be mapped to a domain)", rule.value
                )
                continue
            yield Entry("regex", mapped, "gfwlist")
            continue
        try:
            domain = normalize_domain(rule.value)
        except InvalidDomain:
            # Let DomainSet record the precise rejection reason.
            yield Entry("suffix", rule.value, "gfwlist")
            continue
        if is_allowed(domain):
            ctx.dropped("gfwlist", "allowed by @@", domain)
            continue
        yield Entry("suffix", domain, "gfwlist")


# ---------------------------------------------------------------------------
# dnsmasq-china-list (accelerated-domains.china.conf)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# DB-IP Lite country database (geolocation / user-attributed, monthly CSV)
# ---------------------------------------------------------------------------


def load_dbip_country(
    ctx: OriginContext, src: SourceConfig, selector: str
) -> Iterator[Entry]:
    """``start,end,country`` rows from DB-IP Lite.

    This is the "where the address is used" view: it is produced from registry
    data plus network topology and observed geolocation, so it catches blocks
    that are registered abroad but operate from China (and vice versa). It is
    unioned with the registry and BGP views instead of replacing them.
    """
    country = selector.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", country):
        raise BuildError(
            f"dbip: selector must be a two letter country, got {selector!r}"
        )
    try:
        raw = ctx.source_text(src)
    except BuildError as exc:
        if not src.url_fallback:
            raise
        # Monthly files appear a little after the first of the month; fall back
        # to the previous release and say so. Both URLs end up in the manifest.
        log(f"{src.name}: {exc}; falling back to {src.url_fallback}", "warn")
        raw = ctx.fetch_url(ctx.fallback_url(src), src)
    try:
        text = gzip.decompress(raw).decode("utf-8", "replace")
    except (OSError, EOFError):
        text = raw.decode("utf-8", "replace")

    origin = f"{src.name}:{country}"
    found = 0
    for line in text.splitlines():
        parts = line.split(",")
        if len(parts) < 3 or parts[2].strip().upper() != country:
            continue
        try:
            start = ipaddress.ip_address(parts[0].strip())
            end = ipaddress.ip_address(parts[1].strip())
        except ValueError:
            raise BuildError(f"{src.name}: malformed range {line[:80]!r}") from None
        for network in ipaddress.summarize_address_range(start, end):
            yield Entry("cidr", str(network), origin)
            found += 1
    if not found:
        raise BuildError(f"{src.name}: no records for {country}")


def load_dnsmasq_china(
    ctx: OriginContext, src: SourceConfig, _selector: str
) -> Iterator[Entry]:
    """Domains that resolve better through a Chinese DNS resolver.

    Format: ``server=/example.com/114.114.114.114``. The criterion is domestic
    presence (a Chinese edge/cache answers faster), not "Chinese company" — see
    the README for the measurement that backs treating them as direct.
    """
    text = ctx.source_text(src).decode("utf-8", "replace")
    for line in text.splitlines():
        entry = line.split("#", 1)[0].strip()
        if not entry.startswith("server=/"):
            continue
        body = entry[len("server=/") :]
        domain = body.rsplit("/", 1)[0].strip()
        if domain:
            yield Entry("suffix", domain, src.name)


# ---------------------------------------------------------------------------
# RIR delegated stats (APNIC / ARIN / RIPE NCC / LACNIC / AFRINIC)
# ---------------------------------------------------------------------------


def load_rir(ctx: OriginContext, src: SourceConfig, selector: str) -> Iterator[Entry]:
    country = selector.strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", country):
        raise BuildError(
            f"apnic: selector must be a two letter country code, got {selector!r}"
        )
    text = ctx.source_text(src).decode("utf-8", "replace")
    origin = f"{src.name}:{country}"
    found = 0
    for line in text.splitlines():
        if not line or line.startswith("#") or "|" not in line:
            continue
        fields = line.split("|")
        if len(fields) < 7:
            continue
        registry, cc, rtype, start, count, _date, status = fields[:7]
        if registry == "*" or cc != country:
            continue
        if status not in ("allocated", "assigned"):
            continue
        try:
            size = int(count)
        except ValueError:
            raise BuildError(f"rir: malformed record {line[:80]!r}") from None
        if rtype == "ipv4":
            first = ipaddress.IPv4Address(start)
            if size and size & (size - 1) == 0:
                prefixlen = 32 - (size.bit_length() - 1)
                yield Entry("cidr", f"{first}/{prefixlen}", origin)
            else:
                for network in ipaddress.summarize_address_range(
                    first, first + size - 1
                ):
                    yield Entry("cidr", str(network), origin)
            found += 1
        elif rtype == "ipv6":
            yield Entry("cidr", f"{ipaddress.IPv6Address(start)}/{size}", origin)
            found += 1
    if not found:
        log(f"rir: {src.name} has no records for {country}", "warn")


# ---------------------------------------------------------------------------
# Official service endpoints
# ---------------------------------------------------------------------------


def load_cidr(ctx: OriginContext, src: SourceConfig, _selector: str) -> Iterator[Entry]:
    text = ctx.source_text(src).decode("utf-8", "replace")
    origin = src.name
    for line in text.splitlines():
        token = line.split("#", 1)[0].strip()
        if not token:
            continue
        yield Entry("cidr", token, origin)


def load_static(
    _ctx: OriginContext, src: SourceConfig, _selector: str
) -> Iterator[Entry]:
    entries = src.options.get("entries") or []
    if not isinstance(entries, list):
        raise BuildError(f"static: {src.name}: 'entries' must be a list")
    for item in entries:
        text = str(item).strip()
        if not text:
            continue
        try:
            ipaddress.ip_network(text, strict=False)
        except ValueError:
            yield Entry("suffix", text, src.name)
        else:
            yield Entry("cidr", text, src.name)


def load_domain_list(
    ctx: OriginContext, src: SourceConfig, _selector: str
) -> Iterator[Entry]:
    text = ctx.source_text(src).decode("utf-8", "replace")
    origin = src.name
    for line in text.splitlines():
        token = line.split("#", 1)[0].strip()
        if not token:
            continue
        kind, sep, value = token.partition(":")
        if sep and kind in ("domain", "suffix"):
            yield Entry("suffix", value, origin)
        elif sep and kind == "full":
            yield Entry("exact", value, origin)
        elif sep:
            ctx.dropped(origin, f"rule type {kind}", token)
        else:
            yield Entry("suffix", token, origin)


def load_ip2asn(
    ctx: OriginContext, src: SourceConfig, selector: str
) -> Iterator[Entry]:
    """ASN prefixes from iptoasn.com (``start\\tend\\tASN\\tCC\\tdescription``)."""
    asn = selector.strip().upper().removeprefix("AS")
    if not asn.isdigit():
        raise BuildError(f"ip2asn: selector must be an ASN, got {selector!r}")
    text = ctx.memoize(f"ip2asn:{src.name}", lambda: _ip2asn_text(ctx, src))
    origin = f"as{asn}"
    found = 0
    for line in text.splitlines():
        fields = line.split("\t")
        if len(fields) < 3 or fields[2] != asn:
            continue
        try:
            start = ipaddress.ip_address(fields[0])
            end = ipaddress.ip_address(fields[1])
        except ValueError:
            raise BuildError(f"ip2asn: malformed range {line[:80]!r}") from None
        for network in ipaddress.summarize_address_range(start, end):
            yield Entry("cidr", str(network), origin)
            found += 1
    if not found:
        raise BuildError(f"ip2asn: AS{asn} has no prefix in {src.name}")


def _ip2asn_text(ctx: OriginContext, src: SourceConfig) -> str:
    raw = ctx.source_text(src)
    try:
        return gzip.decompress(raw).decode("utf-8", "replace")
    except (OSError, EOFError):
        return raw.decode("utf-8", "replace")


def load_iana_special(
    ctx: OriginContext, src: SourceConfig, _selector: str
) -> Iterator[Entry]:
    """Non-globally-reachable ranges from an IANA special-purpose registry.

    A parent block is only kept when none of its children is marked globally
    reachable: ``2001::/23`` (IETF protocol assignments) contains globally
    reachable blocks such as ``2001:3::/32``, so claiming the whole /23 would
    be wrong.
    """
    text = ctx.source_text(src).decode("utf-8", "replace")
    origin = src.name
    parsed: list[tuple[list[Network], bool | None]] = []
    for row in csv.DictReader(io.StringIO(text)):
        reach = _iana_flag(row.get("Globally Reachable"))
        block = _IANA_ANNOTATION.sub("", row.get("Address Block") or "")
        networks = []
        for part in block.split(","):
            token = part.strip()
            if not token:
                continue
            try:
                networks.append(ipaddress.ip_network(token, strict=False))
            except ValueError:
                raise BuildError(f"{origin}: invalid address block {token!r}") from None
        if networks:
            parsed.append((networks, reach))

    global_nets = [net for networks, reach in parsed if reach for net in networks]
    for networks, reach in parsed:
        if reach is not False:
            continue
        for net in networks:
            if any(child != net and _within(child, net) for child in global_nets):
                continue
            yield Entry("cidr", str(net), origin)


_IANA_ANNOTATION = re.compile(r"\[[^\]]*\]")


def _within(child: Network, parent: Network) -> bool:
    """``child.subnet_of(parent)`` without the IPv4/IPv6 union narrowing."""

    def span(net: Network) -> tuple[int, int, int]:
        return (net.version, int(net.network_address), int(net.broadcast_address))

    if child.version != parent.version:
        return False
    _, start, end = span(child)
    _, pstart, pend = span(parent)
    return pstart <= start and end <= pend


def _iana_flag(value: object) -> bool | None:
    """``True`` / ``False [1]`` / ``N/A`` / ``''`` -> bool or None."""
    text = _IANA_ANNOTATION.sub("", str(value or "")).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def load_cloudflare(
    ctx: OriginContext, src: SourceConfig, _selector: str
) -> Iterator[Entry]:
    payload = _json(ctx.source_text(src), "cloudflare")
    if not payload.get("success"):
        raise BuildError("cloudflare: API returned success=false")
    result = payload.get("result") or {}
    for key in ("ipv4_cidrs", "ipv6_cidrs"):
        for prefix in result.get(key) or []:
            yield Entry("cidr", str(prefix), "cloudflare")


def load_google_ipranges(
    ctx: OriginContext, src: SourceConfig, _selector: str
) -> Iterator[Entry]:
    payload = _json(ctx.source_text(src), "google_ipranges")
    prefixes = payload.get("prefixes")
    if not isinstance(prefixes, list):
        raise BuildError("google_ipranges: response has no 'prefixes' list")
    for item in prefixes:
        for key in ("ipv4Prefix", "ipv6Prefix"):
            if key in item:
                yield Entry("cidr", str(item[key]), "google")


def load_aws_ipranges(
    ctx: OriginContext, src: SourceConfig, selector: str
) -> Iterator[Entry]:
    """AWS public ranges; selector filters the ``service`` field (comma separated)."""
    payload = _json(ctx.source_text(src), "aws_ipranges")
    wanted = {part.strip().upper() for part in selector.split(",") if part.strip()}
    for key, field in (("prefixes", "ip_prefix"), ("ipv6_prefixes", "ipv6_prefix")):
        for item in payload.get(key) or []:
            service = str(item.get("service", "")).upper()
            if wanted and service not in wanted:
                continue
            prefix = item.get(field)
            if prefix:
                yield Entry("cidr", str(prefix), f"{src.name}:{service}")


def load_github_meta(
    ctx: OriginContext, src: SourceConfig, selector: str
) -> Iterator[Entry]:
    payload = _json(ctx.source_text(src), "github_meta")
    keys = [part.strip() for part in selector.split(",") if part.strip()]
    if not keys:
        keys = ["web", "api", "git", "pages", "packages", "hooks", "importer"]
    missing: list[str] = []
    for key in keys:
        values = payload.get(key)
        if not isinstance(values, list):
            missing.append(key)
            continue
        for prefix in values:
            yield Entry("cidr", str(prefix), f"github:{key}")
    if missing:
        ctx.note(f"github_meta: sections not present upstream: {', '.join(missing)}")


HANDLERS = {
    "dbip_country": load_dbip_country,
    "dlc": load_dlc,
    "dnsmasq_china": load_dnsmasq_china,
    "gfwlist": load_gfwlist,
    "rir": load_rir,
    "apnic": load_rir,  # legacy alias
    "ip2asn": load_ip2asn,
    "iana_special": load_iana_special,
    "cidr": load_cidr,
    "static": load_static,
    "domain_list": load_domain_list,
    "aws_ipranges": load_aws_ipranges,
    "cloudflare": load_cloudflare,
    "google_ipranges": load_google_ipranges,
    "github_meta": load_github_meta,
}
