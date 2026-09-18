"""Turning a printed ingredient list into names the register can be asked about."""

from __future__ import annotations

import re
import unicodedata

# What a pack prints around the names themselves.
LEAD_IN = re.compile(r"^\s*(?:ingredients?|inci|composition|zutaten|ingr[ée]dients)\s*[:\-]\s*",
                     re.IGNORECASE)

# Colour index groupings, organic stars, and the "may contain" marker.
NOISE = re.compile(r"(?:\[|\]|\{|\}|\+/-|±|\*+|†|‡)")

SPLIT = re.compile(r"[,;\n\r•·|]+|\s+/\s+")

# Fragments that are list punctuation rather than an ingredient. Nothing that
# could be a substance belongs here: deciding what is uninteresting is the
# register's job, not this parser's.
DROPPABLE = re.compile(r"^(?:may\s+contain|contains?|and|n/a)$", re.IGNORECASE)

PERCENT_ONLY = re.compile(r"^[\d.,%\s<>=]+$")


def clean(value):
    value = unicodedata.normalize("NFKC", value)
    value = NOISE.sub(" ", value)
    value = value.replace("(and)", " ")
    value = re.sub(r"\s+", " ", value).strip()
    value = value.strip(" .:-–—")
    return value


def read_ingredients(text):
    """The ingredient names on a label, in the order they were printed.

    Duplicates are kept out, empty fragments and bare percentages are dropped,
    and nothing else is thrown away. An ingredient this function does not
    recognise is still returned, because the register, not this function,
    decides what is interesting.
    """
    text = LEAD_IN.sub("", text.strip())
    names, seen = [], set()
    for piece in SPLIT.split(text):
        value = clean(piece)
        if not value or len(value) < 2:
            continue
        if PERCENT_ONLY.match(value):
            continue
        if DROPPABLE.match(value):
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        names.append(value)
    return names
