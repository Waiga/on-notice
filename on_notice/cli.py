"""The on-notice command line."""

from __future__ import annotations

import argparse
import datetime
import json
import sys

from . import __version__
from .ingredients import read_ingredients
from .register import load_register, MATCH_CONTAINED

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def pretty_date(iso):
    try:
        value = datetime.date.fromisoformat(iso)
    except ValueError:
        return iso
    return "{} {} {}".format(value.day, MONTHS[value.month - 1], value.year)


def read_input(path):
    if path in (None, "-"):
        if sys.stdin.isatty():
            raise SystemExit("on-notice: give a file, or pipe an ingredient list in")
        return sys.stdin.read()
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return handle.read()


def gaps(register):
    """What the register itself says it could not read.

    A quiet result is only worth having when the reader knows how complete the
    thing behind it is, so this is printed on every run.
    """
    lines = []
    if register.fetch_failures:
        lines.append(
            "{} regulation(s) could not be downloaded when the register was built, "
            "so any deadline they carry is missing here.".format(len(register.fetch_failures)))
    if register.unresolved:
        lines.append(
            "{} dated restriction(s) were found in the regulations but the substances "
            "they cover could not be read from the text, so they are not matched "
            "against your list.".format(len(register.unresolved)))
    if getattr(register, "not_recovered", None):
        lines.append(
            "{} dated entries had no restriction text that could be recovered from "
            "the source, because the conditions are printed on a parent row. They are "
            "neither reported as findings nor dropped. Run with --unresolved to read "
            "them.".format(len(register.not_recovered)))
    if getattr(register, "labelling_only", None):
        substances = {(e.get("inci_name") or e.get("chemical_name"))
                      for e in register.labelling_only}
        lines.append(
            "{} further substance(s) have a dated rule requiring them to be NAMED in "
            "the list of ingredients above a threshold. A list that names one is doing "
            "what that rule asks, so they are not reported as findings. The products at "
            "risk print only parfum and never name the substance, and nothing that reads "
            "printed names can see them.".format(len(substances)))
    if getattr(register, "uncheckable", None):
        lines.append(
            "{} dated restriction(s) name a class of ingredients with an exception "
            "list rather than a substance, so they cannot be matched against a "
            "printed list at all. Run with --unresolved to read them.".format(
                len(register.uncheckable)))
    if register.unreadable_tables:
        lines.append(
            "{} annex table(s) could not be read, so substances in them are "
            "missing.".format(len(register.unreadable_tables)))
    if register.unclassified:
        lines.append(
            "{} sentence(s) in the regulations mention a date and the Union market in "
            "wording the builder does not interpret.".format(len(register.unclassified)))
    return lines


def describe_unresolved(register, out):
    """Everything the register knows it could not answer."""
    counts = register.counts
    out.write("Register built {} from {} of {} regulations.\n".format(
        register.built,
        counts.get("regulations_read", "?"),
        counts.get("regulations_listed", "?")))
    out.write("{} dated provisions found in total, {} of which could not be tied to "
              "named substances. {} of those have a date still ahead and are shown "
              "below.\n\n".format(
                  counts.get("dated_provisions_found", "?"),
                  counts.get("unresolved_provisions_total", "?"),
                  counts.get("unresolved_provisions_shipped", "?")))
    if register.is_complete:
        out.write("The register has no unresolved provisions, no unread tables and no "
                  "unclassified sentences.\n")
        return

    if register.fetch_failures:
        out.write("Regulations that could not be downloaded\n\n")
        for item in register.fetch_failures:
            out.write("  {}  {}\n".format(item["celex"], item["error"]))
            out.write("    {}\n\n".format(item["consequence"]))

    if register.unresolved:
        out.write("Dated restrictions whose substances could not be identified\n\n")
        for item in register.unresolved:
            out.write("  {}  {}\n".format(pretty_date(item["date"]), item["regulation"]))
            out.write("    why  {}\n".format(item["reason"]))
            out.write("    text {}\n\n".format(item["provision"]))

    if register.unreadable_tables:
        out.write("Annex tables that could not be read\n\n")
        for item in register.unreadable_tables:
            out.write("  {}  {}\n".format(item["celex"], item["reason"]))
            out.write("    starts {}\n\n".format(item["sample"]))

    if register.unclassified:
        out.write("Sentences mentioning a date and the market that were not "
                  "interpreted\n\n")
        for item in register.unclassified:
            out.write("  {}  {}\n".format(item["celex"], item["sentence"]))
        out.write("\n")


def render(findings, ingredients, register, source, out):
    out.write("on-notice {}   register built {}\n".format(__version__, register.built))
    out.write("read {} ingredient(s) from {}\n\n".format(len(ingredients), source))

    if findings:
        substances = sorted({f.matched_name for f in findings})
        in_force = sum(1 for f in findings if f.already_applying)
        out.write("{} of them {} named in an EU rule with a date still ahead of "
                  "it.\n".format(len(substances),
                                 "is" if len(substances) == 1 else "are"))
        if in_force:
            out.write("Some of those rules are already in force; the date shown is when "
                      "stock can no longer be sold.\n")
        out.write("\n")
        current = None
        for finding in findings:
            heading = (finding.date, finding.restriction)
            if heading != current:
                current = heading
                out.write("{}   {}{}\n".format(
                    pretty_date(finding.date),
                    finding.restriction_plain,
                    "   [this rule is already in force; this is the sell-through end]"
                    if finding.already_applying else ""))
            out.write("    {}\n".format(finding.matched_name))
            out.write("      on the label as   {}{}\n".format(
                finding.ingredient,
                "   (the register name appears inside this one, worth checking)"
                if finding.match_type == MATCH_CONTAINED else ""))
            out.write("      named in          {}, Annex {}{}\n".format(
                finding.regulation,
                finding.entry["annex"] or "unstated",
                " entry " + finding.entry["entry_reference"]
                if finding.entry["entry_reference"] else ""))
            out.write("      the rule says     {}\n\n".format(finding.entry["provision"]))

        out.write("A date here names the ingredient, not your product. Each rule catches\n"
                  "products that do not meet its new restriction, and a printed ingredient\n"
                  "list states no concentrations, so this tool cannot tell you which side of\n"
                  "that line you are on. Read the rule text above against what you know\n"
                  "of the product. Some conditions are not formulation choices at all: a\n"
                  "peroxide value or a trace impurity limit is a property of the material\n"
                  "you buy, and is answered by a supplier certificate, not by a recipe.\n\n")
    else:
        out.write("None of these ingredients is named in a rule with a date still ahead "
                  "of it.\n")
        out.write("Checked against {} names drawn from {} regulations.\n\n".format(
            register.distinct_names(), register.counts.get("regulations_read", "?")))

    out.write("What this check could not see\n")
    problems = gaps(register)
    if problems:
        for line in problems:
            out.write("  {}\n".format(line))
        out.write("  Run with --unresolved to read them.\n")
    else:
        out.write("  Nothing. Every regulation in scope was read, every dated provision "
                  "was classified, and every one was tied to named substances.\n")
    out.write("\nThis tool reports dates, not verdicts. It does not say whether a "
              "product may be sold.\n")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="on-notice",
        description="Report which ingredients on a list have an EU deadline that has "
                    "not arrived yet.")
    parser.add_argument("file", nargs="?", default="-",
                        help="a file holding an ingredient list, or - for standard input")
    parser.add_argument("--register", default=None, help="path to a register.json")
    parser.add_argument("--before", default=None, metavar="YYYY-MM-DD",
                        help="only report restrictions that start on or before this date")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="print the findings as JSON")
    parser.add_argument("--unresolved", action="store_true",
                        help="print the dated restrictions whose substances could not "
                             "be identified, and stop")
    parser.add_argument("--version", action="version", version="on-notice " + __version__)
    return parser


def main(argv=None, out=None):
    out = out or sys.stdout
    args = build_parser().parse_args(argv)

    try:
        register = load_register(args.register)
    except IOError as error:
        sys.stderr.write("on-notice: {}\n".format(error))
        return 2

    if args.unresolved:
        describe_unresolved(register, out)
        return 0

    if args.before:
        try:
            datetime.date.fromisoformat(args.before)
        except ValueError:
            sys.stderr.write("on-notice: --before needs a date like 2027-12-31\n")
            return 2

    try:
        text = read_input(args.file)
    except IOError as error:
        sys.stderr.write("on-notice: {}\n".format(error))
        return 2

    ingredients = read_ingredients(text)
    findings = register.check(ingredients, not_after=args.before)

    if args.as_json:
        json.dump({
            "register_built": register.built,
            "ingredients_read": ingredients,
            "findings": [f.as_dict() for f in findings],
            "register_gaps": {
                "unresolved_provisions": register.unresolved,
                "unclassified_sentences": register.unclassified,
                "unreadable_tables": register.unreadable_tables,
                "fetch_failures": register.fetch_failures,
            },
            "complete": register.is_complete,
        }, out, indent=2, ensure_ascii=False)
        out.write("\n")
    else:
        render(findings, ingredients, register, 
               "standard input" if args.file in (None, "-") else args.file, out)

    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
