#!/usr/bin/env python3
"""Run on-notice across a corpus of real published ingredient lists.

Reports what the tool says about labels it did not author, and, just as
importantly, how much of the corpus it could not read at all.

    curl -sO https://static.openbeautyfacts.org/data/en.openbeautyfacts.org.products.csv.gz
    shasum -a 256 en.openbeautyfacts.org.products.csv.gz
    python3 scripts/measure_corpus.py en.openbeautyfacts.org.products.csv.gz

The export is the Open Beauty Facts CSV export, which is gzipped and tab
delimited despite the name. It is read here directly, so the command above is
the whole reproduction and there is no intermediate file to build. The export
is Open Database Licence 1.0, which is share alike and so incompatible with
redistributing a filtered subset inside an MIT repository. It is not vendored
here. Only the measurements are published, and the hash the script prints is
how a reader checks they have the same file.

The published numbers came from the copy whose SHA-256 is
``d527f033d2549b86424db0ef1e87b785f92f53901036afd0c0a24bd629a766a5``
(17,884,435 bytes). The server republishes this file daily and moves its
Last-Modified stamp even when the bytes do not change, so the hash is the only
identity worth quoting.

Selection rule, applied to every record in the export: keep it if its
``ingredients_text`` field holds anything other than whitespace. Nothing else
is filtered, sorted or sampled.

A JSONL file is also accepted, one object per line carrying the keys ``code``,
``product_name``, ``brands`` and ``ingredients_text``. That was the original
input and it still works. The export path is the documented one because it
needs no preparation.
"""
import json, sys, collections, argparse, os, csv, gzip, hashlib, itertools

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from on_notice.ingredients import read_ingredients
from on_notice.register import load_register

# The four columns this measurement reads. The export carries about two hundred.
FIELDS = ("code", "product_name", "brands", "ingredients_text")

GZIP_MAGIC = b"\x1f\x8b"


def _rows_from_jsonl(lines):
    """Yield the objects of a JSONL corpus, one per non empty line."""
    for line in lines:
        if not line.strip():
            continue
        yield json.loads(line)


def _rows_from_export(lines, counts):
    """Yield the export records that carry an ingredient list.

    ``counts["records"]`` ends up holding every record the export contained,
    including the ones skipped here for having no ingredient list, because the
    two numbers together are what says how much of the export was readable.
    """
    csv.field_size_limit(10 ** 8)
    reader = csv.reader(lines, delimiter="\t")
    try:
        header = next(reader)
    except StopIteration:
        raise SystemExit("the export is empty")
    missing = [name for name in FIELDS if name not in header]
    if missing:
        raise SystemExit(
            "this file does not look like an Open Beauty Facts export. "
            "Missing column(s): " + ", ".join(missing)
        )
    for raw in reader:
        row = dict(zip(header, raw))
        counts["records"] += 1
        text = row.get("ingredients_text") or ""
        if not text.strip():
            continue
        yield {name: (row.get(name) or "") for name in FIELDS}


def read_corpus(path, counts):
    """Yield product rows from whichever of the two shapes ``path`` holds.

    The Open Beauty Facts export is detected by its gzip magic bytes or, once
    decompressed, by a first line that is not a JSON object. Nothing here
    trusts the file extension, because the export is named ``.csv.gz`` and is
    neither comma separated nor, once a reader has unzipped it by hand, still
    carrying the ``.gz``.
    """
    with open(path, "rb") as probe:
        gzipped = probe.read(2) == GZIP_MAGIC
    opener = gzip.open if gzipped else open
    with opener(path, mode="rt", encoding="utf-8", errors="replace", newline="") as fh:
        first = fh.readline()
        lines = itertools.chain([first], fh)
        if first.lstrip().startswith("{"):
            counts["shape"] = "jsonl"
            yield from _rows_from_jsonl(lines)
        else:
            counts["shape"] = "export"
            yield from _rows_from_export(lines, counts)


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    ap = argparse.ArgumentParser(
        description="Measure on-notice against the Open Beauty Facts export."
    )
    ap.add_argument(
        "corpus",
        help="the export, en.openbeautyfacts.org.products.csv.gz, or a JSONL corpus",
    )
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    reg = load_register()
    counts = {"records": 0, "shape": None}
    products = 0
    unreadable = 0          # no ingredient tokens recovered at all
    with_findings = 0
    ingredient_counts = []
    by_substance = collections.Counter()
    by_date = collections.Counter()
    by_regulation = collections.Counter()
    products_by_substance_count = collections.Counter()
    hits = []

    digest = file_sha256(args.corpus)
    size = os.path.getsize(args.corpus)

    for row in read_corpus(args.corpus, counts):
        products += 1
        names = read_ingredients(row["ingredients_text"])
        if not names:
            unreadable += 1
            continue
        ingredient_counts.append(len(names))
        findings = reg.check(names) if hasattr(reg, "check") else reg.match(names)
        if not findings:
            continue
        with_findings += 1
        subs = sorted({f.matched_name for f in findings})
        products_by_substance_count[len(subs)] += 1
        for s in subs:
            by_substance[s] += 1
        for f in findings:
            by_date[f.date] += 1
            by_regulation[f.entry["celex"]] += 1
        if len(hits) < 40:
            hits.append({"code": row["code"], "name": row["product_name"][:60],
                         "brands": row["brands"][:40], "substances": subs})

    total_read = products - unreadable
    print("corpus file                   :", os.path.basename(args.corpus))
    print("sha256                        :", digest)
    print("bytes                         :", size)
    if counts["shape"] == "export":
        print("records in the export         :", counts["records"])
    print("products in corpus            :", products)
    print("no ingredient names recovered :", unreadable)
    print("lists actually read           :", total_read)
    print("median ingredients per list   :",
          sorted(ingredient_counts)[len(ingredient_counts)//2] if ingredient_counts else 0)
    print()
    print("lists naming at least one substance with a future date :", with_findings,
          "({:.1f}% of lists read)".format(100.0*with_findings/total_read if total_read else 0))
    print()
    print("how many such substances per affected list:")
    for k in sorted(products_by_substance_count):
        print("   {:>2} substance(s): {:>6}".format(k, products_by_substance_count[k]))
    print()
    print("top substances by number of lists naming them:")
    for s, c in by_substance.most_common(25):
        print("   {:>6}  {}".format(c, s))
    print()
    print("findings by deadline:")
    for d, c in sorted(by_date.items()):
        print("   {}  {:>7}".format(d, c))
    print()
    print("findings by regulation:")
    for r, c in by_regulation.most_common():
        print("   {}  {:>7}".format(r, c))
    print()
    print("distinct register substances actually seen in the corpus:",
          len(by_substance), "of", reg.distinct_names())

    if args.out:
        json.dump({"corpus_sha256": digest, "corpus_bytes": size,
                   "export_records": counts["records"] if counts["shape"] == "export" else None,
                   "products": products, "unreadable": unreadable,
                   "lists_read": total_read, "with_findings": with_findings,
                   "by_substance": by_substance.most_common(),
                   "by_date": sorted(by_date.items()),
                   "by_regulation": by_regulation.most_common(),
                   "sample": hits},
                  open(args.out, "w"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
