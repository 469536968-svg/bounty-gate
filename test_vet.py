#!/usr/bin/env python3
"""Offline tests for vet.py. No network. Run: python3 test_vet.py"""
import unittest

from vet import assess, max_amount, parse_ref, rails_in


class TestParse(unittest.TestCase):
    def test_url(self):
        self.assertEqual(parse_ref("https://github.com/o/r/issues/42"), ("o", "r", 42))

    def test_short(self):
        self.assertEqual(parse_ref("o/r#42"), ("o", "r", 42))

    def test_garbage(self):
        with self.assertRaises(ValueError):
            parse_ref("not a ref")


class TestAmounts(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(max_amount("Bounty $500 for this"), 500)

    def test_comma(self):
        self.assertEqual(max_amount("we pay $1,500"), 1500)

    def test_max_wins(self):
        self.assertEqual(max_amount("$100 or $3000 tier"), 3000)

    def test_out_of_range_rejected(self):
        self.assertEqual(max_amount("$99999999 jackpot"), 0)

    def test_none(self):
        self.assertEqual(max_amount(""), 0)


class TestRails(unittest.TestCase):
    def test_algora(self):
        self.assertIn("algora", rails_in("see https://algora.io/org/repo"))

    def test_none(self):
        self.assertEqual(rails_in("proposed, $500, will pay"), [])


def issue(login="alice", title="Do a thing", body=""):
    return {"title": title, "body": body, "user": {"login": login},
            "html_url": "https://github.com/o/r/issues/1"}


def pr(login):
    return {"user": {"login": login}, "number": 9, "title": "fix #1"}


class TestAssess(unittest.TestCase):
    def test_vetoes_on_occupancy_even_with_rail(self):
        r = assess(issue(body="algora.io $500"), [pr("bob")])
        self.assertEqual(r["verdict"], "OCCUPIED")
        self.assertLess(r["score"], 50)

    def test_self_dealt_detected(self):
        r = assess(issue(login="alice", body="algora.io $500"), [pr("alice")])
        self.assertTrue(r["self_dealt"])
        self.assertEqual(r["verdict"], "OCCUPIED")

    def test_no_rail(self):
        r = assess(issue(body="we should pay $500 someday"), [])
        self.assertEqual(r["verdict"], "NO-RAIL")
        self.assertEqual(r["rails"], [])

    def test_viable(self):
        r = assess(issue(body="Escrowed on algora.io, $500"), [])
        self.assertEqual(r["verdict"], "VIABLE")
        self.assertEqual(r["score"], 90.0)  # 50 base + 10 (amount 500) + 30 rail

    def test_viable_requires_amount_parse_to_be_useful(self):
        r = assess(issue(body="algora.io payout"), [])
        self.assertEqual(r["verdict"], "VIABLE")
        self.assertTrue(any("no parseable" in x for x in r["reasons"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
