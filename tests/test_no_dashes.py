"""No punctuation dash reaches a reader, and the two parsers keep the dashes they eat.

on-notice was the last tool in this set without this guard. Its output is clean
today: a scan of every renderer found no punctuation dash anywhere, and the only
dashes in the package sit inside two character classes that read input, where
they are required. Nothing stopped one coming back, so this is the test that
does.

Two halves, because either one alone leaves a hole.

The rendered half runs every renderer the README documents and reads what a
person would actually see: the text report, the JSON report, the ``--unresolved``
report, the help, the version, the refusal messages, and
``scripts/measure_corpus.py``, whose printed block the README quotes. It cannot
see a message no fixture here happens to trigger.

The source half reads the string constants in ``on_notice/`` and ``scripts/``
instead, so a dash typed into a line nothing here exercises still fails. It
walks the syntax tree rather than the tokens. From Python 3.12 an f-string
literal is split into ``FSTRING_MIDDLE`` tokens, which are not ``token.STRING``,
so a tokeniser looking only for ``STRING`` walks straight past a dash inside an
f-string; the syntax tree has no such version dependence. Comments never reach
the tree, and a docstring is identified by the node it opens and skipped,
because neither is printed.

Three further traps, each of which has produced a wrong answer in this set of
tools and each of which is closed here.

The ASCII spaced double hyphen prints as a dash to a reader and does not match a
search for the em dash, so it is scanned for by name alongside the real dash
characters.

``json.dumps`` escapes a non-ASCII character by default, so an em dash leaves a
JSON renderer as the six characters ``\\u2014``. A search of the raw text finds
nothing while the reader still sees a dash, so the JSON is parsed and its keys
and values walked.

Shell grep has returned a false negative for an em dash on a file that visibly
held one, so every file read here is read as bytes and decoded explicitly.

The inverse assertion is the one that matters most for this tool. Two character
classes are required to carry dashes: the set ``clean`` strips off an ingredient
name, and the class the register builder uses to recognise a table cell holding
only punctuation. Stripping the dash forms a pack prints off a name is correct,
and deleting any of them makes the parser worse. Both literals are exempted by
exact text, and the tests below assert they still hold every dash they need, so
a later tidy that removes one fails here rather than quietly degrading what the
tool can read.

The scanner allows nothing else. on-notice prints no bullet lists and no rule
lines, so it needs no layout exemption, and adding one would be a hole rather
than a convenience.

Only ``on_notice/`` and ``scripts/`` are read. This file is not: it has to name
the dash characters to look for them.
"""

import ast
import contextlib
import gzip
import io
import json
import os
import pathlib
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from on_notice.cli import build_parser, main  # noqa: E402
from on_notice.ingredients import clean, read_ingredients  # noqa: E402
from on_notice.register import load_register  # noqa: E402

EXAMPLES = os.path.join(ROOT, "examples")
SHIPPED = os.path.join(ROOT, "on_notice", "register.json")

# Every character a reader sees as a dash, plus the two ASCII sequences that
# print as one. The spaced double hyphen is the form that hides from a search for
# the em dash while reading identically on the page.
DASH_FORMS = {
    "em dash": "—",
    "en dash": "–",
    "figure dash": "‒",
    "horizontal bar": "―",
    "minus sign": "−",
    "non breaking hyphen": "‑",
    "spaced double hyphen": " -- ",
    "spaced hyphen": " - ",
}

# The two literals allowed to carry a dash, matched by exact text. Both read
# input; neither is ever printed. Editing either one breaks this exemption and
# fails the source test, and the inverse tests below say what each must keep.
INPUT_CHARACTER_CLASSES = {
    # on_notice/ingredients.py: what clean() strips off an ingredient name.
    " .:-–—",
    # scripts/build_register.py: a table cell holding only punctuation.
    "[-–—\\s.,;:%0-9/]+",
}


def punctuation_dashes(text):
    """Every dash in text that a reader would read as punctuation."""
    found = []
    for number, line in enumerate(text.splitlines(), start=1):
        for name in sorted(DASH_FORMS):
            if DASH_FORMS[name] in line:
                found.append("line {}: {} in {!r}".format(number, name, line.strip()))
    return found


def read_source(path):
    """A file as text, read as bytes and decoded here rather than by the platform."""
    return pathlib.Path(path).read_bytes().decode("utf-8")


def strings_in_json(blob):
    """Every string in a JSON document, keys included, one per line."""
    out = []

    def walk(node):
        if isinstance(node, str):
            out.append(node)
        elif isinstance(node, dict):
            for key, value in node.items():
                out.append(key)
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(blob))
    return "\n".join(out)


def printable_strings(source):
    """Every string literal in a module except the docstrings.

    A comment never reaches a reader and never reaches the syntax tree either. A
    docstring is found by the node it opens, which is stable across versions in a
    way that tokenising an f-string is not.
    """
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                docstrings.add(id(body[0].value))
    return [node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstrings]


def printable_modules():
    """The package, and the scripts that write what the package prints.

    scripts/build_register.py is here because the wording it files as
    restriction_plain is printed verbatim under every finding, and
    scripts/measure_corpus.py because the README quotes the block it prints.
    """
    return sorted(list((pathlib.Path(ROOT) / "on_notice").rglob("*.py"))
                  + list((pathlib.Path(ROOT) / "scripts").rglob("*.py")))


def run(argv):
    out = io.StringIO()
    errors = io.StringIO()
    with contextlib.redirect_stderr(errors):
        code = main(argv, out=out)
    return code, out.getvalue(), errors.getvalue()


def write_json(payload):
    handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                         encoding="utf-8")
    json.dump(payload, handle)
    handle.close()
    return handle.name


def register_declaring_every_gap():
    """A register carrying one of every kind of gap the reports can describe.

    The shipped register has no fetch failure, no unresolved provision and no
    unreadable table, so three of the lines in gaps() and three of the blocks in
    describe_unresolved() would never be rendered by a run over real data.
    """
    entry = {
        "id": "gap-1", "celex": "32099R0001",
        "regulation": "Commission Regulation (EU) 2099/1",
        "annex": "III", "entry_reference": "88",
        "inci_name": "Harmless Glycol", "chemical_name": "Some chemical name",
        "names": [{"name": "Harmless Glycol", "source": "inci_glossary",
                   "key": "harmless glycol"}],
        "date": "2100-01-01", "stated_date": "2100-01-01", "basis": "from",
        "restriction": "placing", "resolution": "footnote marker (*1)",
        "provision": "From 1 January 2100 cosmetic products containing these "
                     "substances shall not be placed on the Union market.",
    }
    return write_json({
        "built": "2099-01-01",
        "counts": {"regulations_read": 1, "regulations_listed": 2,
                   "dated_provisions_found": 4, "unresolved_provisions_total": 2,
                   "unresolved_provisions_shipped": 1},
        "scan_boundary": {"today": "2099-01-01"},
        "fetch_failures": [{
            "celex": "32099R0009",
            "error": "HTTP 500 from EUR-Lex",
            "consequence": "any deadline this regulation carries is missing here.",
        }],
        "unresolved": [{
            "celex": "32099R0002",
            "regulation": "Commission Regulation (EU) 2099/2",
            "date": "2100-03-01", "restriction": "placing",
            "reason": "footnote marker (*4) is carried by no entry",
            "provision": "From 1 March 2100 cosmetic products containing these "
                         "substances shall not be placed on the Union market.",
        }],
        "unreadable_tables": [{
            "celex": "32099R0003",
            "reason": "the table has no header row this reader recognises",
            "sample": "Reference number Substance identification",
        }],
        "unclassified_sentences": [{
            "celex": "32099R0004", "origin": "recital",
            "regulation": "Commission Regulation (EU) 2099/4",
            "sentence": "Article 2 shall apply from 27 November 2099.",
        }],
        "uncheckable": [dict(entry, id="gap-2")],
        "labelling_only": [dict(entry, id="gap-3")],
        "restriction_text_not_recovered": [dict(entry, id="gap-4")],
        "entries": [entry],
    })


# --- the rendered half: what a person actually sees ---------------------------


class TestRenderedOutputCarriesNoDash(unittest.TestCase):
    EXAMPLE_LISTS = ("night-cream.txt", "one-ingredient.txt", "plain-cleanser.txt")

    def check(self, label, text):
        self.assertTrue(text.strip(), "{} rendered nothing to check".format(label))
        self.assertEqual([], punctuation_dashes(text),
                         "{} carries a punctuation dash: {}".format(
                             label, punctuation_dashes(text)))

    def test_the_text_report(self):
        """Both branches: a list with findings on it, and a list with none."""
        for name in self.EXAMPLE_LISTS:
            path = os.path.join(EXAMPLES, name)
            for flags in ([], ["--before", "2027-12-31"]):
                with self.subTest(example=name, flags=flags):
                    _, text, _ = run(flags + [path])
                    self.check("{} {}".format(name, flags), text)

    def test_the_json_report(self):
        """Decoded, because json.dumps hides a dash from a search of the raw text."""
        for name in self.EXAMPLE_LISTS:
            with self.subTest(example=name):
                _, text, _ = run(["--json", os.path.join(EXAMPLES, name)])
                self.check("{} as json".format(name), strings_in_json(text))

    def test_the_report_read_from_standard_input(self):
        stdin = sys.stdin
        sys.stdin = io.StringIO("Aqua, Triphenyl Phosphate, Glycerin")
        try:
            _, text, _ = run(["-"])
        finally:
            sys.stdin = stdin
        self.check("standard input", text)

    def test_the_unresolved_report(self):
        _, text, _ = run(["--unresolved"])
        self.check("--unresolved", text)

    def test_every_kind_of_gap_this_tool_can_declare(self):
        path = register_declaring_every_gap()
        listing = os.path.join(EXAMPLES, "plain-cleanser.txt")

        _, text, _ = run(["--register", path, listing])
        self.assertIn("could not be downloaded", text)
        self.assertIn("name a class of ingredients", text)
        self.check("every gap, text", text)

        _, text, _ = run(["--register", path, "--unresolved"])
        self.assertIn("(*4)", text)
        self.check("every gap, --unresolved", text)

        _, text, _ = run(["--register", path, "--json", listing])
        self.check("every gap, json", strings_in_json(text))

    def test_the_help_and_the_usage(self):
        self.check("help", build_parser().format_help())
        self.check("usage", build_parser().format_usage())

    def test_the_version(self):
        with self.assertRaises(SystemExit):
            with contextlib.redirect_stdout(io.StringIO()) as printed:
                build_parser().parse_args(["--version"])
        self.check("--version", printed.getvalue())

    def test_the_refusal_messages(self):
        """What a reader sees when the run cannot happen is output too."""
        with tempfile.TemporaryDirectory() as folder:
            missing = os.path.join(folder, "no-such-register.json")
            code, _, errors = run(["--register", missing,
                                   os.path.join(EXAMPLES, "night-cream.txt")])
            self.assertEqual(2, code)
            self.check("missing register", errors)

            code, _, errors = run(["--before", "not a date",
                                   os.path.join(EXAMPLES, "night-cream.txt")])
            self.assertEqual(2, code)
            self.check("bad --before", errors)

            code, _, errors = run([os.path.join(folder, "no-such-list.txt")])
            self.assertEqual(2, code)
            self.check("missing ingredient list", errors)

    def test_the_corpus_measurement_the_readme_quotes(self):
        """scripts/measure_corpus.py prints the block printed in the README."""
        import measure_corpus

        header = ["code", "url", "product_name", "brands", "ingredients_text"]
        rows = [
            ["0001", "http://x/1", "Night Cream", "Acme",
             "Aqua, Benzyl Salicylate, Citral, Retinol"],
            ["0002", "http://x/2", "No List", "Acme", ""],
            ["0003", "http://x/3", "Cleanser", "Beta", "Aqua, Glycerin"],
        ]
        table = "\t".join(header) + "\n" + "\n".join("\t".join(r) for r in rows) + "\n"

        with tempfile.TemporaryDirectory() as folder:
            corpus = os.path.join(folder, "export.csv.gz")
            with gzip.open(corpus, "wb") as handle:
                handle.write(table.encode("utf-8"))

            argv = sys.argv
            sys.argv = ["measure_corpus.py", corpus]
            try:
                with contextlib.redirect_stdout(io.StringIO()) as printed:
                    measure_corpus.main()
            finally:
                sys.argv = argv

        text = printed.getvalue()
        self.assertIn("lists actually read", text)
        self.assertIn("top substances by number of lists naming them:", text)
        self.check("measure_corpus.py", text)


class TestTheShippedRegisterPrintsNoDash(unittest.TestCase):
    """The register quotes EUR-Lex, and some of what it quotes is printed.

    A dash arriving in a rebuilt register is a different problem from a dash
    typed into this repository, so it is named separately here. Every field
    below reaches a reader through render(), describe_unresolved() or the JSON.
    row_text is not among them and is not checked.
    """

    PRINTED_FIELDS = ("regulation", "annex", "entry_reference", "provision",
                      "restriction_plain", "resolution", "celex", "inci_name",
                      "chemical_name", "stated_date", "basis", "restriction", "date")

    def test_no_entry_prints_a_dash(self):
        register = load_register(SHIPPED)
        for entry in register.entries:
            for field in self.PRINTED_FIELDS:
                value = entry.get(field)
                if isinstance(value, str):
                    self.assertEqual([], punctuation_dashes(value),
                                     "entry {} field {}".format(entry["id"], field))
            for name in entry.get("names") or []:
                self.assertEqual([], punctuation_dashes(name["name"]),
                                 "entry {} name".format(entry["id"]))

    def test_no_gap_record_prints_a_dash(self):
        register = load_register(SHIPPED)
        for label, records in (("unresolved", register.unresolved),
                               ("unclassified", register.unclassified),
                               ("unreadable tables", register.unreadable_tables),
                               ("fetch failures", register.fetch_failures)):
            for record in records:
                for key, value in record.items():
                    if isinstance(value, str):
                        self.assertEqual([], punctuation_dashes(value),
                                         "{} field {}".format(label, key))


# --- the source half: a message no fixture here happens to trigger ------------


class TestSourceCarriesNoPrintableDash(unittest.TestCase):
    def test_there_are_modules_to_read(self):
        """Without this an empty list would pass the test below reading nothing."""
        names = {path.name for path in printable_modules()}
        self.assertLessEqual({"cli.py", "register.py", "ingredients.py",
                              "build_register.py", "measure_corpus.py"}, names)

    def test_no_printable_string_holds_a_dash(self):
        for module in printable_modules():
            with self.subTest(module=module.name):
                offences = []
                for literal in printable_strings(read_source(module)):
                    if literal in INPUT_CHARACTER_CLASSES:
                        continue
                    offences += ["{!r}: {}".format(literal, hit)
                                 for hit in punctuation_dashes(literal)]
                self.assertEqual([], offences,
                                 "{} holds a printable string with a dash: {}".format(
                                     module.name, offences))


# --- the inverse: the parsers keep the dashes they are meant to eat -----------


class TestTheParsersKeepTheirDashes(unittest.TestCase):
    """Deleting a dash from either character class makes this tool worse.

    A pack prints a hyphen, an en dash and an em dash around and inside names,
    and a register table has cells holding nothing but punctuation. Both classes
    exist to absorb exactly that. These tests exist so that a later tidy aimed at
    the no dashes rule cannot reach them without failing.
    """

    PRINTED_BY_A_PACK = ("-", "–", "—")

    def test_the_ingredient_parser_still_declares_every_dash_it_strips(self):
        source = read_source(os.path.join(ROOT, "on_notice", "ingredients.py"))
        literals = printable_strings(source)
        self.assertIn(" .:-–—", literals,
                      "the character class clean() strips has been edited")

    def test_the_ingredient_parser_still_strips_each_of_them(self):
        for dash in self.PRINTED_BY_A_PACK:
            with self.subTest(dash=dash):
                self.assertEqual("Retinol", clean(dash + " Retinol " + dash))

    def test_a_fragment_that_is_only_dashes_is_not_read_as_an_ingredient(self):
        """Doubled, because a single character is already too short to be a name.

        A fragment of one character is dropped by the length rule whatever the
        character class holds, so a one dash fragment would pass this test even
        with the class emptied. Two dashes are long enough to survive that rule
        and reach the strip, which is the thing under test.
        """
        for dash in self.PRINTED_BY_A_PACK:
            with self.subTest(dash=dash):
                self.assertEqual(["Aqua", "Retinol"],
                                 read_ingredients("Aqua, {}, Retinol".format(dash * 2)))

    def test_the_register_builder_still_declares_its_punctuation_class(self):
        source = read_source(os.path.join(ROOT, "scripts", "build_register.py"))
        literals = printable_strings(source)
        self.assertIn("[-–—\\s.,;:%0-9/]+", literals,
                      "the builder's punctuation only character class has been edited")

    def test_the_builders_class_still_recognises_a_cell_of_punctuation(self):
        pattern = "[-–—\\s.,;:%0-9/]+"
        for dash in self.PRINTED_BY_A_PACK:
            with self.subTest(dash=dash):
                self.assertTrue(re.fullmatch(pattern, "{} 12/3 {}".format(dash, dash)))
        self.assertIsNone(re.fullmatch(pattern, "Limonene"),
                          "the class has widened and would swallow a substance name")


# --- the scanner itself, which is the thing everything above trusts -----------


class TestTheScannerIsNotAsleep(unittest.TestCase):
    def test_it_sees_every_form_it_lists(self):
        for name in sorted(DASH_FORMS):
            with self.subTest(form=name):
                found = punctuation_dashes("read{}this".format(DASH_FORMS[name]))
                self.assertTrue(found, "{} was not seen".format(name))

    def test_it_sees_the_ascii_double_hyphen_that_a_search_for_an_em_dash_misses(self):
        line = "on-notice reads a label -- and reports a date"
        self.assertNotIn("—", line)
        self.assertTrue(punctuation_dashes(line))

    def test_it_leaves_spelling_and_identifiers_alone(self):
        for allowed in ("sell-through", "--unresolved", "non-compliant",
                        "2027-12-31", "115-86-6", "on-notice", "register.json",
                        "--before YYYY-MM-DD"):
            with self.subTest(text=allowed):
                self.assertEqual([], punctuation_dashes(allowed))

    def test_it_reports_which_line_and_which_form(self):
        found = punctuation_dashes("clean\nread{}this".format(DASH_FORMS["em dash"]))
        self.assertEqual(1, len(found))
        self.assertIn("line 2", found[0])
        self.assertIn("em dash", found[0])

    def test_the_json_walk_sees_a_dash_the_raw_text_hides(self):
        blob = json.dumps({"provision": "read{}this".format(DASH_FORMS["em dash"])})
        self.assertNotIn("—", blob)
        self.assertEqual([], punctuation_dashes(blob))
        self.assertTrue(punctuation_dashes(strings_in_json(blob)))

    def test_the_json_walk_reads_keys_as_well_as_values(self):
        blob = json.dumps({"read{}this".format(DASH_FORMS["em dash"]): 1})
        self.assertTrue(punctuation_dashes(strings_in_json(blob)))

    def test_the_source_reader_sees_a_dash_inside_an_f_string(self):
        """The trap that hid five sites of nine in another tool in this set.

        From Python 3.12 the middle of an f-string is not a STRING token, so a
        tokeniser looking for STRING misses this. The syntax tree does not.
        """
        source = 'name = "x"\nline = f"on-notice {name}—built"\n'
        self.assertTrue(any(punctuation_dashes(literal)
                            for literal in printable_strings(source)))

    def test_the_source_reader_skips_docstrings_and_comments(self):
        source = ('"""A module docstring holding an {0}."""\n'
                  '# a comment holding an {0}\n'
                  'def f():\n'
                  '    """A function docstring holding an {0}."""\n'
                  '    return 1\n').format(DASH_FORMS["em dash"])
        self.assertEqual([], [hit for literal in printable_strings(source)
                              for hit in punctuation_dashes(literal)])

    def test_the_source_reader_reads_a_plain_assignment(self):
        source = 'MESSAGE = "read{}this"\n'.format(DASH_FORMS["em dash"])
        self.assertTrue(any(punctuation_dashes(literal)
                            for literal in printable_strings(source)))

    def test_files_are_decoded_here_rather_than_by_the_platform(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "held.py")
            with open(path, "wb") as handle:
                handle.write('X = "read—this"\n'.encode("utf-8"))
            self.assertTrue(punctuation_dashes(read_source(path)))


if __name__ == "__main__":
    unittest.main()
