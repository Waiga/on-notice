"""A synonym must never be counted as a substance.

The published table once carried a Geranial row beside a Citral row. They are
one substance under two glossary names, so the table invented a ninth substance,
understated Citral by three lists, and made the sentence "nine of the register's
fourteen substances" compare a name count against a substance denominator.

The register knows the difference: every entry carrying the name Geranial has an
``inci_name`` of Citral. Nothing was reading it. These tests read it, and fail if
a future register lets a second name for one substance become a second substance.
"""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from on_notice.register import load_register  # noqa: E402


class TestSubstanceIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = load_register()

    def test_geranial_is_citral(self):
        """The worked example, named in the README, pinned here."""
        carrying = [entry for entry in self.reg.entries
                    if any(n["name"] == "Geranial" for n in entry.get("names", []))]
        self.assertTrue(carrying, "no entry carries the name Geranial any more")
        for entry in carrying:
            self.assertEqual(self.reg.substance_of(entry), "Citral")

    def test_an_entry_without_an_inci_name_falls_back_to_the_chemical_name(self):
        """Annex II carries Triphenyl Phosphate with no INCI name at all."""
        without = [entry for entry in self.reg.entries if not entry.get("inci_name")]
        self.assertTrue(without, "every entry now has an INCI name; revisit this test")
        for entry in without:
            self.assertEqual(self.reg.substance_of(entry), entry["chemical_name"])

    def test_every_entry_resolves_to_a_substance(self):
        for entry in self.reg.entries:
            self.assertTrue(self.reg.substance_of(entry),
                            "entry {} names no substance".format(entry.get("id")))

    def test_one_name_never_belongs_to_two_substances(self):
        """The invariant that makes grouping by substance safe.

        If a single register name resolved to two substances, grouping by
        substance would be as wrong as grouping by name is, and no count in the
        README could be trusted. Nothing in the shipped register does this.
        """
        owners = {}
        for entry in self.reg.entries:
            substance = self.reg.substance_of(entry)
            for name in entry.get("names", []):
                key = name.get("key") or name["name"].lower()
                owners.setdefault(key, set()).add(substance)
        shared = {k: v for k, v in owners.items() if len(v) > 1}
        self.assertEqual(shared, {}, "these names belong to more than one substance")

    def test_the_substance_count_is_smaller_than_the_name_count(self):
        self.assertEqual(self.reg.distinct_substances(), 14)
        self.assertEqual(self.reg.distinct_names(), 49)
        self.assertLess(self.reg.distinct_substances(), self.reg.distinct_names())


class TestMeasurementGroupsBySubstance(unittest.TestCase):
    """A label printing Geranial and a label printing Citral are one substance.

    This walks the same path the measurement walks: read a printed list, match
    it, then group. It fails if the script ever goes back to grouping on the
    name that happened to match.
    """

    @classmethod
    def setUpClass(cls):
        cls.reg = load_register()

    def _substances(self, printed):
        from on_notice.ingredients import read_ingredients
        names = read_ingredients(printed)
        findings = self.reg.check(names) if hasattr(self.reg, "check") else self.reg.match(names)
        return sorted({self.reg.substance_of(f.entry) for f in findings})

    def test_a_label_printing_geranial_is_a_citral_label(self):
        self.assertEqual(self._substances("Aqua, Geranial, Glycerin"), ["Citral"])

    def test_a_label_printing_citral_is_the_same_substance(self):
        self.assertEqual(self._substances("Aqua, Citral, Glycerin"), ["Citral"])

    def test_a_label_printing_both_counts_one_substance_not_two(self):
        self.assertEqual(self._substances("Aqua, Citral, Geranial, Glycerin"), ["Citral"])

    def test_the_matched_name_is_still_the_name_the_label_printed(self):
        """Grouping changes the count, never what the user is told they wrote."""
        from on_notice.ingredients import read_ingredients
        names = read_ingredients("Aqua, Geranial, Glycerin")
        findings = self.reg.check(names) if hasattr(self.reg, "check") else self.reg.match(names)
        self.assertIn("Geranial", {f.matched_name for f in findings})


if __name__ == "__main__":
    unittest.main()
