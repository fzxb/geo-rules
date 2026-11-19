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

    def test_intersect_takes_the_more_specific_suffix(self):
        left = DomainSet()
        left.add("example.com")
        right = DomainSet()
        right.add("sub.example.com")
        result = left.intersect(right)
        self.assertEqual(result.suffixes, {"sub.example.com"})

    def test_intersect_suffix_with_exact_is_exact(self):
        left = DomainSet()
        left.add("example.com")
        right = DomainSet()
        right.add("www.example.com", kind="exact")
        result = left.intersect(right)
        self.assertEqual(result.suffixes, set())
        self.assertEqual(result.exacts, {"www.example.com"})

    def test_intersect_drops_unrelated_entries(self):
        left = DomainSet()
        left.add("example.com")
        right = DomainSet()
        right.add("example.net")
        self.assertEqual(left.intersect(right).total, 0)

    def test_intersect_keeps_matching_exacts(self):
        left = DomainSet()
        left.add("api.example.com", kind="exact")
        right = DomainSet()
        right.add("api.example.com", kind="exact")
        right.add("example.net", kind="exact")
        self.assertEqual(left.intersect(right).exacts, {"api.example.com"})

    def test_strict_subtract_removes_a_parent_that_covers_the_target(self):
        left = DomainSet()
        for value in ("example.com", "keep.example.org"):
            left.add(value)
        blocked = DomainSet()
        blocked.add("blocked.example.com")
        self.assertEqual(left.strict_subtract(blocked), 1)
        self.assertEqual(left.suffixes, {"keep.example.org"})
        self.assertTrue(left.is_disjoint(blocked))

    def test_strict_subtract_keeps_explicit_non_overlapping_children(self):
        left = DomainSet()
        left.add("cn")
        left.add("keep.cn")
        blocked = DomainSet()
        blocked.add("blocked.cn")
        _ = left.strict_subtract(blocked)
        left.minimize()
        self.assertEqual(left.suffixes, {"keep.cn"})
        self.assertTrue(left.is_disjoint(blocked))

    def test_strict_subtract_removes_entries_covered_by_target(self):
        left = DomainSet()
        left.add("a.example.com")
        left.add("keep.example.org")
        left.add("exact.example.com", kind="exact")
        blocked = DomainSet()
        blocked.add("example.com")
        _ = left.strict_subtract(blocked)
        self.assertEqual(left.suffixes, {"keep.example.org"})
        self.assertEqual(left.exacts, set())
        self.assertTrue(left.is_disjoint(blocked))

    def test_strict_subtract_keeps_exact_parent_of_exact_child(self):
        left = DomainSet()
        left.add("example.com", kind="exact")
        blocked = DomainSet()
        blocked.add("sub.example.com", kind="exact")
        self.assertEqual(left.strict_subtract(blocked), 0)
        self.assertEqual(left.exacts, {"example.com"})
        self.assertTrue(left.is_disjoint(blocked))

    def test_strict_subtract_does_not_remove_unrelated_parents(self):
        left = DomainSet()
        left.add("cn")
        blocked = DomainSet()
        blocked.add("example.net")
        self.assertEqual(left.strict_subtract(blocked), 0)
        self.assertEqual(left.suffixes, {"cn"})
        self.assertTrue(left.is_disjoint(blocked))


if __name__ == "__main__":
    unittest.main()
