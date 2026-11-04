"""Domain normalisation and set algebra.

Everything that ends up in a rule-set must be a lowercase, ASCII (punycode)
domain, because sing-box matches the wire format byte-for-byte and does not
perform IDNA conversion.

Set algebra is deliberately "suffix aware": ``a.example.com`` is redundant when
``example.com`` is already a suffix of the same set, and an exact ``domain``
entry is redundant when a suffix covers it. Removing those duplicates is a
cheap size win (typically 5-10% of the entries, more when lists overlap) and
it also shrinks the suffix trie sing-box builds at load time.
"""

from __future__ import annotations

import ipaddress
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

_LABEL_RE = re.compile(r"^[a-z0-9_-]{1,63}$")


class InvalidDomain(ValueError):
    """Raised when a token cannot be represented as a rule-set domain."""


class IsIPAddress(InvalidDomain):
    """The token is an IP address, not a domain."""

    def __init__(self, value: str) -> None:
        super().__init__("ip address")
        self.value = value


def _to_ascii(value: str) -> str:
    try:
        return value.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise InvalidDomain(f"idna: {exc}") from None


def normalize_domain(raw: str) -> str:
    """Return the canonical form of ``raw`` or raise :class:`InvalidDomain`."""
    value = raw.strip()
    if not value:
        raise InvalidDomain("empty")
    value = value.lower()
    value = value.removeprefix("*.")
    value = value.strip(".")
    if not value:
        raise InvalidDomain("empty")
    if "/" in value or " " in value:
        raise InvalidDomain("invalid characters")

    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        raise IsIPAddress(value)

    if not value.isascii():
        value = _to_ascii(value)

    for label in value.split("."):
        if not _LABEL_RE.match(label):
            raise InvalidDomain(f"invalid label {label!r}")
    if len(value) > 253:
        raise InvalidDomain("domain too long")
    return value


def covered_by(domain: str, suffixes: set[str]) -> bool:
    """True when ``domain`` equals a suffix or is a subdomain of one."""
    if domain in suffixes:
        return True
    parts = domain.split(".")
    return any(".".join(parts[index:]) in suffixes for index in range(1, len(parts)))


@dataclass
class DomainSet:
    suffixes: set[str] = field(default_factory=set)
    exacts: set[str] = field(default_factory=set)
    regexes: set[str] = field(default_factory=set)
    rejects: Counter = field(default_factory=Counter)
    samples: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    origins: Counter = field(default_factory=Counter)

    # -- building ----------------------------------------------------------

    def add(self, raw: str, kind: str = "suffix", origin: str = "") -> bool:
        if kind == "regex":
            # Patterns are emitted verbatim (already anchored by the caller);
            # they are never normalised, because IDNA/lowercasing would change
            # their meaning.
            value = raw.strip()
            if not value:
                self._reject("empty regex", raw)
                return False
            self.regexes.add(value)
            if origin:
                self.origins[origin] += 1
            return True
        try:
            value = normalize_domain(raw)
        except IsIPAddress as exc:
            self._reject("ip address in domain list", exc.value)
            return False
        except InvalidDomain as exc:
            self._reject(str(exc).split(":")[0][:48], raw)
            return False
        if kind == "exact":
            self.exacts.add(value)
        else:
            self.suffixes.add(value)
        if origin:
            self.origins[origin] += 1
        return True

    def update(self, other: DomainSet) -> None:
        self.suffixes |= other.suffixes
        self.exacts |= other.exacts
        self.regexes |= other.regexes
        self.origins.update(other.origins)
        for reason, count in other.rejects.items():
            self.rejects[reason] += count
            for sample in other.samples.get(reason, ()):
                self._sample(reason, sample)

    def subtract(self, other: DomainSet) -> int:
        """Remove everything covered by ``other`` (used for cn minus gfw)."""
        before = len(self.suffixes) + len(self.exacts)
        self.suffixes = {
            suffix for suffix in self.suffixes if not covered_by(suffix, other.suffixes)
        }
        self.exacts = {
            item
            for item in self.exacts
            if item not in other.exacts and not covered_by(item, other.suffixes)
        }
        return before - (len(self.suffixes) + len(self.exacts))

    def _reject(self, reason: str, value: str) -> None:
        self.rejects[reason] += 1
        self._sample(reason, value)

    def _sample(self, reason: str, value: str) -> None:
        bucket = self.samples[reason]
        if len(bucket) < 5:
            bucket.append(value)

    # -- output ------------------------------------------------------------

    def minimize(self) -> None:
        """Drop entries already covered by a shorter suffix in the same set."""
        if self.suffixes:
            suffixes = self.suffixes
            kept: set[str] = set()
            for suffix in suffixes:
                parts = suffix.split(".")
                if not any(
                    ".".join(parts[index:]) in suffixes
                    for index in range(1, len(parts))
                ):
                    kept.add(suffix)
            self.suffixes = kept
        if self.suffixes and self.exacts:
            self.exacts = {
                item for item in self.exacts if not covered_by(item, self.suffixes)
            }

    def to_rule(self) -> dict[str, list[str]]:
        rule: dict[str, list[str]] = {}
        if self.exacts:
            rule["domain"] = sorted(self.exacts)
        if self.suffixes:
            rule["domain_suffix"] = sorted(self.suffixes)
        if self.regexes:
            rule["domain_regex"] = sorted(self.regexes)
        return rule

    @property
    def total(self) -> int:
        return len(self.exacts) + len(self.suffixes) + len(self.regexes)

    def __len__(self) -> int:
        return self.total


def overlap(source: DomainSet, reference: DomainSet) -> list[str]:
    """Suffixes of ``source`` that are fully covered by ``reference``."""
    return [
        suffix for suffix in source.suffixes if covered_by(suffix, reference.suffixes)
    ]
