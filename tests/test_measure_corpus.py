"""The reproduction path the README promises has to work on the file it names.

The README tells a reader to run ``scripts/measure_corpus.py`` over the Open
Beauty Facts export. For a while it could not: the script read JSONL, the
export is a gzipped tab delimited table, and every reader who followed the
instruction got a traceback. These tests hold the two shapes to the same
result so the published instruction stays true.
"""

import gzip
import io
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import measure_corpus  # noqa: E402

HEADER = ["code", "url", "product_name", "brands", "ingredients_text"]
ROWS = [
    ["0001", "http://x/1", "Night Cream", "Acme", "Aqua, Benzyl Salicylate, Citral"],
    ["0002", "http://x/2", "No List", "Acme", ""],
    ["0003", "http://x/3", "Whitespace Only", "Acme", "   "],
    ["0004", "http://x/4", "Cleanser", "Beta", "Aqua, Glycerin"],
]


def _tsv_bytes():
    out = io.StringIO()
    out.write("\t".join(HEADER) + "\n")
    for row in ROWS:
        out.write("\t".join(row) + "\n")
    return out.getvalue().encode("utf-8")


class TestExportReading(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

        self.gz = os.path.join(self.dir.name, "export.csv.gz")
        with gzip.open(self.gz, "wb") as fh:
            fh.write(_tsv_bytes())

        self.plain = os.path.join(self.dir.name, "export.csv")
        with open(self.plain, "wb") as fh:
            fh.write(_tsv_bytes())

        self.jsonl = os.path.join(self.dir.name, "corpus.jsonl")
        with open(self.jsonl, "w", encoding="utf-8") as fh:
            for row in ROWS:
                record = dict(zip(HEADER, row))
                if not record["ingredients_text"].strip():
                    continue
                fh.write(json.dumps({k: record[k] for k in
                                     ("code", "product_name", "brands", "ingredients_text")}) + "\n")

    def _read(self, path):
        counts = {"records": 0, "shape": None}
        rows = list(measure_corpus.read_corpus(path, counts))
        return rows, counts

    def test_the_gzipped_export_is_read_without_an_intermediate_file(self):
        rows, counts = self._read(self.gz)
        self.assertEqual(counts["shape"], "export")
        self.assertEqual([r["code"] for r in rows], ["0001", "0004"])

    def test_every_export_record_is_counted_including_the_skipped_ones(self):
        _, counts = self._read(self.gz)
        self.assertEqual(counts["records"], len(ROWS))

    def test_a_record_whose_ingredient_field_is_only_whitespace_is_skipped(self):
        rows, _ = self._read(self.gz)
        self.assertNotIn("0003", [r["code"] for r in rows])

    def test_the_export_is_recognised_after_someone_unzips_it(self):
        rows, counts = self._read(self.plain)
        self.assertEqual(counts["shape"], "export")
        self.assertEqual([r["code"] for r in rows], ["0001", "0004"])

    def test_the_jsonl_shape_still_works(self):
        rows, counts = self._read(self.jsonl)
        self.assertEqual(counts["shape"], "jsonl")
        self.assertEqual([r["code"] for r in rows], ["0001", "0004"])

    def test_both_shapes_yield_the_same_ingredient_text(self):
        from_export = [r["ingredients_text"] for r in self._read(self.gz)[0]]
        from_jsonl = [r["ingredients_text"] for r in self._read(self.jsonl)[0]]
        self.assertEqual(from_export, from_jsonl)

    def test_a_file_that_is_not_the_export_says_which_columns_are_missing(self):
        wrong = os.path.join(self.dir.name, "wrong.csv")
        with open(wrong, "w", encoding="utf-8") as fh:
            fh.write("a\tb\n1\t2\n")
        with self.assertRaises(SystemExit) as caught:
            self._read(wrong)
        self.assertIn("ingredients_text", str(caught.exception))

    def test_the_hash_is_what_shasum_would_print(self):
        import hashlib
        with open(self.gz, "rb") as fh:
            expected = hashlib.sha256(fh.read()).hexdigest()
        self.assertEqual(measure_corpus.file_sha256(self.gz), expected)


if __name__ == "__main__":
    unittest.main()
