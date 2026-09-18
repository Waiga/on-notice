#!/usr/bin/env python3
"""Build the On Notice register from EUR-Lex.

Reads the Commission regulations that amend Regulation (EC) No 1223/2009 and
extracts every dated transitional provision: a rule stating a date from which a
cosmetic product containing a named substance may no longer be placed on, or
made available on, the Union market.

Nothing is interpreted. A provision is recorded only when the regulation itself
states the date, and a substance is attached to it only when the regulation
itself links them, either through a footnote marker carried by an annex entry or
through a provision that names the substance or names the regulation as a whole.

The one thing this script must never do is fall silent. Every regulation it
could not fetch, every dated sentence it could not classify, and every provision
whose substances it could not resolve is written into the register as an
explicit record. A missing substance is reported as unknown, never as a
confirmed nothing.

Usage:
    python3 scripts/build_register.py --out on_notice/register.json
    python3 scripts/build_register.py --cache-dir .cache --out register.json
"""

from __future__ import annotations

import argparse
import datetime
import html as html_module
import json
import os
import re
import sys
import time
import unicodedata
import urllib.request
from html.parser import HTMLParser

EURLEX_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A{celex}"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

INSTRUMENT = "Regulation (EC) No 1223/2009 on cosmetic products"

# Commission regulations amending Regulation (EC) No 1223/2009, 2013 onward.
CELEX_IDS = [
    "32013R0344", "32013R0483", "32013R0658", "32013R1197", "32014R0358",
    "32014R0866", "32014R1003", "32014R1004", "32015R1190", "32015R1298",
    "32016R0314", "32016R0621", "32016R0622", "32016R1120", "32016R1121",
    "32016R1143", "32016R1198", "32017R0237", "32017R0238", "32017R1224",
    "32017R1410", "32017R1413", "32017R2228", "32018R0885", "32018R0978",
    "32018R1847", "32019R0680", "32019R0681", "32019R0698", "32019R0831",
    "32019R1257", "32019R1857", "32019R1858", "32019R1966", "32020R1682",
    "32020R1683", "32020R1684", "32021R0850", "32021R1099", "32021R1902",
    "32022R0135", "32022R1176", "32022R1181", "32022R1531", "32022R2195",
    "32023R1490", "32023R1545", "32024R0858", "32024R0996", "32025R0877",
    "32026R0078", "32026R0909",
]

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
DATE = r"(\d{1,2})\s+(" + "|".join(MONTHS) + r")\s+(\d{4})"

PLACING = "placing"
MAKING_AVAILABLE = "making_available"
APPLICATION = "application"

RESTRICTION_PLAIN = {
    PLACING: ("products that do not meet the new restriction cannot be placed "
              "on the Union market"),
    MAKING_AVAILABLE: ("products that do not meet the new restriction cannot be sold "
                       "in the Union, including stock already made"),
    APPLICATION: "the amendment starts to apply",
}


# ---------------------------------------------------------------------------
# A small document model. The standard library only, so the tool installs and
# runs anywhere without a dependency tree.
# ---------------------------------------------------------------------------

VOID_TAGS = {
    "br", "img", "hr", "meta", "link", "input", "col", "area", "base",
    "source", "wbr", "param", "embed", "track",
}


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.children = []
        self.parent = parent

    def classes(self):
        return self.attrs.get("class", "").split()

    def walk(self):
        """Yield every descendant element in document order."""
        for child in self.children:
            if isinstance(child, Node):
                yield child
                for grandchild in child.walk():
                    yield grandchild

    def find_all(self, tag=None, cls=None):
        return [
            n for n in self.walk()
            if (tag is None or n.tag == tag) and (cls is None or cls in n.classes())
        ]

    def text(self):
        parts = []

        def collect(node):
            for child in node.children:
                if isinstance(child, str):
                    parts.append(child)
                else:
                    if child.tag in ("br", "p", "tr", "td", "div"):
                        parts.append(" ")
                    collect(child)

        collect(self)
        return squash(" ".join(parts))

    def ancestors(self):
        node = self.parent
        while node is not None:
            yield node
            node = node.parent

    def own_rows(self):
        """Rows belonging to this table, not to tables nested inside its cells."""
        rows = []

        def descend(node):
            for child in node.children:
                if not isinstance(child, Node):
                    continue
                if child.tag == "tr":
                    rows.append(child)
                elif child.tag in ("tbody", "thead", "tfoot"):
                    descend(child)

        descend(self)
        return rows

    def own_cells(self):
        return [c for c in self.children if isinstance(c, Node) and c.tag in ("td", "th")]


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document")
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.current)
        self.current.children.append(node)
        if tag not in VOID_TAGS:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Node(tag, dict(attrs), self.current))

    def handle_endtag(self, tag):
        node = self.current
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.current = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def parse_html(markup):
    builder = _Builder()
    builder.feed(markup)
    return builder.root


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def squash(text):
    return re.sub(r"\s+", " ", text).strip()


def plain_text(markup):
    stripped = re.sub(r"<[^>]+>", " ", markup)
    return squash(html_module.unescape(stripped))


QUOTE_CHARS = "‘’“”«»'\""


def tidy(text):
    """Strip the Official Journal's quotation and amendment punctuation."""
    text = squash(text)
    text = text.strip()
    while text and (text[0] in QUOTE_CHARS or text[0] in "’;,"):
        text = text[1:].strip()
    while text and (text[-1] in QUOTE_CHARS or text[-1] in ";,"):
        text = text[:-1].strip()
    return text


def normalise_name(name):
    """Reduce a substance name to a comparison key.

    Case, accents, quotation style, bracket style and punctuation all vary
    between an annex table and a printed pack. The key keeps letters and
    digits and nothing else, so those variations stop mattering.
    """
    name = unicodedata.normalize("NFKD", name)
    name = "".join(ch for ch in name if not unicodedata.combining(ch))
    name = name.lower()
    name = re.sub(r"\(\s*\*+\s*\d*\s*\)", " ", name)
    name = re.sub(r"[^a-z0-9]+", " ", name)
    return squash(name)


MARKER_RE = re.compile(r"\(\s*(\*{1,6})\s*(\d{0,2})\s*\)")
ANCHOR_MARKER_RE = re.compile(r"nt[cr](\*\d{0,2})[-\s]")


def markers_in(text):
    return {"(" + m.group(1) + m.group(2) + ")" for m in MARKER_RE.finditer(text)}


def markers_in_node(node):
    found = markers_in(node.text())
    for anchor in node.find_all("a"):
        for value in (anchor.attrs.get("id", ""), anchor.attrs.get("href", "")):
            for m in ANCHOR_MARKER_RE.finditer(value + " "):
                found.add("(" + m.group(1) + ")")
    return found


def to_date(day, month, year):
    return datetime.date(int(year), MONTHS.index(month) + 1, int(day))


# ---------------------------------------------------------------------------
# Operative constructions
#
# Four shapes carry a transitional deadline in these regulations. Keeping them
# separate matters commercially: "placed on" stops new supply, "made available
# on" stops the sale of stock already in the channel, and the "until" form gives
# a last lawful day rather than a first restricted day.
# ---------------------------------------------------------------------------

NOT_BE = r"shall\s+(?:not\s+be|be\s+not\s+be)\s+"

CONSTRUCTIONS = [
    # From <date> ... shall not be placed on the Union market.
    ("from_not_placed", PLACING, "from",
     re.compile(r"From\s+" + DATE + r"\s[^.]{0,400}?" + NOT_BE + r"placed\s+on\s+the\s+Union\s+market",
                re.IGNORECASE)),
    # From <date> ... shall not be made available on the Union market.
    ("from_not_made_available", MAKING_AVAILABLE, "from",
     re.compile(r"From\s+" + DATE + r"\s[^.]{0,400}?" + NOT_BE + r"made\s+available\s+on\s+the\s+Union\s+market",
                re.IGNORECASE)),
    # From <date> only cosmetic products which comply ... shall be placed [and made available] on the Union market.
    ("from_only_complying_placed", PLACING, "from",
     re.compile(r"From\s+" + DATE + r"\s+only\s+cosmetic\s+products\s+which\s+comply[^.]{0,300}?"
                r"shall\s+be\s+placed(?:\s+and\s+made\s+available)?\s+on\s+the\s+Union\s+market",
                re.IGNORECASE)),
    ("from_only_complying_made_available", MAKING_AVAILABLE, "from",
     re.compile(r"From\s+" + DATE + r"\s+only\s+cosmetic\s+products\s+which\s+comply[^.]{0,300}?"
                r"shall\s+be\s+(?:placed\s+and\s+)?made\s+available\s+on\s+the\s+Union\s+market",
                re.IGNORECASE)),
    # ... may be placed on the Union market until <date>.
    ("placed_until", PLACING, "until",
     re.compile(r"placed\s+on\s+the\s+Union\s+market\s+until\s+" + DATE, re.IGNORECASE)),
    # ... made available on the Union market until <date>.
    ("made_available_until", MAKING_AVAILABLE, "until",
     re.compile(r"made\s+available\s+on\s+the\s+Union\s+market\s+until\s+" + DATE, re.IGNORECASE)),
    # This Regulation / It / Article 1 shall apply from <date>. A regulation can
    # be adopted now and bite later with no transitional footnote at all, so this
    # form has to be read or the whole regulation goes unreported.
    ("applies_from", APPLICATION, "from",
     re.compile(r"(?:This\s+Regulation|It|Article\s+1)\s+shall\s+apply\s+from\s+" + DATE,
                re.IGNORECASE)),
]

# The same words, but scoped to one point of the annex. The point cannot be
# resolved to entries, so it is recorded as an open question rather than
# stretched across every substance in the regulation.
PARTIAL_APPLICATION_RE = re.compile(
    r"(?:Point[s]?\s*\([^)]{1,12}\)[^.]{0,80}?|the\s+following\s+provisions[^.]{0,60}?"
    r"|except\s+the\s+provisions[^.]{0,80}?)shall\s+apply\s+from\s+" + DATE,
    re.IGNORECASE,
)

# A provision whose scope is the regulation as a whole rather than one entry.
REGULATION_WIDE_RE = re.compile(
    r"(?:substances?\s+(?:prohibited|restricted)\s+by\s+this\s+Regulation"
    r"|comply\s+with\s+this\s+Regulation"
    r"|comply\s+with\s+Regulation\s+\(EC\)\s+No\s+1223/2009\s+as\s+amended\s+by\s+this\s+Regulation"
    r"|laid\s+down\s+in\s+this\s+Regulation"
    r"|This\s+Regulation\s+shall\s+apply\s+from"
    r"|\bIt\s+shall\s+apply\s+from"
    r"|Article\s+1\s+shall\s+apply\s+from)",
    re.IGNORECASE,
)


def sentence_around(text, start, end):
    """The sentence containing a matched span, used as the quoted provision."""
    left = text.rfind(". ", 0, start)
    left = 0 if left == -1 else left + 2
    right = text.find(".", end)
    right = len(text) if right == -1 else right + 1
    return tidy(text[left:right])


def find_provisions(text, origin):
    """Every dated transitional construction in a block of text."""
    found = []
    for name, restriction, basis, pattern in CONSTRUCTIONS:
        for m in pattern.finditer(text):
            stated = to_date(m.group(1), m.group(2), m.group(3))
            effective = stated if basis == "from" else stated + datetime.timedelta(days=1)
            found.append({
                "construction": name,
                "restriction": restriction,
                "basis": basis,
                "stated_date": stated.isoformat(),
                "date": effective.isoformat(),
                "span": (m.start(), m.end()),
                "text": sentence_around(text, m.start(), m.end()),
                "origin": origin,
                "regulation_wide": bool(REGULATION_WIDE_RE.search(m.group(0))),
            })
    # The same sentence can satisfy two constructions, for example "placed and
    # made available". Keep both restrictions but drop exact duplicates.
    unique = {}
    for p in found:
        key = (p["restriction"], p["date"], p["text"])
        if key not in unique:
            unique[key] = p
    return list(unique.values())


MARKET_MENTION_RE = re.compile(
    r"(?:Union\s+market|on\s+the\s+market|shall\s+apply\s+from)", re.IGNORECASE)
ANY_DATE_RE = re.compile(DATE)


def unclassified_mentions(text, provisions, origin):
    """Dated market sentences that no construction claimed.

    This is the tripwire. If EUR-Lex starts phrasing a deadline in a way this
    script does not recognise, the sentence is written into the register as an
    open question rather than dropped.
    """
    spans = [p["span"] for p in provisions]
    out = []
    for m in MARKET_MENTION_RE.finditer(text):
        if any(a <= m.start() and m.end() <= b for a, b in spans):
            continue
        sentence = sentence_around(text, m.start(), m.end())
        if not ANY_DATE_RE.search(sentence):
            continue
        if any(sentence == p["text"] for p in provisions):
            continue
        out.append({"origin": origin, "sentence": sentence})
    seen, unique = set(), []
    for item in out:
        if item["sentence"] in seen:
            continue
        seen.add(item["sentence"])
        unique.append(item)
    return unique


# ---------------------------------------------------------------------------
# Annex tables
# ---------------------------------------------------------------------------

# An annex amendment is introduced in several ways: "Annex II is amended as
# follows", "in Annex V, the following entry is added", "in Annex VI, entry 28
# is replaced by the following". All three have to set the current annex, or
# every entry after the first heading is filed under the wrong annex.
ANNEX_HEADING_RE = re.compile(
    r"\bAnnex\s+([IVX]+)\b[^.]{0,120}?\b(?:is\s+amended|are\s+amended"
    r"|is\s+replaced\s+by\s+the\s+following|are\s+replaced\s+by\s+the\s+following"
    r"|the\s+following\s+entr(?:y|ies)\s+(?:is|are)\s+(?:added|inserted)"
    r"|(?:is|are)\s+replaced\s+by\s+the\s+text\s+set\s+out"
    r"|(?:is|are)\s+deleted)",
    re.IGNORECASE,
)
ANNEX_TITLE_RE = re.compile(r"^ANNEX\s+([IVX]+)\s*$", re.IGNORECASE)


def build_grid(table):
    """Lay a table out as a rectangle, honouring colspan and rowspan."""
    grid = []
    carry = {}  # column index -> [cell, rows remaining]
    for row in table.own_rows():
        if "oj-tblnote" in row.classes():
            grid.append(None)  # placeholder keeps row indexes aligned
            continue
        line = []
        col = 0
        for cell in row.own_cells():
            while col in carry:
                line.append(carry[col][0])
                carry[col][1] -= 1
                if carry[col][1] <= 0:
                    del carry[col]
                col += 1
            try:
                colspan = max(1, int(cell.attrs.get("colspan", "1")))
            except ValueError:
                colspan = 1
            try:
                rowspan = max(1, int(cell.attrs.get("rowspan", "1")))
            except ValueError:
                rowspan = 1
            for _ in range(colspan):
                line.append(cell)
                if rowspan > 1:
                    carry[col] = [cell, rowspan - 1]
                col += 1
        while col in carry:
            line.append(carry[col][0])
            carry[col][1] -= 1
            if carry[col][1] <= 0:
                del carry[col]
            col += 1
        grid.append(line)
    return grid


def is_header_row(row):
    return bool(row.find_all("p", cls="oj-tbl-hdr")) and not row.find_all("p", cls="oj-tbl-txt")


def column_labels(table, grid):
    rows = table.own_rows()
    labels = {}
    header_count = 0
    for index, row in enumerate(rows):
        if grid[index] is None:
            continue
        if not is_header_row(row):
            break
        header_count = index + 1
        for col, cell in enumerate(grid[index]):
            piece = squash(cell.text())
            if not piece or len(piece) < 2:
                continue
            existing = labels.setdefault(col, [])
            if piece not in existing:
                existing.append(piece)
    return {c: " | ".join(v) for c, v in labels.items()}, header_count


def cell_names(cell):
    """The distinct names written in one table cell."""
    if cell.find_all("table"):
        values = [cell.text()]
    else:
        paragraphs = cell.find_all("p")
        values = [p.text() for p in paragraphs] if paragraphs else [cell.text()]
    names = []
    for value in values:
        value = tidy(MARKER_RE.sub(" ", value))
        value = squash(value)
        if not value or len(value) < 2:
            continue
        if re.fullmatch(r"[-–—\s.,;:%0-9/]+", value):
            continue
        for piece in re.split(r"\s*;\s*", value):
            piece = squash(piece)
            if not piece or len(piece) < 2:
                continue
            if piece not in names:
                names.append(piece)
    return names


TRAILING_BRACKET_RE = re.compile(r"\s*\(([^()]{1,40})\)\s*$")


def name_variants(name):
    """The name plus the spellings a pack is likely to print instead.

    An annex cell writes "Diethylamino Hydroxybenzoyl Hexyl Benzoate (DHHB)".
    A label prints one or the other. Both have to match, or the deadline is
    silently missed.
    """
    variants = [(name, "as written")]
    m = TRAILING_BRACKET_RE.search(name)
    if m:
        stem = squash(name[:m.start()])
        inner = squash(m.group(1))
        if len(stem) >= 3:
            variants.append((stem, "without the bracketed suffix"))
        if re.fullmatch(r"[A-Za-z0-9-]{2,12}", inner):
            variants.append((inner, "bracketed short form"))
    return variants


def find_column(labels, needle):
    for col, label in sorted(labels.items()):
        if needle in label.lower():
            return col
    return None


def read_entries(root):
    """Every annex entry amended by this regulation, with its footnote markers."""
    entries = []
    unreadable = []
    title_annexes = read_title_annexes(root)
    annex = title_annexes[0] if len(title_annexes) == 1 else None
    for node in root.walk():
        if node.tag == "p":
            # Only a heading outside the annex tables and outside the recitals
            # may set the annex. A cross reference inside a table cell, such as
            # "under the conditions set out in entry 61 in Annex V", must not.
            if any(x.tag == "table" and "oj-table" in x.classes() for x in node.ancestors()):
                continue
            if any(x.attrs.get("id", "").startswith("rct") for x in node.ancestors()):
                continue
            text = squash(node.text())
            if text and len(text) < 400:
                m = ANNEX_TITLE_RE.match(text) or ANNEX_HEADING_RE.search(text)
                if m:
                    annex = m.group(1).upper()
            continue
        if node.tag != "table" or "oj-table" not in node.classes():
            continue
        if any(a.tag == "table" and "oj-table" in a.classes() for a in node.ancestors()):
            continue
        entries.extend(read_table(node, annex, unreadable))
    return entries, unreadable


ENTRY_REFERENCE_RE = re.compile(r"^[\u2018\u2019'\"]?\s*\d{1,4}\s*[a-z]?\s*[)\]]?\s*[\u2018\u2019'\"]?$",
                                re.IGNORECASE)


def infer_columns(width):
    """Column positions for an annex table printed without a text header.

    The older EUR-Lex renderings label the columns only with the letters a to i.
    The layouts are fixed by the Cosmetics Regulation itself, so the position of
    the glossary column follows from the width. An unfamiliar width returns
    nothing, and the table is reported as unread rather than guessed at.
    """
    if width == 4:            # Annex II: reference, chemical name, CAS, EC
        return 0, 1, None
    if 8 <= width <= 10:      # Annexes III, IV, V and VI
        return 0, 1, 2
    return None


def read_table(table, annex, unreadable):
    # An amendment that only deletes an entry prints the entry number alone.
    # There is no substance in it, and it is not a gap in the reading.
    if ENTRY_REFERENCE_RE.match(squash(table.text())):
        return []
    grid = build_grid(table)
    labels, header_count = column_labels(table, grid)
    glossary_col = find_column(labels, "common ingredients glossary")
    chemical_col = find_column(labels, "chemical name")
    reference_col = find_column(labels, "reference number")
    layout = "column headings"

    if glossary_col is None and chemical_col is None:
        widths = [len(line) for line in grid[header_count:] if line]
        width = max(set(widths), key=widths.count) if widths else 0
        guess = infer_columns(width)
        first = None
        for line in grid[header_count:]:
            if line:
                first = squash(line[0].text())
                break
        if guess is None or not first or not ENTRY_REFERENCE_RE.match(first):
            unreadable.append({
                "annex": annex,
                "columns": width,
                "first_cell": (first or "")[:80],
                "sample": table.text()[:200],
                "reason": ("this table carries no readable column headings and its shape "
                           "does not match a known annex layout, so no substance was taken "
                           "from it"),
            })
            return []
        reference_col, chemical_col, glossary_col = guess
        layout = "inferred from the table shape"

    rows = table.own_rows()
    entries = []
    for index in range(header_count, len(rows)):
        line = grid[index]
        if line is None:
            continue
        row = rows[index]
        if is_header_row(row):
            continue
        row_text = row.text()
        if not squash(row_text):
            continue

        def column_text(col):
            if col is None or col >= len(line):
                return ""
            return squash(line[col].text())

        def column_names(col):
            if col is None or col >= len(line):
                return []
            return cell_names(line[col])

        inci = column_names(glossary_col)
        chemical = column_names(chemical_col)
        if not inci and not chemical:
            continue

        names = []
        seen_keys = set()

        def add(value, source):
            for variant, form in name_variants(value):
                key = normalise_name(variant)
                if not key or key in seen_keys:
                    continue
                # A trailing bracket in a chemical name is sometimes a source
                # cross reference rather than a synonym, as in
                # "...-2-buten-1-one (16)". Splitting that out produced a
                # matchable substance called "16", which any label carrying a
                # bare number would have matched. A substance name is never a
                # bare number and never one or two characters.
                if key.isdigit() or len(key) < 3:
                    continue
                seen_keys.add(key)
                names.append({"name": variant, "source": source, "form": form, "key": key})

        for value in inci:
            add(value, "inci_glossary")
        for value in chemical:
            add(value, "chemical_name")
        if not names:
            continue

        entries.append({
            "layout": layout,
            "annex": annex,
            "entry_reference": tidy(column_text(reference_col)) or None,
            "inci_name": inci[0] if inci else None,
            "chemical_name": chemical[0] if chemical else None,
            "names": names,
            "row_text": squash(row.text())[:2000],
            "markers": sorted(markers_in_node(row)),
        })
    return entries


def read_footnotes(root):
    """Transitional footnotes, in both markup families EUR-Lex serves."""
    notes = []

    # Family A: a footnote row inside the annex table.
    for row in root.find_all("tr", cls="oj-tblnote"):
        for inner in row.find_all("tr"):
            cells = inner.own_cells()
            if len(cells) < 2:
                continue
            marker_set = markers_in(cells[0].text())
            if not marker_set:
                continue
            body = squash(" ".join(c.text() for c in cells[1:]))
            notes.append({"marker": sorted(marker_set)[0], "text": tidy(body)})

    # Family B: a footnote paragraph printed under the table.
    for para in root.find_all("p", cls="oj-note"):
        marker = None
        for anchor in para.find_all("a"):
            for m in ANCHOR_MARKER_RE.finditer(anchor.attrs.get("id", "") + " "):
                marker = "(" + m.group(1) + ")"
        if marker is None:
            continue
        body = para.text()
        body = MARKER_RE.sub(" ", body, count=1)
        notes.append({"marker": marker, "text": tidy(body)})

    merged = {}
    for note in notes:
        merged.setdefault(note["marker"], set()).add(note["text"])
    return [
        {"marker": marker, "text": " ".join(sorted(texts))}
        for marker, texts in sorted(merged.items())
    ]


def read_article_paragraphs(root):
    """Body paragraphs outside the annex tables and outside the recitals."""
    out = []
    for para in root.find_all("p", cls="oj-normal"):
        skip = False
        for ancestor in para.ancestors():
            if ancestor.tag == "table" and "oj-table" in ancestor.classes():
                skip = True
                break
            if ancestor.attrs.get("id", "").startswith("rct"):
                skip = True
                break
        if skip:
            continue
        text = squash(para.text())
        if text:
            out.append(text)
    return out


TITLE_ANNEX_RE = re.compile(r"amending\s+Annex(?:es)?\s+((?:[IVX]+(?:\s*,\s*|\s+and\s+)?)+)\s+to\s+Regulation",
                            re.IGNORECASE)


def read_title_annexes(root):
    """The annexes named in the regulation's own title.

    Used only as a fallback. When the title names exactly one annex, an entry
    with no heading above it can safely be filed there. When it names several,
    the entry keeps a null annex rather than a guess.
    """
    for node in root.find_all("p"):
        if node.attrs.get("id") not in ("title", "englishTitle"):
            continue
        m = TITLE_ANNEX_RE.search(squash(node.text()))
        if m:
            found = re.findall(r"[IVX]+", m.group(1).upper())
            if found:
                return found
    return []


def read_title(root, celex):
    for node in root.find_all("p"):
        if node.attrs.get("id") in ("title", "englishTitle"):
            text = squash(node.text())
            m = re.search(r"(Commission\s+Regulation\s+\(E[UC]\)\s+(?:No\s+)?[\d/]+)", text)
            if m:
                return squash(m.group(1))
    m = re.match(r"3(\d{4})R(\d{4})", celex)
    if m:
        return "Commission Regulation (EU) {}/{}".format(m.group(1), int(m.group(2)))
    return celex


# ---------------------------------------------------------------------------
# Per regulation
# ---------------------------------------------------------------------------

def analyse(celex, markup):
    body = markup[markup.find("<body"):] or markup
    root = parse_html(body)

    title = read_title(root, celex)
    entries, unreadable_tables = read_entries(root)
    footnotes = read_footnotes(root)
    articles = read_article_paragraphs(root)

    marker_index = {}
    for entry in entries:
        for marker in entry["markers"]:
            marker_index.setdefault(marker, []).append(entry)

    records = []
    unresolved = []
    unclassified = []
    provision_count = 0

    for note in footnotes:
        origin = "footnote " + note["marker"]
        provisions = find_provisions(note["text"], origin)
        unclassified.extend(unclassified_mentions(note["text"], provisions, origin))
        if not provisions:
            continue
        linked = marker_index.get(note["marker"], [])
        for provision in provisions:
            provision_count += 1
            if linked:
                for entry in linked:
                    records.append(make_record(celex, title, entry, provision,
                                               "footnote marker " + note["marker"]))
            else:
                unresolved.append({
                    "celex": celex,
                    "regulation": title,
                    "date": provision["date"],
                    "restriction": provision["restriction"],
                    "reason": ("footnote marker {} carries a dated restriction but no annex "
                               "entry in this regulation is marked with it, so the substances "
                               "it covers could not be identified").format(note["marker"]),
                    "provision": provision["text"],
                })

    article_text = " ".join(articles)
    provisions = find_provisions(article_text, "article")
    for m in PARTIAL_APPLICATION_RE.finditer(article_text):
        stated = to_date(m.group(1), m.group(2), m.group(3))
        provision_count += 1
        provisions.append({
            "construction": "partial_application", "restriction": APPLICATION,
            "basis": "from", "stated_date": stated.isoformat(), "date": stated.isoformat(),
            "span": (m.start(), m.end()), "text": sentence_around(article_text, m.start(), m.end()),
            "origin": "article", "regulation_wide": False, "partial": True,
        })
        unresolved.append({
            "celex": celex, "regulation": title, "date": stated.isoformat(),
            "restriction": APPLICATION,
            "reason": ("part of this regulation starts to apply on this date, but the "
                       "provision points at a numbered part of the annex rather than at "
                       "named substances, so which substances it covers is not readable "
                       "from the text"),
            "provision": sentence_around(article_text, m.start(), m.end()),
        })
    unclassified.extend(unclassified_mentions(article_text, provisions, "article"))
    for provision in provisions:
        if provision.get("partial"):
            continue
        provision_count += 1
        if provision["regulation_wide"] and entries:
            for entry in entries:
                records.append(make_record(celex, title, entry, provision,
                                           "provision applies to every substance this "
                                           "regulation amends"))
            continue
        named = [e for e in entries
                 if any(n["key"] and n["key"] in normalise_name(provision["text"])
                        for n in e["names"])]
        if named:
            for entry in named:
                records.append(make_record(celex, title, entry, provision,
                                           "substance named in the provision"))
            continue
        unresolved.append({
            "celex": celex,
            "regulation": title,
            "date": provision["date"],
            "restriction": provision["restriction"],
            "reason": ("a dated restriction in the body of the regulation could not be "
                       "tied to any annex entry, so the substances it covers could not "
                       "be identified"),
            "provision": provision["text"],
        })

    seen = set()
    deduped = []
    for record in records:
        if record["id"] in seen:
            continue
        seen.add(record["id"])
        deduped.append(record)

    return {
        "celex": celex,
        "regulation": title,
        "entries_found": len(entries),
        "unreadable_tables": [dict(t, celex=celex, regulation=title) for t in unreadable_tables],
        "footnotes_found": len(footnotes),
        "provisions_found": provision_count,
        "records": deduped,
        "unresolved": unresolved,
        "unclassified": [dict(item, celex=celex, regulation=title) for item in unclassified],
    }


def make_record(celex, title, entry, provision, resolution):
    identifier = "{}:{}:{}:{}:{}".format(
        celex,
        entry["annex"] or "?",
        entry["entry_reference"] or entry["names"][0]["key"][:40],
        provision["date"],
        provision["restriction"],
    )
    return {
        "id": identifier,
        "celex": celex,
        "table_layout": entry.get("layout"),
        "regulation": title,
        "annex": entry["annex"],
        "entry_reference": entry["entry_reference"],
        "inci_name": entry["inci_name"],
        "chemical_name": entry["chemical_name"],
        "names": entry["names"],
        "row_text": entry.get("row_text"),
        "date": provision["date"],
        "stated_date": provision["stated_date"],
        "basis": provision["basis"],
        "restriction": provision["restriction"],
        "restriction_plain": RESTRICTION_PLAIN[provision["restriction"]],
        "resolution": resolution,
        "provision": provision["text"],
    }


# What a rule actually asks for decides whether a printed ingredient list can
# evidence anything against it.
#
# A duty to LABEL says the substance must be named in the list of ingredients
# above a threshold. Regulation (EU) 2023/1545 is the large example: "The
# presence of the substance shall be indicated in the list of ingredients
# referred to in Article 19(1), point (g), when its concentration exceeds
# 0,001 % in leave-on products". A list that names the substance is therefore
# doing what the rule asks. The products at risk are the ones that print only
# "parfum" and never name it, and no check that reads printed names can see
# them. Reporting a label that names the substance as though it faced a
# deadline points the reader the wrong way.
#
# A restriction on USE sets a maximum concentration or a permitted product
# type. There, the presence of the name is evidence the product contains the
# substance, the date is real for that product, and the reader has something to
# check their formulation against.
LABELLING_SENTENCE = re.compile(
    r"The presence of the substances?(?:\s+or\s+substances)?\s+shall be"
    r" (?:indicated|declared).*?rinse-off products\.?",
    re.I | re.S)

LABELLING_DUTY = re.compile(
    r"(?:indicated|declared)\s+(?:as\s+.{0,80}?\s+)?in the list of ingredients",
    re.I)

# A maximum concentration or permitted product type surviving the removal of the
# labelling sentence. Annex III entry 75 as replaced by Regulation (EU) 2026/909
# carries BOTH a 4 % maximum and the labelling sentence, so reading the
# labelling phrase alone would discard a real restriction.
CONCENTRATION = re.compile(r"\d+(?:[.,]\d+)?\s*%")

# Wording that shows the row carried some condition at all. Without one of
# these, and without a percentage, the row holds only a name, a CAS number and
# an EC number, which means the restriction text was not recovered rather than
# that there is none. Several Annex III entries are printed as multiple rows
# with the conditions on a parent row.
CONDITION_WORDING = re.compile(
    r"\bproducts?\b|\bbody parts\b|\bconcentration\b|\bready for use\b"
    r"|\bpurposes?\b|\bperoxide value\b|\bppm\b|\bshall\b|\bmust\b"
    r"|\bnot exceed\b|\bmaximum\b",
    re.I)

USE_RESTRICTION = "use_restriction"
LABELLING = "labelling"
NOT_RECOVERED = "restriction_text_not_recovered"


def obligation_of(record):
    """What this entry asks of a product, judged from the entry's own text.

    Three answers, because two would force a false one. A restriction on use is
    reported as a finding. A duty to name the substance in the list is not, and
    is explained instead, since a list that names it is doing what the rule
    asks. A row whose restriction text was never recovered is neither: it is
    reported as a gap, because promoting it would invent a finding and
    demoting it would hide one.
    """
    text = record.get("row_text") or ""

    # Annex II is the prohibited list. An entry there needs no conditions
    # column: being in it is the restriction.
    if (record.get("annex") or "").upper() == "II":
        return USE_RESTRICTION

    remainder = LABELLING_SENTENCE.sub(" ", text)
    if CONCENTRATION.search(remainder):
        return USE_RESTRICTION
    if LABELLING_DUTY.search(text):
        return LABELLING
    if not CONDITION_WORDING.search(remainder):
        return NOT_RECOVERED
    return USE_RESTRICTION


def placing_limb_already_passed(record, today):
    """True when this entry's own provision shows the rule is already biting.

    Regulation (EU) 2023/1545 states its transition as "may be placed on the
    Union market until 31 July 2026 and made available on the Union market
    until 31 July 2028". On 18 September 2026 the first limb has passed. The
    remaining date is a sell-through end for a rule already in force, not a
    rule that starts to apply later, and calling it the latter is false.
    """
    text = record.get("provision") or ""
    for match in re.finditer(r"placed on the Union market until " + DATE, text):
        try:
            when = to_date(match.group(1), match.group(2), match.group(3))
        except Exception:
            continue
        if when <= today:
            return True
    for match in re.finditer(r"From " + DATE + r"[^.]{0,200}?shall not be placed", text):
        try:
            when = to_date(match.group(1), match.group(2), match.group(3))
        except Exception:
            continue
        if when <= today:
            return True
    return False


CATEGORY_NAME = re.compile(
    r"with the exception of those listed"
    r"|^[\d,\s]+of Annex"
    r"|^[\d,\s]+$",
    re.I)


def names_a_category(record):
    names = [n["name"] for n in record.get("names") or []]
    if not names:
        return False
    return all(CATEGORY_NAME.search(n) for n in names)


# ---------------------------------------------------------------------------
# Fetching
# ---------------------------------------------------------------------------

# The smallest real document in scope is about 250 kB. A short body means a
# consent page, a rate limit, or a cut connection. EUR-Lex answers 200 to all of
# those, and a 200 with nothing in it reads exactly like a regulation with no
# deadlines, which is the one wrong answer this tool must never give.
MINIMUM_DOCUMENT_BYTES = 20000


class BadDocument(Exception):
    pass


def check_document(celex, markup):
    if len(markup) < MINIMUM_DOCUMENT_BYTES:
        raise BadDocument(
            "the response for {} was only {} characters, far short of a regulation; "
            "it was not read".format(celex, len(markup)))
    if "<body" not in markup.lower():
        raise BadDocument("the response for {} had no document body".format(celex))
    if 'class="oj-' not in markup:
        raise BadDocument(
            "the response for {} carries none of the Official Journal markup the "
            "parser needs".format(celex))
    return markup


def fetch(celex, cache_dir, pause):
    path = os.path.join(cache_dir, celex + ".html") if cache_dir else None
    if path and os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            return check_document(celex, handle.read()), "cache"
    request = urllib.request.Request(EURLEX_URL.format(celex=celex),
                                     headers={"User-Agent": USER_AGENT,
                                              "Accept": "text/html",
                                              "Accept-Language": "en"})
    with urllib.request.urlopen(request, timeout=90) as response:
        markup = response.read().decode("utf-8", "replace")
    check_document(celex, markup)  # a bad response is never cached
    if path:
        os.makedirs(cache_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(markup)
    time.sleep(pause)
    return markup, "network"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the On Notice register from EUR-Lex.")
    parser.add_argument("--out", default="on_notice/register.json")
    parser.add_argument("--cache-dir", default=".cache")
    parser.add_argument("--today", default=None,
                        help="Scan boundary, default the system date. Provisions on or "
                             "before this date are counted but not shipped.")
    parser.add_argument("--celex", nargs="*", default=None)
    parser.add_argument("--pause", type=float, default=0.5)
    parser.add_argument("--keep-past", action="store_true",
                        help="Ship past provisions too. For inspection, not for release.")
    args = parser.parse_args(argv)

    today = (datetime.date.fromisoformat(args.today) if args.today
             else datetime.date.today())
    celexes = args.celex or CELEX_IDS

    records, unresolved, unclassified, failures, unreadable = [], [], [], [], []
    fetched = 0
    provisions_found = 0
    per_regulation = []

    for celex in celexes:
        try:
            markup, where = fetch(celex, args.cache_dir, args.pause)
        except Exception as error:  # network, refusal, or a removed document
            failures.append({
                "celex": celex,
                "error": "{}: {}".format(type(error).__name__, error),
                "consequence": ("this regulation was not read at all, so any deadline it "
                                "carries is missing from this register"),
            })
            print("  {}  FETCH FAILED  {}".format(celex, error), file=sys.stderr)
            continue
        fetched += 1
        result = analyse(celex, markup)
        records.extend(result["records"])
        unresolved.extend(result["unresolved"])
        unclassified.extend(result["unclassified"])
        unreadable.extend(result["unreadable_tables"])
        provisions_found += result["provisions_found"]
        per_regulation.append({
            "celex": celex,
            "regulation": result["regulation"],
            "source": where,
            "annex_entries_read": result["entries_found"],
            "footnotes_read": result["footnotes_found"],
            "dated_provisions_found": result["provisions_found"],
            "substance_links_made": len(result["records"]),
            "substance_links_unresolved": len(result["unresolved"]),
        })
        print("  {}  entries {:>4}  provisions {:>3}  links {:>4}  unresolved {}".format(
            celex, result["entries_found"], result["provisions_found"],
            len(result["records"]), len(result["unresolved"])), file=sys.stderr)

    future = [r for r in records
              if args.keep_past or datetime.date.fromisoformat(r["date"]) > today]
    for record in future:
        record["obligation"] = obligation_of(record)
        record["already_applying"] = placing_limb_already_passed(record, today)
    uncheckable = [r for r in future if names_a_category(r)]
    rest = [r for r in future if not names_a_category(r)]
    labelling_only = [r for r in rest if r["obligation"] == LABELLING]
    not_recovered = [r for r in rest if r["obligation"] == NOT_RECOVERED]
    shipped = [r for r in rest if r["obligation"] == USE_RESTRICTION]
    shipped.sort(key=lambda r: (r["date"], (r["inci_name"] or r["chemical_name"] or "").lower()))

    future_unresolved = [u for u in unresolved
                         if args.keep_past or datetime.date.fromisoformat(u["date"]) > today]

    substances = sorted({(r["inci_name"] or r["chemical_name"]) for r in shipped})

    register = {
        "schema_version": 1,
        "built": datetime.date.today().isoformat(),
        "scan_boundary": {
            "today": today.isoformat(),
            "rule": ("only provisions that start applying after this date are shipped; "
                     "anything already in force is counted below but left out, because "
                     "this tool reports what is coming, not what is already the case"),
            "earliest_amendment_covered": "2013",
            "instrument": INSTRUMENT,
        },
        "source": {
            "name": "EUR-Lex",
            "url_pattern": EURLEX_URL,
            "what_was_read": ("the English consolidated text of each Commission regulation "
                              "amending " + INSTRUMENT),
        },
        "celex_scanned": celexes,
        "counts": {
            "regulations_listed": len(celexes),
            "regulations_read": fetched,
            "regulations_not_read": len(failures),
            "dated_provisions_found": provisions_found,
            "substance_links_made": len(records),
            "substance_links_shipped": len(shipped),
            "provisions_naming_a_category": len(uncheckable),
            "provisions_that_are_labelling_duties": len(labelling_only),
            "provisions_with_no_restriction_text_recovered": len(not_recovered),
            "shipped_entries_already_applying": sum(
                1 for r in shipped if r["already_applying"]),
            "distinct_substances_labelling_only": len(
                {(r["inci_name"] or r["chemical_name"]) for r in labelling_only}),
            "distinct_substances_shipped": len(substances),
            "unresolved_provisions_total": len(unresolved),
            "unresolved_provisions_shipped": len(future_unresolved),
            "unclassified_sentences": len(unclassified),
            "unreadable_tables": len(unreadable),
        },
        "fetch_failures": failures,
        "uncheckable": uncheckable,
        "labelling_only": labelling_only,
        "restriction_text_not_recovered": not_recovered,
        "unresolved": future_unresolved,
        "unclassified_sentences": unclassified,
        "unreadable_tables": unreadable,
        "per_regulation": per_regulation,
        "entries": shipped,
    }

    directory = os.path.dirname(os.path.abspath(args.out))
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(register, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    print("\nWrote {}".format(args.out), file=sys.stderr)
    for key, value in register["counts"].items():
        print("  {:<34} {}".format(key, value), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
