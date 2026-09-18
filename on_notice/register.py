"""Reading the register and matching label names against it.

The register is built by scripts/build_register.py from EUR-Lex and shipped
inside the package as register.json. Nothing here goes to the network.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import unicodedata

REGISTER_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "register.json")

RESTRICTION_ORDER = {"placing": 0, "making_available": 1, "application": 2}

RESTRICTION_PLAIN = {
    "placing": ("products that do not meet the new restriction cannot be placed "
                "on the Union market"),
    "making_available": ("products that do not meet the new restriction cannot be sold "
                         "in the Union, including stock already made"),
    "application": "the amendment starts to apply",
}

MATCH_EXACT = "exact"
MATCH_CONTAINED = "contained"


def normalise_name(name):
    """The same key the builder uses, so both sides of a match agree.

    Case, accents, quotation style and punctuation all differ between an annex
    table and a printed pack. The key keeps letters and digits and nothing else.
    """
    name = unicodedata.normalize("NFKD", name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    name = name.lower()
    name = re.sub(r"\(\s*\*+\s*\d*\s*\)", " ", name)
    name = re.sub(r"[^a-z0-9]+", " ", name)
    return re.sub(r"\s+", " ", name).strip()


class Finding(object):
    """One ingredient on the label meeting one dated restriction."""

    __slots__ = ("ingredient", "matched_name", "match_type", "entry")

    def __init__(self, ingredient, matched_name, match_type, entry):
        self.ingredient = ingredient
        self.matched_name = matched_name
        self.match_type = match_type
        self.entry = entry

    @property
    def date(self):
        return self.entry["date"]

    @property
    def restriction(self):
        return self.entry["restriction"]

    @property
    def restriction_plain(self):
        return self.entry.get("restriction_plain") or RESTRICTION_PLAIN.get(
            self.entry["restriction"], self.entry["restriction"])

    @property
    def already_applying(self):
        return bool(self.entry.get("already_applying"))

    @property
    def regulation(self):
        return self.entry["regulation"]

    def as_dict(self):
        return {
            "ingredient_as_written": self.ingredient,
            "matched_register_name": self.matched_name,
            "match": self.match_type,
            "date": self.entry["date"],
            "date_basis": self.entry["basis"],
            "stated_date": self.entry["stated_date"],
            "restriction": self.entry["restriction"],
            "restriction_plain": self.restriction_plain,
            "regulation": self.entry["regulation"],
            "celex": self.entry["celex"],
            "annex": self.entry["annex"],
            "entry_reference": self.entry["entry_reference"],
            "provision": self.entry["provision"],
            "how_the_substance_was_identified": self.entry["resolution"],
        }


class Register(object):
    def __init__(self, data):
        self.data = data
        self.entries = data.get("entries", [])
        self._exact = {}
        self._keys = []
        for entry in self.entries:
            for name in entry.get("names", []):
                key = name.get("key") or normalise_name(name["name"])
                if not key:
                    continue
                self._exact.setdefault(key, []).append((name["name"], entry))
                self._keys.append((key, name["name"], entry))
        self._keys.sort(key=lambda item: -len(item[0]))

    # -- what the register knows about itself -------------------------------

    @property
    def built(self):
        return self.data.get("built", "unknown")

    @property
    def counts(self):
        return self.data.get("counts", {})

    @property
    def unresolved(self):
        return self.data.get("unresolved", [])

    @property
    def not_recovered(self):
        """Entries whose restriction text was never recovered from the source.

        Several Annex III entries print as multiple rows with the conditions on
        a parent row. Promoting one of these to a finding would invent a
        restriction; dropping it would hide a date. It is reported instead.
        """
        return self.data.get("restriction_text_not_recovered", [])

    @property
    def labelling_only(self):
        """Dated duties to NAME a substance in the list of ingredients.

        Regulation (EU) 2023/1545 is the large example. A list that already
        names the substance is doing what the rule asks, so finding the name
        here is evidence of the duty being met, not of a deadline being faced.
        The products at risk print only "parfum" and never name it, and no
        check that reads printed names can see them. These are reported, never
        counted as findings.
        """
        return self.data.get("labelling_only", [])

    @property
    def uncheckable(self):
        """Dated restrictions naming a class of ingredients, not a substance.

        A printed list carries substance names, so these cannot be matched
        against one. They are reported rather than matched or dropped.
        """
        return self.data.get("uncheckable", [])

    @property
    def unclassified(self):
        return self.data.get("unclassified_sentences", [])

    @property
    def unreadable_tables(self):
        return self.data.get("unreadable_tables", [])

    @property
    def fetch_failures(self):
        return self.data.get("fetch_failures", [])

    @property
    def is_complete(self):
        return not (self.unresolved or self.unclassified
                    or self.unreadable_tables or self.fetch_failures
                    or self.uncheckable or self.labelling_only
                    or self.not_recovered)

    def distinct_names(self):
        return len(self._exact)

    # -- matching -----------------------------------------------------------

    def match(self, ingredient):
        """Every register entry this one label name meets.

        An exact match is a normalised name for name match. A contained match is
        a register name appearing whole inside the label name, which is how a
        pack writes "Alpha-Pinene" for the register's "Pinene". Contained
        matches are reported as such so the reader can judge them, never
        silently folded into exact ones.
        """
        key = normalise_name(ingredient)
        if not key:
            return []
        found, seen = [], set()
        for name, entry in self._exact.get(key, []):
            if entry["id"] in seen:
                continue
            seen.add(entry["id"])
            found.append(Finding(ingredient, name, MATCH_EXACT, entry))
        padded = " " + key + " "
        for register_key, name, entry in self._keys:
            if entry["id"] in seen or register_key == key or len(register_key) < 5:
                continue
            if (" " + register_key + " ") in padded:
                seen.add(entry["id"])
                found.append(Finding(ingredient, name, MATCH_CONTAINED, entry))
        return found

    def check(self, ingredients, not_after=None):
        findings = []
        for ingredient in ingredients:
            for finding in self.match(ingredient):
                if not_after and finding.date > not_after:
                    continue
                findings.append(finding)
        findings.sort(key=lambda f: (
            f.date,
            RESTRICTION_ORDER.get(f.restriction, 9),
            f.matched_name.lower(),
        ))
        return findings


def load_register(path=None):
    path = path or REGISTER_PATH
    if not os.path.exists(path):
        raise IOError(
            "no register at {}. Build one with scripts/build_register.py".format(path))
    with open(path, "r", encoding="utf-8") as handle:
        return Register(json.load(handle))


def parse_date(value):
    return datetime.date.fromisoformat(value)
