from __future__ import annotations

import unittest

from geobuild.domains import (
    DomainSet,
    InvalidDomain,
    IsIPAddress,
    covered_by,
    normalize_domain,
)


class NormalizeTest(unittest.TestCase):
    def test_lowercase_and_trim(self):
        self.assertEqual(normalize_domain("  Example.COM. "), "example.com")

    def test_wildcard_and_leading_dot(self):
        self.assertEqual(normalize_domain("*.example.com"), "example.com")
        self.assertEqual(normalize_domain(".example.com"), "example.com")

    def test_punycode(self):
        self.assertEqual(normalize_domain("xn--ngstr-lra8j.com"), "xn--ngstr-lra8j.com")
        self.assertEqual(normalize_domain("例子.测试"), "xn--fsqu00a.xn--0zwm56d")

    def test_single_label_tld(self):
        self.assertEqual(normalize_domain("cn"), "cn")

    def test_ip_is_not_a_domain(self):
        with self.assertRaises(IsIPAddress):
            normalize_domain("10.0.0.1")
        with self.assertRaises(IsIPAddress):
            normalize_domain("2001:db8::1")

    def test_invalid(self):
        for value in ("", "*.", "exa mple.com", "a/b", "x" * 64 + ".com"):
            with self.assertRaises(InvalidDomain, msg=value):
                normalize_domain(value)


class CoveredByTest(unittest.TestCase):
    def test_exact_and_subdomain(self):
        suffixes = {"example.com"}
        self.assertTrue(covered_by("example.com", suffixes))
        self.assertTrue(covered_by("a.b.example.com", suffixes))
        self.assertFalse(covered_by("notexample.com", suffixes))
        self.assertFalse(covered_by("example.org", suffixes))


class DomainSetTest(unittest.TestCase):
    def test_suffix_minimization(self):
        domains = DomainSet()
        for value in ("example.com", "a.example.com", "b.example.com", "example.org"):
            self.assertTrue(domains.add(value))
        domains.minimize()
        self.assertEqual(domains.suffixes, {"example.com", "example.org"})

    def test_exact_covered_by_suffix_is_removed(self):
        domains = DomainSet()
        domains.add("example.com", kind="suffix")
        domains.add("example.com", kind="exact")
        domains.add("only.example.org", kind="exact")
        domains.minimize()
        self.assertEqual(domains.exacts, {"only.example.org"})
        self.assertEqual(
            domains.to_rule(),
            {"domain": ["only.example.org"], "domain_suffix": ["example.com"]},
        )

    def test_tld_suffix_is_kept(self):
        domains = DomainSet()
        domains.add("cn")
        domains.add("example.com.cn")
        domains.minimize()
        self.assertEqual(domains.suffixes, {"cn"})

    def test_rejects_are_reported(self):
        domains = DomainSet()
        self.assertFalse(domains.add("10.0.0.1"))
        self.assertFalse(domains.add("bad domain"))
        self.assertEqual(sum(domains.rejects.values()), 2)
        self.assertTrue(domains.samples)

    def test_regex_is_kept_verbatim_and_sorted(self):
        domains = DomainSet()
        self.assertTrue(domains.add("^b\\.example$", kind="regex"))
        self.assertTrue(domains.add("^a\\.example$", kind="regex"))
        self.assertEqual(
            domains.to_rule()["domain_regex"],
            ["^a\\.example$", "^b\\.example$"],
        )
        self.assertEqual(domains.total, 2)

    def test_subtract_removes_covered_entries(self):
        left = DomainSet()
        for value in ("example.com", "a.example.com", "keep.example.org"):
            left.add(value)
        left.add("exact.example.net", kind="exact")
        blocked = DomainSet()
        blocked.add("example.com")
        blocked.add("exact.example.net")
        self.assertEqual(left.subtract(blocked), 3)
        self.assertEqual(left.suffixes, {"keep.example.org"})
        self.assertEqual(left.exacts, set())

    def test_union(self):
        left = DomainSet()
        left.add("example.com")
        right = DomainSet()
        right.add("a.example.com")
        right.add("example.net", kind="exact")
        left.update(right)
        left.minimize()
        self.assertEqual(left.suffixes, {"example.com"})
        self.assertEqual(left.exacts, {"example.net"})


if __name__ == "__main__":
    unittest.main()
