#!/usr/bin/env python3
"""Run on-notice across a corpus of real published ingredient lists.

Reports what the tool says about labels it did not author, and, just as
importantly, how much of the corpus it could not read at all.
"""
import json, sys, collections, argparse, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from on_notice.ingredients import read_ingredients
from on_notice.register import load_register


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("corpus")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    reg = load_register()
    products = 0
    unreadable = 0          # no ingredient tokens recovered at all
    with_findings = 0
    ingredient_counts = []
    by_substance = collections.Counter()
    by_date = collections.Counter()
    by_regulation = collections.Counter()
    products_by_substance_count = collections.Counter()
    hits = []

    with open(args.corpus, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
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
        json.dump({"products": products, "unreadable": unreadable,
                   "lists_read": total_read, "with_findings": with_findings,
                   "by_substance": by_substance.most_common(),
                   "by_date": sorted(by_date.items()),
                   "by_regulation": by_regulation.most_common(),
                   "sample": hits},
                  open(args.out, "w"), indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
