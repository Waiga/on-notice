"""What a person gets back, and what they must never get back."""

import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from on_notice.cli import main  # noqa: E402
from on_notice.ingredients import read_ingredients  # noqa: E402
from on_notice.register import Register, load_register, normalise_name  # noqa: E402

SHIPPED = os.path.join(ROOT, "on_notice", "register.json")


def run(argv):
    out = io.StringIO()
    code = main(argv, out=out)
    return code, out.getvalue()


def write_register(payload):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    json.dump(payload, handle)
    handle.close()
    return handle.name


def write_list(text):
    handle = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8")
    handle.write(text)
    handle.close()
    return handle.name


class TestShippedRegister(unittest.TestCase):
    def test_triphenyl_phosphate_finds_the_january_2027_date(self):
        path = write_list("Aqua, Glycerin, Triphenyl Phosphate, Parfum")
        code, text = run([path])
        self.assertEqual(code, 1)
        self.assertIn("Triphenyl Phosphate", text)
        self.assertIn("1 January 2027", text)
        self.assertIn("cannot be placed on the Union market", text)
        # The rule restricts the substance, it does not ban it. The wording must
        # keep the qualifier, or a reader concludes the ingredient is prohibited.
        self.assertIn("products that do not meet the new restriction", text)
        self.assertIn("this tool cannot tell you which side of", text)

    def test_the_regulation_behind_the_date_is_named(self):
        path = write_list("Triphenyl Phosphate")
        _, text = run([path])
        self.assertIn("2026/909", text)

    def test_the_making_available_date_is_separate_from_the_placing_one(self):
        path = write_list("Triphenyl Phosphate")
        code, text = run(["--json", path])
        payload = json.loads(text)
        dates = {f["restriction"]: f["date"] for f in payload["findings"]}
        self.assertEqual(dates["placing"], "2027-01-01")
        self.assertEqual(dates["making_available"], "2028-07-01")

    def test_a_list_with_none_of_the_register_substances_finds_nothing(self):
        path = write_list("Aqua, Sodium Chloride, Glycerin, Citric Acid, Panthenol")
        code, text = run([path])
        self.assertEqual(code, 0)
        self.assertIn("None of these ingredients", text)

    def test_a_clean_result_still_says_what_was_checked(self):
        path = write_list("Aqua, Sodium Chloride")
        _, text = run([path])
        self.assertIn("Checked against", text)

    def test_no_run_claims_a_product_is_legal(self):
        for listing in ("Triphenyl Phosphate", "Aqua, Glycerin"):
            path = write_list(listing)
            _, text = run([path])
            lowered = text.lower()
            for word in ("compliant", "non-compliant", "legal", "illegal", "safe to sell"):
                self.assertNotIn(word, lowered)

    def test_every_run_says_what_it_could_not_see(self):
        path = write_list("Aqua")
        _, text = run([path])
        self.assertIn("What this check could not see", text)

    def test_the_register_itself_ships_no_past_dates(self):
        register = load_register(SHIPPED)
        boundary = register.data["scan_boundary"]["today"]
        for entry in register.entries:
            self.assertGreater(entry["date"], boundary)

    def test_the_register_records_its_own_provenance(self):
        register = load_register(SHIPPED)
        self.assertIn("celex_scanned", register.data)
        self.assertTrue(register.data["celex_scanned"])
        self.assertIn("source", register.data)
        self.assertIn("counts", register.data)
        self.assertIn("fetch_failures", register.data)


class TestUnresolvedIsSurfaced(unittest.TestCase):
    """An unresolved provision has to reach the reader, in both directions."""

    def setUp(self):
        self.register_path = write_register({
            "built": "2099-01-01",
            "counts": {"regulations_read": 1},
            "scan_boundary": {"today": "2099-01-01"},
            "fetch_failures": [],
            "unclassified_sentences": [],
            "unreadable_tables": [],
            "unresolved": [{
                "celex": "32099R0002",
                "regulation": "Commission Regulation (EU) 2099/2",
                "date": "2100-03-01",
                "restriction": "placing",
                "reason": "footnote marker (*4) is carried by no entry",
                "provision": "From 1 March 2100 cosmetic products containing these "
                             "substances shall not be placed on the Union market.",
            }],
            "entries": [],
        })

    def test_a_clean_looking_result_still_warns(self):
        path = write_list("Aqua, Glycerin")
        code, text = run(["--register", self.register_path, path])
        self.assertEqual(code, 0)
        self.assertIn("None of these ingredients", text)
        self.assertIn("could not be read from the text", text)

    def test_the_warning_is_not_hidden_behind_a_flag(self):
        path = write_list("Aqua")
        _, text = run(["--register", self.register_path, path])
        self.assertIn("1 dated restriction", text)

    def test_the_detail_is_available_and_complete(self):
        code, text = run(["--register", self.register_path, "--unresolved"])
        self.assertEqual(code, 0)
        self.assertIn("(*4)", text)
        self.assertIn("1 March 2100", text)
        self.assertIn("2099/2", text)

    def test_a_complete_register_says_so_plainly(self):
        empty = write_register({
            "built": "2099-01-01", "counts": {"regulations_read": 1},
            "scan_boundary": {"today": "2099-01-01"},
            "fetch_failures": [], "unclassified_sentences": [],
            "unreadable_tables": [], "unresolved": [], "entries": [],
        })
        path = write_list("Aqua")
        _, text = run(["--register", empty, path])
        self.assertIn("Nothing.", text)


class TestNameNormalisation(unittest.TestCase):
    def test_case_does_not_matter(self):
        self.assertEqual(normalise_name("TRIPHENYL PHOSPHATE"),
                         normalise_name("Triphenyl Phosphate"))

    def test_spacing_does_not_matter(self):
        self.assertEqual(normalise_name("Benzyl  Salicylate "),
                         normalise_name("Benzyl Salicylate"))

    def test_punctuation_does_not_matter(self):
        for variant in ("Triphenyl-Phosphate", "Triphenyl. Phosphate",
                        "TRIPHENYL_PHOSPHATE", "Triphenyl Phosphate"):
            self.assertEqual(normalise_name(variant), "triphenyl phosphate")

    def test_accents_are_folded(self):
        self.assertEqual(normalise_name("Caféine"), normalise_name("Cafeine"))

    def test_footnote_markers_are_not_part_of_the_name(self):
        self.assertEqual(normalise_name("Triphenyl Phosphate (*)"), "triphenyl phosphate")
        self.assertEqual(normalise_name("d-Limonene ( *1 )"), "d limonene")

    def test_variants_on_a_real_label_still_match(self):
        for variant in ("triphenyl phosphate", "TRIPHENYL PHOSPHATE",
                        "Triphenyl  Phosphate", "Triphenyl-Phosphate"):
            path = write_list("Aqua, {}, Glycerin".format(variant))
            code, text = run([path])
            self.assertEqual(code, 1, variant)
            self.assertIn("1 January 2027", text)


class TestIngredientReading(unittest.TestCase):
    def test_a_lead_in_is_dropped_but_ingredients_are_not(self):
        self.assertEqual(read_ingredients("Ingredients: Aqua, Glycerin"),
                         ["Aqua", "Glycerin"])

    def test_newlines_and_commas_both_separate(self):
        self.assertEqual(read_ingredients("Aqua\nGlycerin, Parfum"),
                         ["Aqua", "Glycerin", "Parfum"])

    def test_colour_index_groupings_survive_as_names(self):
        names = read_ingredients("Aqua, [+/- CI 77491, CI 77492]")
        self.assertIn("CI 77491", names)
        self.assertIn("CI 77492", names)

    def test_water_is_not_thrown_away(self):
        self.assertIn("Water", read_ingredients("Water, Retinol"))

    def test_a_repeated_name_is_listed_once(self):
        self.assertEqual(read_ingredients("Aqua, aqua, AQUA"), ["Aqua"])


class TestMatching(unittest.TestCase):
    def setUp(self):
        self.register = Register({
            "entries": [{
                "id": "x", "celex": "32099R0001",
                "regulation": "Commission Regulation (EU) 2099/1",
                "annex": "III", "entry_reference": "88",
                "inci_name": "Limonene", "chemical_name": "d-Limonene",
                "names": [{"name": "Limonene", "source": "inci_glossary",
                           "key": "limonene"}],
                "date": "2028-08-01", "stated_date": "2028-07-31", "basis": "until",
                "restriction": "making_available",
                "restriction_plain": "existing stock can no longer be sold in the Union",
                "resolution": "footnote marker (*1)", "provision": "a sentence",
            }],
        })

    def test_an_exact_name_matches_exactly(self):
        found = self.register.match("Limonene")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].match_type, "exact")

    def test_a_longer_label_name_containing_it_is_flagged_for_checking(self):
        found = self.register.match("Alpha-Limonene")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].match_type, "contained")

    def test_an_unrelated_name_does_not_match(self):
        self.assertEqual(self.register.match("Glycerin"), [])

    def test_a_partial_word_does_not_match(self):
        self.assertEqual(self.register.match("Limonenic Acid"), [])


if __name__ == "__main__":
    unittest.main()

class TestCategoryProvisionsAreReportedNotMatched(unittest.TestCase):
    """A restriction naming a class of ingredients cannot be matched to a label.

    Annex III entry 379 of Regulation 2026/909 reads "Aluminium-containing
    ingredients with the exception of those listed in entries 34, 50, ...".
    Matching that against a printed list would be false precision, and dropping
    it would be a silent gap. It is reported instead.
    """

    def test_a_clean_list_still_declares_the_category_gap(self):
        path = write_list("Aqua, Glycerin")
        code, text = run([path])
        self.assertEqual(code, 0)
        self.assertIn("What this check could not see", text)
        self.assertIn("name a class of ingredients", text)

    def test_category_entries_are_not_in_the_matchable_set(self):
        from on_notice.register import load_register
        register = load_register()
        for entry in register.entries:
            names = [n["name"] for n in entry.get("names") or []]
            self.assertFalse(
                all("with the exception of those listed" in n for n in names) and names,
                "a category entry reached the matchable set: " + entry["id"])
        self.assertTrue(register.uncheckable, "the category entries were dropped entirely")

