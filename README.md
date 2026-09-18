# On Notice

Reads a cosmetic ingredient list and reports which ingredients on it are named in
an EU rule that has already been adopted but has not started to apply yet, and
from what date.

It does not say whether a product may be sold. It reports dates.

## Why this one exists

The other tools in this set check what is wrong with a document today. A cosmetic
reformulation takes the better part of a year, so the question that actually costs
money is the other one: what becomes wrong while the stock is still on the shelf.

Regulation (EU) 2026/909 was adopted on 27 April 2026. It restricts Benzyl
Salicylate, among others, in fragrance products to 4 per cent, and the date it
bites is 1 January 2027. A product on a shelf today can be entirely lawful and
already be on a clock, and nothing on the pack says so.

## Use

```bash
on-notice ingredients.txt
on-notice --unresolved          # everything the register could not settle
cat list.txt | on-notice -
```

Exit code is 1 when something on the list has a date, 0 when nothing does, 2 when
the register cannot be read.

```
on-notice 0.1.0   register built 2026-09-18
read 5 ingredient(s) from night-cream.txt

2 of them are named in an EU rule that is already adopted and starts to apply later.

1 January 2027   products that do not meet the new restriction cannot be placed on the Union market
    Benzyl Salicylate
      on the label as   Benzyl Salicylate
      named in          Commission Regulation (EU) 2026/909, Annex III entry 75
      the rule says     From 1 January 2027 cosmetic products containing these substances and not complying with the restrictions shall not be placed on the Union market.
```

The register ships inside the package. Nothing leaves your machine.

## What it was measured against

17,626 published cosmetic products from Open Beauty Facts carry an ingredient
list. 31 of those lists yielded no readable ingredient names at all, leaving
**17,595 lists read**, median 17 ingredients each. None of them was written by
this tool or by anybody connected to it.

**3,270 of the 17,595, or 18.6 per cent, name at least one substance carrying a
future restriction.** Of those, 2,828 name one such substance, 386 name two, and
56 name three or more.

The substances actually driving it, counted by the number of lists naming each:

| Substance | Lists | First date |
|---|---:|---|
| Benzyl Salicylate | 1,614 | 1 January 2027 |
| Citral | 1,416 | 1 January 2027 |
| Diethylamino Hydroxybenzoyl Hexyl Benzoate | 190 | 1 January 2027 |
| Eucalyptus Globulus Leaf Oil | 94 | 1 August 2028 |
| Retinol | 47 | 1 May 2027 |
| Triphenyl Phosphate | 3 | 1 January 2027 |

31 of the register's substances were seen at least once in the corpus. The rest
appear in no published list it read, which is a fact about the corpus and not
evidence that nothing uses them.

## The first number this tool produced was wrong, and the reason is the point

The first complete run reported that **44.0 per cent** of the corpus faced a
future deadline. That number was wrong, and it was wrong in the direction that
would have flattered the tool most: a bigger, more alarming finding.

Roughly sixty of the substances in the first register came from Regulation (EU)
2023/1545, which is titled "as regards labelling of fragrance allergens". What
that regulation requires is this, quoted from Annex III as it amends it:

> The presence of the substance shall be indicated in the list of ingredients
> referred to in Article 19(1), point (g), when its concentration exceeds:
> 0,001 % in leave-on products, 0,01 % in rinse-off products.

The duty it creates is to **name the substance in the list of ingredients**. So
when a tool that reads printed ingredient names found Limonene on 5,301 labels,
it had not found 5,301 products facing a deadline. It had found 5,301 products
doing the thing the rule asks for. The products actually at risk are the ones
that print only `parfum` and never name the allergen, and no check that reads
printed names can see a single one of them.

The finding pointed the opposite way from what a reader would have assumed.

The fix is not to drop those substances silently. Each register entry is now
classified from its own text: the labelling sentence is removed, and if a
maximum concentration or a permitted product type survives that removal, the
entry is a restriction on use and is reported. If nothing survives, it is a
labelling duty and the tool says so in plain words instead of counting it.

That distinction is not academic, and getting it wrong in either direction is
easy. Annex III entry 75 as replaced by Regulation 2026/909 carries **both**: a
4 per cent maximum in fragrance products and the labelling sentence. A first
attempt at the fix looked for the labelling phrase and filed the whole entry as
a labelling duty, which discarded a real restriction on 1,614 products. That is
the same error with the sign flipped, and it was caught the same way, by reading
the entry rather than the regulation's title.

**18.6 per cent is the number that survives.** It is less than half the first
one.

## What it cannot tell you

**It cannot tell you whether your product complies.** Every restriction in the
register catches products that do not meet a new condition, and the conditions
are concentrations and product types. A printed ingredient list states no
concentrations. So the tool can tell you a date applies to an ingredient you
use, and it cannot tell you which side of that date you are on. The rule text is
printed with every finding so the reader can check their own formulation against
it.

**It cannot see the products at risk under a labelling rule.** 38 substances in
the register carry a dated duty to be named on the pack above a threshold. A
list naming one is meeting that duty. The list that omits it is the one at risk
and is invisible here. The tool reports these separately on every run and never
counts them as findings.

**Two dated restrictions name a class, not a substance.** Annex III entry 379 as
amended by Regulation 2026/909 reads "Aluminium-containing ingredients with the
exception of those listed in entries 34, 50, 189, 190 and 192 of Annex III...".
There is no honest way to match that against a printed name, so it is reported
and never matched.

**One sentence was not interpreted.** A sentence mentioning a date and the Union
market in wording the builder does not recognise is recorded verbatim rather
than guessed at. `on-notice --unresolved` prints it.

**The register is a scan, not the law.** It covers Commission regulations
amending Regulation (EC) No 1223/2009 from 2013 onward, read from EUR-Lex: 52
regulations listed, 52 read, 0 that could not be downloaded. 120 dated
provisions were found and 703 substance links made across all of them; only
those dated after the build date are shipped. 9 provisions could not be tied to
named substances, and every one of those has a date already in the past, so none
reaches the shipped register. National rules, rules outside the Cosmetics
Regulation, and anything adopted after the build date are all outside it.

**A quiet answer is not a clean bill.** The tool prints what it could not see on
every run, including runs that find nothing.

## How the register is built

`scripts/build_register.py` reads each regulation from EUR-Lex, parses the annex
tables, links footnote markers to the entries that carry them, and extracts the
dates. It is worth knowing that four separate things about those documents broke
a first attempt at this, all of them silently:

- Regulation 2023/1545 states its deadline as "may be placed on the Union market
  until 31 July 2026", not as "shall not be". A parser looking only for the
  negative form reports nothing for every substance in it.
- A footnote can put two dates and two different restrictions in consecutive
  sentences. A pattern that crosses the sentence boundary pairs the first date
  with the second restriction and every making-available date comes out wrong.
- EUR-Lex serves two different markups for footnotes, and prints the same marker
  three ways.
- Annex attribution reads from lead-in wording that takes several forms, so
  entries were filed under the wrong annex while looking entirely correct.

One fetch also returned HTTP 200 with an empty body, and the build reported it as
a regulation read with no deadlines in it, which is indistinguishable from the
truth. Responses are now checked for Official Journal markup before being
accepted, and a bad one is recorded as a failure rather than cached.

`docs/how-it-reads-the-source.md` records what these documents actually look like.

## Install

Not yet published to the package index.

```bash
git clone https://github.com/Waiga/on-notice
cd on-notice
pip install -e .
```

Python 3.9 or later. No dependencies.

## Licence

MIT.
