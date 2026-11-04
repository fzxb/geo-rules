from __future__ import annotations

import unittest

from geobuild.ips import IPSet, canonical


class IPSetTest(unittest.TestCase):
    def test_containment_is_collapsed(self):
        ips = IPSet()
        for value in ("10.0.0.0/8", "10.1.0.0/16", "10.1.2.3/32"):
            self.assertTrue(ips.add(value))
        self.assertEqual(ips.to_rule(), {"ip_cidr": ["10.0.0.0/8"]})

    def test_siblings_are_merged(self):
        ips = IPSet()
        for value in ("192.168.0.0/24", "192.168.1.0/24"):
            ips.add(value)
        self.assertEqual(ips.to_rule(), {"ip_cidr": ["192.168.0.0/23"]})

    def test_host_bits_are_normalised(self):
        ips = IPSet()
        ips.add("192.168.1.7/24")
        self.assertEqual(ips.to_rule(), {"ip_cidr": ["192.168.1.0/24"]})

    def test_mixed_families(self):
        ips = IPSet()
        ips.add("1.0.1.0/24")
        ips.add("2001:250::/32")
        self.assertEqual(ips.to_rule(), {"ip_cidr": ["1.0.1.0/24", "2001:250::/32"]})

    def test_invalid(self):
        ips = IPSet()
        self.assertFalse(ips.add("not-an-ip"))
        self.assertEqual(ips.rejects["invalid cidr"], 1)
        self.assertEqual(ips.to_rule(), {})

    def test_canonical_is_order_insensitive(self):
        self.assertEqual(
            canonical(["10.0.0.0/8", "10.1.0.0/16"]),
            canonical(["10.1.0.0/16", "10.0.0.0/8"]),
        )


if __name__ == "__main__":
    unittest.main()
