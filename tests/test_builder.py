"""The builder has one job it must never get wrong: staying loud about gaps."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import build_register as builder  # noqa: E402
from tests import fixtures  # noqa: E402


class TestAnnexReading(unittest.TestCase):
    def setUp(self):
        self.result = builder.analyse("32099R0001", fixtures.ANNEX_TABLE)

    def test_footnote_marker_is_linked_to_the_entry_carrying_it(self):
        names = {r["chemical_name"] for r in self.result["records"]}
        self.assertIn("Triphenyl Phosphate", names)

    def test_both_dates_in_one_footnote_are_kept_apart(self):
        triphenyl = [r for r in self.result["records"]
                     if r["chemical_name"] == "Triphenyl Phosphate"]
        by_restriction = {r["restriction"]: r["date"] for r in triphenyl}
        self.assertEqual(by_restriction["placing"], "2027-01-01")
        self.assertEqual(by_restriction["making_available"], "2028-07-01")

    def test_these_substances_resolves_through_the_marker(self):
        benzyl = [r for r in self.result["records"] if r["inci_name"] == "Benzyl Salicylate"]
        self.assertTrue(benzyl)
        self.assertIn("these substances", benzyl[0]["provision"])
        self.assertEqual(benzyl[0]["date"], "2027-01-01")

    def test_the_glossary_column_is_the_match_key(self):
        benzyl = [r for r in self.result["records"] if r["inci_name"] == "Benzyl Salicylate"][0]
        keys = [n["key"] for n in benzyl["names"] if n["source"] == "inci_glossary"]
        self.assertIn("benzyl salicylate", keys)

    def test_annexes_are_attributed_separately(self):
        annexes = {r["chemical_name"] or r["inci_name"]: r["annex"]
                   for r in self.result["records"]}
        self.assertEqual(annexes["Triphenyl Phosphate"], "II")
        self.assertEqual(annexes["2-hydroxybenzoic acid phenylmethyl ester"], "III")

    def test_nothing_was_left_unexplained(self):
        self.assertEqual(self.result["unresolved"], [])
        self.assertEqual(self.result["unclassified"], [])
        self.assertEqual(self.result["unreadable_tables"], [])


class TestUnresolvedIsNeverSwallowed(unittest.TestCase):
    """A footnote nobody carries must become a loud unknown, not a silent nothing."""

    def setUp(self):
        self.result = builder.analyse("32099R0002", fixtures.ORPHAN_FOOTNOTE)

    def test_the_provision_is_reported_as_unresolved(self):
        self.assertEqual(len(self.result["unresolved"]), 1)

    def test_it_is_not_attached_to_an_unrelated_substance(self):
        self.assertEqual(self.result["records"], [])

    def test_the_reason_and_the_full_sentence_are_kept(self):
        item = self.result["unresolved"][0]
        self.assertEqual(item["date"], "2028-03-01")
        self.assertIn("(*4)", item["reason"])
        self.assertIn("1 March 2028", item["provision"])

    def test_the_provision_was_still_counted(self):
        self.assertEqual(self.result["provisions_found"], 1)


class TestUntilForm(unittest.TestCase):
    """A last lawful day is not the same as a first restricted day."""

    def setUp(self):
        self.result = builder.analyse("32099R0003", fixtures.UNTIL_FORM)

    def test_the_deadline_is_the_day_after_the_stated_one(self):
        making = [r for r in self.result["records"]
                  if r["restriction"] == "making_available"]
        self.assertEqual(len(making), 1)
        self.assertEqual(making[0]["stated_date"], "2028-07-31")
        self.assertEqual(making[0]["date"], "2028-08-01")
        self.assertEqual(making[0]["basis"], "until")

    def test_the_older_footnote_markup_still_links(self):
        self.assertTrue(all(r["inci_name"] == "Limonene" for r in self.result["records"]))


class TestMarkers(unittest.TestCase):
    def test_spacing_inside_a_marker_does_not_change_it(self):
        self.assertEqual(builder.markers_in("Something ( *1 )"), {"(*1)"})
        self.assertEqual(builder.markers_in("Something (*1)"), {"(*1)"})
        self.assertEqual(builder.markers_in("Something ( ** )"), {"(**)"})

    def test_star_counts_do_not_collide(self):
        self.assertEqual(builder.markers_in("a (*) b (**) c (***)"),
                         {"(*)", "(**)", "(***)"})

    def test_an_ordinary_reference_is_not_a_transitional_marker(self):
        self.assertEqual(builder.markers_in("Benzyl alcohol ( 7 )"), set())


class TestBadDocumentGuard(unittest.TestCase):
    """A short or wrong response must fail, not read as a regulation with no dates."""

    def test_an_empty_response_is_refused(self):
        with self.assertRaises(builder.BadDocument):
            builder.check_document("32099R0001", "")

    def test_a_short_response_is_refused(self):
        with self.assertRaises(builder.BadDocument):
            builder.check_document("32099R0001", "<html><body>rate limited</body></html>")

    def test_a_long_page_without_journal_markup_is_refused(self):
        with self.assertRaises(builder.BadDocument):
            builder.check_document("32099R0001", "<body>" + ("x" * 30000) + "</body>")

    def test_a_real_looking_document_passes(self):
        markup = "<body>" + ("x" * 30000) + '<p class="oj-normal">text</p></body>'
        self.assertEqual(builder.check_document("32099R0001", markup), markup)


class TestUnclassifiedTripwire(unittest.TestCase):
    def test_a_dated_market_sentence_nobody_claimed_is_reported(self):
        text = ("From 1 May 2030 cosmetic products shall be withdrawn from the Union "
                "market by their manufacturers.")
        provisions = builder.find_provisions(text, "article")
        self.assertEqual(provisions, [])
        left = builder.unclassified_mentions(text, provisions, "article")
        self.assertEqual(len(left), 1)
        self.assertIn("1 May 2030", left[0]["sentence"])

    def test_a_sentence_a_construction_claimed_is_not_reported_twice(self):
        text = ("From 1 May 2030 cosmetic products containing that substance shall not "
                "be placed on the Union market.")
        provisions = builder.find_provisions(text, "article")
        self.assertEqual(len(provisions), 1)
        self.assertEqual(builder.unclassified_mentions(text, provisions, "article"), [])


if __name__ == "__main__":
    unittest.main()
