from __future__ import annotations

import base64
import gzip
import unittest

from geobuild.config import SourceConfig
from geobuild.origins import (
    domain_regex_from_url,
    load_dbip_country,
    load_dlc,
    load_dnsmasq_china,
    load_gfwlist,
    load_github_meta,
    load_google_ipranges,
    load_iana_special,
    load_ip2asn,
    load_rir,
    parse_dlc_plain_yaml,
    split_dlc_rule,
)
from geobuild.util import BuildError


class FakeBuilder:
    """Minimal stand-in for :class:`geobuild.build.Builder`."""

    def __init__(self, payload: bytes = b"") -> None:
        self.payload = payload
        self.drops: list[tuple[str, str, str]] = []
        self.notes: list[str] = []

    def source_text(self, src: SourceConfig) -> bytes:
        del src
        return self.payload

    def fetch_url(self, url: str, src: SourceConfig) -> bytes:
        del url, src
        return self.payload

    def url_for(self, src: SourceConfig) -> str:
        del src
        return ""

    def fallback_url(self, src: SourceConfig) -> str:
        del src
        return "fallback"

    def memoize(self, key: str, factory):
        del key
        return factory()

    def dropped(self, origin: str, reason: str, value: str = "") -> None:
        self.drops.append((origin, reason, value))

    def note(self, message: str, level: str = "warn") -> None:
        del level
        self.notes.append(message)


def _src(name: str, kind: str) -> SourceConfig:
    return SourceConfig(name=name, kind=kind)


class DlcParserTest(unittest.TestCase):
    SAMPLE = """\
lists:
  - name: "cn"
    length: 3
    rules:
      - "domain:example.com"
      - "full:www.example.cn"
      - "domain:cn"
  - name: "odd"
    length: 1
    rules:
      - "regexp:^ad\\\\..+$"
"""

    def test_parse(self):
        lists = parse_dlc_plain_yaml(self.SAMPLE)
        self.assertEqual(
            lists["cn"], ["domain:example.com", "full:www.example.cn", "domain:cn"]
        )
        self.assertEqual(lists["odd"], ["regexp:^ad\\..+$"])

    def test_length_mismatch_fails(self):
        broken = self.SAMPLE.replace("length: 3", "length: 4")
        with self.assertRaises(BuildError):
            parse_dlc_plain_yaml(broken)


class DlcRuleTest(unittest.TestCase):
    def test_split_rule_with_attributes(self):
        self.assertEqual(
            split_dlc_rule("full:api.example.com:@ads,@telemetry"),
            ("full", "api.example.com", {"ads", "telemetry"}),
        )
        self.assertEqual(
            split_dlc_rule("domain:example.com:@!cn"),
            ("domain", "example.com", {"!cn"}),
        )
        self.assertEqual(
            split_dlc_rule("example.com"), ("domain", "example.com", set())
        )

    def test_wildcard_attribute_selector(self):
        text = """\
lists:
  - name: "alpha"
    length: 2
    rules:
      - "domain:a.example.com:@cn"
      - "domain:foreign.example.com"
  - name: "category-ads-extra"
    length: 1
    rules:
      - "domain:ad.example.net:@cn"
"""
        builder = FakeBuilder(text.encode("utf-8"))
        entries = list(load_dlc(builder, _src("dlc", "dlc"), "*@cn"))
        self.assertEqual(
            [(entry.kind, entry.value) for entry in entries],
            [("suffix", "a.example.com")],
            "only @cn entries, and ad lists must be skipped",
        )

    def test_wildcard_requires_attribute(self):
        builder = FakeBuilder(b"lists:\n")
        with self.assertRaises(BuildError):
            list(load_dlc(builder, _src("dlc", "dlc"), "*"))


class Ip2AsnTest(unittest.TestCase):
    TSV = (
        "1.0.0.0\t1.0.0.255\t13335\tAU\tCLOUDFLARENET\n"
        "1.0.4.0\t1.0.7.255\t38803\tAU\tWPL-AS-AP\n"
        "1.0.8.0\t1.0.15.255\t13335\tAU\tCLOUDFLARENET\n"
    )

    def _load(self, asn: str):
        payload = gzip.compress(self.TSV.encode())
        builder = FakeBuilder(payload)
        return list(load_ip2asn(builder, _src("bgp_v4", "ip2asn"), asn))

    def test_ranges_are_summarised(self):
        entries = self._load("13335")
        self.assertEqual([e.value for e in entries], ["1.0.0.0/24", "1.0.8.0/21"])

    def test_other_asn_is_ignored(self):
        self.assertEqual([e.value for e in self._load("38803")], ["1.0.4.0/22"])

    def test_unknown_asn_fails(self):
        with self.assertRaises(BuildError):
            self._load("64512")


class IanaSpecialTest(unittest.TestCase):
    CSV = (
        "Address Block,Name,RFC,Allocation Date,Termination Date,Source,"
        "Destination,Forwardable,Globally Reachable,Reserved-by-Protocol\n"
        "10.0.0.0/8,Private-Use,[RFC 1918],1996-02,N/A,True,True,True,False,False\n"
        '"192.0.0.170/32, 192.0.0.171/32",NAT64,[RFC 8215],2017-06,N/A,'
        "True,True,False,False,False\n"
        "64:ff9b::/96,NAT64,[RFC 6052],2010-10,N/A,True,True,True,True,False\n"
        "192.0.0.0/24 [2],IETF,[RFC 6890],2013-04,N/A,True,True,False,False,False\n"
    )

    def test_parent_with_a_global_child_is_dropped(self):
        csv_text = (
            "Address Block,Name,RFC,Allocation Date,Termination Date,Source,"
            "Destination,Forwardable,Globally Reachable,Reserved-by-Protocol\n"
            "2001::/23,IETF Protocol Assignments,[RFC 2928],2000-09,N/A,"
            "True,True,False,False [1],False\n"
            "2001:3::/32,AMT,[RFC 7450],2015-01,N/A,True,True,True,True,False\n"
            "fc00::/7,Unique-Local,[RFC 4193],2005-10,N/A,True,True,True,False [4],False\n"
        )
        builder = FakeBuilder(csv_text.encode())
        entries = list(load_iana_special(builder, _src("iana_v6", "iana_special"), ""))
        self.assertEqual([e.value for e in entries], ["fc00::/7"])

    def test_only_non_globally_reachable_rows(self):
        builder = FakeBuilder(self.CSV.encode())
        entries = list(load_iana_special(builder, _src("iana_v4", "iana_special"), ""))
        self.assertEqual(
            [e.value for e in entries],
            ["10.0.0.0/8", "192.0.0.170/32", "192.0.0.171/32", "192.0.0.0/24"],
        )


class GfwlistTest(unittest.TestCase):
    def _load(self, lines: list[str]):
        text = "[AutoProxy 0.2.9]\n! comment\n" + "\n".join(lines) + "\n"
        builder = FakeBuilder(text.encode("utf-8"))
        entries = list(load_gfwlist(builder, _src("gfwlist", "gfwlist"), ""))
        return builder, entries

    def test_plain_blocked(self):
        _builder, entries = self._load(["||example.com", "|http://site.org/path"])
        self.assertIn(("suffix", "example.com"), [(e.kind, e.value) for e in entries])
        self.assertIn(("suffix", "site.org"), [(e.kind, e.value) for e in entries])

    def test_base64_input(self):
        text = "[AutoProxy 0.2.9]\n||example.com\n"
        builder = FakeBuilder(base64.b64encode(text.encode("utf-8")))
        entries = list(load_gfwlist(builder, _src("gfwlist", "gfwlist"), ""))
        self.assertEqual(
            [(e.kind, e.value) for e in entries], [("suffix", "example.com")]
        )

    def test_allow_removes_exact_match(self):
        builder, entries = self._load(["||example.com", "@@||example.com"])
        self.assertEqual([(e.kind, e.value) for e in entries], [])
        self.assertTrue(
            any("allowed by @@" in reason for _, reason, _ in builder.drops)
        )

    def test_allow_narrower_than_block_is_kept(self):
        builder, entries = self._load(["||example.com", "@@||www.example.com"])
        self.assertEqual(
            [(e.kind, e.value) for e in entries], [("suffix", "example.com")]
        )
        self.assertTrue(builder.notes)

    def test_url_regex_is_mapped_onto_the_domain(self):
        _builder, entries = self._load(["/^https?:\\/\\/x\\.com/"])
        self.assertEqual(
            [(entry.kind, entry.value) for entry in entries], [("regex", "x\\.com")]
        )

    def test_unmappable_regex_is_recorded(self):
        # Lookarounds are unsupported by RE2, so this cannot be translated.
        builder, entries = self._load(["/^https?:\\/\\/(?=.*foo)[a-z]+\\.com$/"])
        self.assertEqual(entries, [])
        self.assertTrue(
            any("cannot be mapped" in reason for _, reason, _ in builder.drops)
        )

    def test_glob_keeps_its_meaning_as_regex(self):
        _builder, entries = self._load(["||fbcdn*.akamaihd.net"])
        self.assertEqual(
            [(entry.kind, entry.value) for entry in entries],
            [("regex", "^fbcdn.*\\.akamaihd\\.net$")],
        )

    def test_allow_regex_is_not_applied(self):
        builder, entries = self._load(
            ["||example.com", "@@/^https?:\\/\\/x\\.example\\.com/"]
        )
        self.assertEqual([entry.value for entry in entries], ["example.com"])
        self.assertTrue(any("regexp" in reason for _, reason, _ in builder.drops))

    def test_ip_entry(self):
        _builder, entries = self._load(["|http://85.17.73.31/"])
        self.assertEqual(
            [(e.kind, e.value) for e in entries], [("cidr", "85.17.73.31")]
        )

    def test_wildcard_suffix(self):
        _builder, entries = self._load(["||*.tokenplus.app"])
        self.assertEqual(
            [(e.kind, e.value) for e in entries], [("suffix", "tokenplus.app")]
        )

    def test_wildcard_block_is_reported_as_widened(self):
        builder, entries = self._load(["||*.example.com"])
        self.assertEqual([e.value for e in entries], ["example.com"])
        self.assertTrue(
            any("widened to the parent domain" in note for note in builder.notes)
        )

    def test_wildcard_allow_does_not_unblock_the_apex(self):
        # "@@||*.example.com" exempts subdomains only; the apex stays blocked.
        _builder, entries = self._load(["||example.com", "@@||*.example.com"])
        self.assertEqual(
            [(e.kind, e.value) for e in entries], [("suffix", "example.com")]
        )

    def test_wildcard_allow_removes_covered_subdomain(self):
        builder, entries = self._load(["||api.example.com", "@@||*.example.com"])
        self.assertEqual(entries, [])
        self.assertTrue(
            any("allowed by @@" in reason for _, reason, _ in builder.drops)
        )

    def test_unparsable_line_is_recorded(self):
        builder, entries = self._load(["|http://", "||example.com"])
        self.assertEqual([e.value for e in entries], ["example.com"])
        self.assertTrue(any(reason == "unparsable" for _, reason, _ in builder.drops))


class DbipCountryTest(unittest.TestCase):
    CSV = (
        b"1.0.0.0,1.0.0.255,AU\n"
        b"1.0.1.0,1.0.3.255,CN\n"
        b"8.128.0.0,8.128.0.255,CN\n"
        b"2001:250::,2001:250:ffff:ffff:ffff:ffff:ffff:ffff,CN\n"
    )

    def _entries(self, builder=None, country="CN"):
        builder = builder or FakeBuilder(gzip.compress(self.CSV))
        return builder, list(
            load_dbip_country(builder, _src("geo_cn", "dbip_country"), country)
        )

    def test_parse_v4_and_v6(self):
        _builder, entries = self._entries()
        self.assertEqual(
            [(entry.kind, entry.value) for entry in entries],
            [
                ("cidr", "1.0.1.0/24"),
                ("cidr", "1.0.2.0/23"),
                ("cidr", "8.128.0.0/24"),
                ("cidr", "2001:250::/32"),
            ],
        )

    def test_other_country_is_ignored(self):
        _builder, entries = self._entries(country="AU")
        self.assertEqual([entry.value for entry in entries], ["1.0.0.0/24"])

    def test_missing_current_month_falls_back(self):
        class FallbackBuilder(FakeBuilder):
            def source_text(self, src):
                raise BuildError("GET current-month failed: HTTP 404")

            def fetch_url(self, url, src):
                self.fetched = url
                return self.payload

        builder = FallbackBuilder(gzip.compress(self.CSV))
        source = SourceConfig(
            name="geo_cn",
            kind="dbip_country",
            url_fallback="https://example.invalid/fallback.csv.gz",
        )
        entries = list(load_dbip_country(builder, source, "CN"))
        self.assertEqual(builder.fetched, "fallback")
        self.assertEqual(len(entries), 4)

    def test_unknown_country_fails(self):
        builder = FakeBuilder(gzip.compress(self.CSV))
        with self.assertRaises(BuildError):
            list(load_dbip_country(builder, _src("geo_cn", "dbip_country"), "ZZ"))


class DnsmasqChinaTest(unittest.TestCase):
    SAMPLE = b"""\
# comment
server=/example.com/114.114.114.114
server=/sub.example.org/114.114.114.114 # trailing
server=/bad
"""

    def test_parse(self):
        builder = FakeBuilder(self.SAMPLE)
        entries = list(
            load_dnsmasq_china(builder, _src("china_domain", "dnsmasq_china"), "")
        )
        self.assertEqual(
            [entry.value for entry in entries],
            ["example.com", "sub.example.org", "bad"],
        )


class DomainRegexTest(unittest.TestCase):
    def test_url_anchor_is_stripped(self):
        self.assertEqual(
            domain_regex_from_url("/^https?:\\/\\/[^\\/]+blogspot\\.(.*)/"),
            "[^/]+blogspot\\.(.*)",
        )

    def test_non_url_patterns_are_rejected(self):
        for pattern in ("/^foo\\./", "/^https?:\\/\\/(?=x)/", "/^https?:\\/\\/a/\\d/"):
            with self.subTest(pattern=pattern):
                self.assertIsNone(domain_regex_from_url(pattern))


class ApnicTest(unittest.TestCase):
    SAMPLE = b"""\
# comment
apnic|*|ipv4|*|10|summary
apnic|CN|ipv4|1.0.1.0|256|20110414|allocated
apnic|CN|ipv4|1.0.2.0|512|20110414|allocated
apnic|CN|ipv4|1.0.3.0|3|20110414|assigned
apnic|CN|ipv4|1.0.9.0|256|20110414|reserved
apnic|JP|ipv4|1.0.16.0|4096|20110414|allocated
apnic|CN|ipv6|2001:250::|32|20030326|allocated
apnic|CN|asn|1234|1|20110414|allocated
"""

    def test_parse(self):
        builder = FakeBuilder(self.SAMPLE)
        entries = list(load_rir(builder, _src("apnic", "apnic"), "CN"))
        values = [entry.value for entry in entries]
        self.assertIn("1.0.1.0/24", values)
        self.assertIn("1.0.2.0/23", values)
        self.assertIn("2001:250::/32", values)
        self.assertFalse(any(value.startswith("1.0.9.") for value in values))
        self.assertFalse(any(value.startswith("1.0.16.") for value in values))
        self.assertNotIn("1.0.3.0/32", values)

    def test_unknown_country_yields_nothing(self):
        # 0 条是合法结果（LACNIC/AFRINIC 就没有 CN 记录），由构建层的
        # produced == 0 / expect_min 检查决定是否报错。
        builder = FakeBuilder(self.SAMPLE)
        self.assertEqual(list(load_rir(builder, _src("rir_apnic", "rir"), "ZZ")), [])


class OfficialJsonTest(unittest.TestCase):
    def test_google(self):
        builder = FakeBuilder(
            b'{"prefixes":[{"ipv4Prefix":"8.8.4.0/24"},{"ipv6Prefix":"2001:4860::/32"}]}'
        )
        entries = list(
            load_google_ipranges(builder, _src("google_ip", "google_ipranges"), "")
        )
        self.assertEqual([e.value for e in entries], ["8.8.4.0/24", "2001:4860::/32"])

    def test_github_defaults_skip_actions(self):
        builder = FakeBuilder(
            b'{"web":["1.1.1.0/24"],"api":["9.9.9.0/24"],"git":["2.2.2.0/24"],"pages":[],"packages":[],"hooks":[],"importer":[],"actions":["3.3.3.0/24"]}'
        )
        entries = list(load_github_meta(builder, _src("github_ip", "github_meta"), ""))
        self.assertEqual(
            [e.value for e in entries], ["1.1.1.0/24", "9.9.9.0/24", "2.2.2.0/24"]
        )


if __name__ == "__main__":
    unittest.main()
