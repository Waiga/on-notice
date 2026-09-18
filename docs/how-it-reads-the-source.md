# How the register is built

Notes on what the source documents actually look like, written down because the
first version of this parser got each of these wrong.

## Where the text comes from

`https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A<CELEX>`, with a
browser User-Agent. The builder keeps a local cache so a rebuild does not hammer
EUR-Lex.

## Two markup families

EUR-Lex serves the same kind of document two different ways, and both are live.

**The newer rendering** puts the transitional footnote inside the annex table as
a row of its own:

```html
<tr class="oj-tblnote">
  <td colspan="4"><table><tbody><tr>
    <td><p class="oj-normal">'(*)</p></td>
    <td><p class="oj-normal">From 1 January 2027 ... shall not be placed on the Union market.</p></td>
  </tr></tbody></table></td>
</tr>
```

**The older rendering** puts it in a paragraph under the table, and hides the
marker in an anchor id:

```html
<p class="oj-note">
  <a id="ntr*1-L_2018176EN.01000501-E0001">(<span class="oj-super">*1</span>)</a>
  From 1 May 2019 cosmetic products containing that substance shall not be placed ...
</p>
```

The builder reads both. A marker is normalised to `(*)`, `(**)`, `(*1)` and so
on, because the flattened text spells the same marker as `(*1)`, `( *1 )` and
`( * )` in different documents.

## Linking a footnote to a substance

Footnotes rarely name the substance. They say "that substance" or "these
substances". The link runs through the marker: an entry row carrying `(**)`
anywhere in it is covered by footnote `(**)`.

Markers are unique within one regulation by Official Journal convention, and
they are not unique per table: in Regulation 2026/909, `(**)` is carried by
entries in two separate amendment blocks and defined once. So the link is made
across the whole regulation, not within one table.

Where several names sit in one row and carry different markers, every name in
the row is linked to every marker in it. That over reports rather than under
reports, which is the right direction for this tool.

## Which column is the name

`Name of Common Ingredients Glossary` is the INCI name and the one a pack
prints. `Chemical name/INN` is not. Both are kept and both are matchable, but
the glossary name is what gets shown.

Annex II, the prohibited list, has no glossary column at all. Its entries are
matched on the chemical name, which for Annex II is usually what a label would
print anyway.

The older documents print no text headings, only the column letters `a` to `i`.
For those the column positions are inferred from the table width, which is fixed
by the Cosmetics Regulation itself: four columns is Annex II, eight to ten is
one of Annexes III to VI. A table that is neither, and whose first cell is not an
entry number, is recorded as unread rather than guessed at.

## The four dated constructions

1. `From <date> ... shall not be placed on the Union market`
2. `From <date> ... shall not be made available on the Union market`
3. `may be placed on the Union market until <date>` and
   `made available on the Union market until <date>`
4. `From <date> only cosmetic products which comply ... shall be placed on the Union market`

Plus `This Regulation shall apply from <date>` for a regulation that is adopted
now and starts applying later with no transitional footnote at all.

Form 3 is the one that catches people out. It states a last lawful day, not a
first restricted day, so the effective date is the day after. Regulation
2023/1545 carries a 31 July 2028 making available deadline in exactly that
shape, and a parser that only looks for "shall not be" misses all sixty of its
substances.

One date must not bind to the phrase in the next sentence. A footnote often
reads "From 1 January 2027 ... placed ... . From 1 July 2028 ... made available
...", and a pattern allowing any characters between the date and the phrase
happily pairs the first date with the second phrase. The patterns stay inside a
sentence.

## The tripwire

After the known constructions have claimed their spans, every remaining sentence
that mentions a date together with the Union market or the words "shall apply
from" is written into the register as an unclassified sentence. If EUR-Lex
starts phrasing deadlines a new way, the register says so rather than going
quiet.
