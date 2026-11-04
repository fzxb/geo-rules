"""IP prefix handling.

sing-box compiles ``ip_cidr`` into an immutable prefix set that is queried by
binary search, so the only thing we can optimise is the number of prefixes.
:func:`ipaddress.collapse_addresses` merges adjacent sibling prefixes and drops
prefixes already covered by a shorter one, which is exactly what we want: a
smaller, strictly equivalent set.
"""

from __future__ import annotations

import ipaddress
from collections import Counter, defaultdict
from dataclasses import dataclass, field

Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_network(raw: str) -> Network:
    return ipaddress.ip_network(raw.strip(), strict=False)


def is_network(raw: str) -> bool:
    try:
        parse_network(raw)
    except ValueError:
        return False
    return True


def _sort_key(network: Network) -> tuple[int, int, int]:
    return (network.version, int(network.network_address), network.prefixlen)


@dataclass
class IPSet:
    networks: set[Network] = field(default_factory=set)
    rejects: Counter = field(default_factory=Counter)
    samples: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    origins: Counter = field(default_factory=Counter)

    def add(self, raw: str, origin: str = "") -> bool:
        try:
            network = parse_network(raw)
        except ValueError:
            self.rejects["invalid cidr"] += 1
            bucket = self.samples["invalid cidr"]
            if len(bucket) < 5:
                bucket.append(raw)
            return False
        self.networks.add(network)
        if origin:
            self.origins[origin] += 1
        return True

    def update(self, other: IPSet) -> None:
        self.networks |= other.networks
        self.origins.update(other.origins)
        for reason, count in other.rejects.items():
            self.rejects[reason] += count
            for sample in other.samples.get(reason, ()):
                bucket = self.samples[reason]
                if len(bucket) < 5:
                    bucket.append(sample)

    def subtract(self, other: IPSet) -> int:
        """Remove prefixes fully contained in ``other``.

        Naive O(n*m): only meant for small exception sets, not for bulk diffs.
        """
        before = len(self.networks)
        kept: set[Network] = set()
        for network in self.networks:
            if any(
                network.version == candidate.version and network.subnet_of(candidate)
                for candidate in other.networks
            ):
                continue
            kept.add(network)
        self.networks = kept
        return before - len(kept)

    def collapsed(self) -> list[Network]:
        v4 = [network for network in self.networks if network.version == 4]
        v6 = [network for network in self.networks if network.version == 6]
        merged = list(ipaddress.collapse_addresses(v4)) + list(
            ipaddress.collapse_addresses(v6)
        )
        return sorted(merged, key=_sort_key)

    def to_rule(self) -> dict[str, list[str]]:
        prefixes = self.collapsed()
        if not prefixes:
            return {}
        return {"ip_cidr": [str(network) for network in prefixes]}

    @property
    def total(self) -> int:
        return len(self.networks)

    def __len__(self) -> int:
        return self.total


def canonical(prefixes: list[str]) -> list[str]:
    """Collapse and sort a prefix list, for set comparison."""
    networks = [parse_network(prefix) for prefix in prefixes]
    v4 = [network for network in networks if network.version == 4]
    v6 = [network for network in networks if network.version == 6]
    merged = list(ipaddress.collapse_addresses(v4)) + list(
        ipaddress.collapse_addresses(v6)
    )
    return [str(network) for network in sorted(merged, key=_sort_key)]
