# On Notice

Reads a cosmetic ingredient list and reports which ingredients on it are named in
an EU rule that carries a date still ahead of it, and what that date is.

It does not say whether a product may be sold. It reports dates.

What it found across 17,595 real published ingredient lists, and the three wrong
readings of the law it took to get there, is written up in
[Lawful today, and non-compliant on 1 January 2027](https://medium.com/@aryawaiga0/lawful-today-and-non-compliant-on-1-january-2027-6939bdbee908).

## Why this one exists

The other tools in this set check what is wrong with a document today. A cosmetic
reformulation takes the better part of a year, so the question that actually costs
money is the other one: what becomes wrong while the stock is still on the shelf.

Regulation (EU) 2026/909 was adopted on 27 April 2026. It restricts Benzyl
Salicylate in fragrance products to 4 per cent, with lower limits in eight other
product types, and the date it bites is 1 January 2027. A product on a shelf
today can be entirely lawful and already be on a clock, and nothing on the pack
says so.

## Use

```bash
on-notice ingredients.txt
on-notice --unresolved          # everything the register could not settle
cat list.txt | on-notice -
```

Exit code is 1 when something on the list has a date, 0 when nothing does, 2 when
the register cannot be read.

```
on-notice 0.1.3   register built 2026-09-18
read 5 ingredient(s) from night-cream.txt

2 of them are named in an EU rule with a date still ahead of it.

1 January 2027   products that do not meet the new restriction cannot be placed on the Union market
    Benzyl Salicylate
      on the label as   Benzyl Salicylate
      named in          Commission Regulation (EU) 2026/909, Annex III entry 75
      the rule says     From 1 January 2027 cosmetic products containing these substances and not complying with the restrictions shall not be placed on the Union market.
```

The register ships inside the package. Nothing leaves your machine.

## What it was measured against

The corpus is the Open Beauty Facts export, `en.openbeautyfacts.org.products.csv.gz`.
The copy these numbers came from is 17,884,435 bytes, SHA-256
`d527f033d2549b86424db0ef1e87b785f92f53901036afd0c0a24bd629a766a5`, and it holds
64,237 product records. Nothing in it was written by this tool or by anybody
connected to it.

That hash, and not a date, is how you tell whether you have the same file. Open
Beauty Facts republishes the export daily and the server's `Last-Modified` stamp
moves with every republication whether or not the bytes change. Those exact
17,884,435 bytes, with that exact hash, were served under a stamp of 9 September
2026 and again under one of 18 September 2026.

Reproduce every number below:

```bash
curl -sO https://static.openbeautyfacts.org/data/en.openbeautyfacts.org.products.csv.gz
shasum -a 256 en.openbeautyfacts.org.products.csv.gz
python3 scripts/measure_corpus.py en.openbeautyfacts.org.products.csv.gz
```

Those three commands are the whole of it. `scripts/measure_corpus.py` reads the
gzipped export as served, so there is nothing to convert first. It opens with
the file it read and what it found in it:

```
corpus file                   : en.openbeautyfacts.org.products.csv.gz
sha256                        : d527f033d2549b86424db0ef1e87b785f92f53901036afd0c0a24bd629a766a5
bytes                         : 17884435
records in the export         : 64237
products in corpus            : 17626
no ingredient names recovered : 31
lists actually read           : 17595
median ingredients per list   : 17
```

17,626 of the 64,237 records carry an ingredient list. 31 of those lists yielded
no readable ingredient names at all, leaving **17,595 lists read**, median 17
ingredients each. If the hash you get is not the one above, you have a later
export and the counts will differ.

The export is Open Database Licence 1.0, which is share alike and therefore
incompatible with shipping a filtered copy of it inside an MIT repository, so it
is not vendored here. Only the measurements are.

**3,050 of the 17,595, or 17.3 per cent, name at least one substance carrying a
date that has not arrived.** 2,703 name one such substance, 334 name two, 13 name
three.

Counted by the number of lists naming each. A substance is counted once however
the label spelled it. The register holds several names for most of its
substances, and Geranial is one of them: it is a second glossary name for
Citral, not a substance of its own. So the three lists that printed Geranial are
three of Citral's 1,419, and there is no Geranial row. The tool itself still
reports the name it read on your label, so a list printing Geranial is reported
as Geranial.

| Substance | Lists | Date | What the date is |
|---|---:|---|---|
| Benzyl Salicylate | 1,614 | 1 January 2027 | new restriction starts |
| Citral | 1,419 | 1 January 2027 | new restriction starts |
| Diethylamino Hydroxybenzoyl Hexyl Benzoate (DHHB) | 190 | 1 January 2027 | new restriction starts |
| Pinene | 77 | 1 August 2028 | already in force, sell-through ends |
| Methyl Salicylate | 56 | 1 August 2028 | already in force, sell-through ends |
| Retinol | 47 | 1 May 2027 | already in force, sell-through ends |
| Zinc Acetate | 4 | 1 January 2027 | new restriction starts |
| Triphenyl Phosphate | 3 | 1 January 2027 | prohibition starts |

Eight of the register's fourteen substances were seen at least once. The other six
appear in no list it read, which is a fact about this corpus and not evidence that
nothing uses them. Nine distinct register names matched a label, out of the 49
the register can match. Those two counts answer different questions and the
measurement script prints both.

**The corpus is not a sample of the EU market.** Open Beauty Facts is a global,
volunteer-contributed database with a heavy western European skew. It is what was
available and reproducible, not a representative frame, and the percentage above
should be read as a property of that corpus rather than of the market the rules
govern.

## The first number this tool produced was wrong three times, each time in its own favour

The first complete run reported **44.0 per cent**. Then **18.6 per cent**. The
number that survived scrutiny is **17.3 per cent**. Every correction moved it
down, which is to say every error made the tool look more impressive than it was.

**First error: it counted compliance as exposure.** Around fifty of the substances
in the first register came from Regulation (EU) 2023/1545, titled "as regards
labelling of fragrance allergens". Quoted from Annex III as it amends it:

> The presence of the substance shall be indicated in the list of ingredients
> referred to in Article 19(1), point (g), when its concentration exceeds:
> 0,001 % in leave-on products, 0,01 % in rinse-off products.

The duty is to **name the substance in the list of ingredients**. So when a tool
that reads printed ingredient names found Limonene on 5,301 labels, it had found
5,301 products doing the thing the rule asks for. The products actually at risk
print only `parfum` and never name the allergen, and no check that reads printed
names can see a single one of them. The finding pointed the opposite way from
what a reader would have assumed.

**Second error, fixing the first: it threw away a real restriction.** Annex III
entry 75 as replaced by Regulation 2026/909 carries **both** a 4 per cent maximum
in fragrance products and the labelling sentence. A first fix matched the
labelling phrase and filed the whole entry as a labelling duty, discarding a real
restriction on 1,614 products. Same error, sign reversed.

**Third error: the fix had a hole big enough for ten entries.** The strip matched
only "The presence of **the substance** shall be indicated". Many entries read
"The presence of the substance **or substances** shall be indicated **as
'Eucalyptus Globulus Oil'**". Those were never stripped, so the 0,001 per cent
labelling threshold inside the sentence was read as a concentration limit and ten
labelling-only entries shipped as findings. One of them, Eucalyptus Globulus Leaf
Oil at 94 lists, was the fourth row of an earlier draft of the table above.

Entries are now classified from their own text, three ways rather than two. The
labelling sentence is removed; a maximum concentration or permitted product type
surviving that removal makes it a restriction on use. An entry in Annex II is a
prohibition and needs no conditions column. An entry whose restriction text was
never recovered is reported as neither, because promoting it invents a finding
and dropping it hides a date.

A separate defect from the same audit: the chemical name
`1-(2,6,6-trimethyl-2-cyclohexen-1-yl)-2-buten-1-one (16)` had its trailing
bracket split off as a synonym, producing a matchable substance named `16`. Any
label carrying a bare 16 would have matched it.

## What it cannot tell you

**It cannot tell you whether your product complies.** Every restriction here
catches products that do not meet a new condition, and those conditions are
concentrations and product types. A printed ingredient list states no
concentrations. The tool can tell you a date applies to an ingredient you use. It
cannot tell you which side of it you are on. The rule text is printed with every
finding so you can check it yourself.

**Some conditions are not formulation choices at all.** The 1 January 2027
condition on Diethylamino Hydroxybenzoyl Hexyl Benzoate is a limit of 10 ppm on a
trace impurity in the filter you buy. Several entries turn on a peroxide value.
Those are answered by a supplier certificate, not by a recipe.

**Some of these rules are already in force.** Regulation 2023/1545's placing limb
passed on 31 July 2026 and Regulation 2024/996's on 1 November 2025. What remains
is the sell-through window. Seven of the 21 shipped entries are in that state and
are labelled as such on every run, because calling a rule already in force "not
yet applying" is simply false.

**It cannot see the products at risk under a labelling rule.** 50 substances carry
a dated duty to be named on the pack above a threshold. A list naming one is
meeting that duty. The list that omits it is the one at risk and is invisible
here. These are reported separately on every run and never counted.

**The percentage understates in one direction as well as overstating in the
other.** Annex III entry 379 as inserted by Regulation 2026/909 covers
"Aluminium-containing ingredients with the exception of those listed in entries
34, 50, 189, 190 and 192 of Annex III...", with the same 1 January 2027 date.
There is no honest way to match a class with an exception list against a printed
name, so it is held back. Aluminium compounds are among the most common things in
antiperspirants and colour cosmetics, so the true number of products in this
corpus carrying a 1 January 2027 obligation is materially higher than 17.3 per
cent. Both sentences belong with the number.

**Three entries had no restriction text recoverable.** Several Annex III entries
print across multiple rows with the conditions on a parent row. Those three are
reported and never matched.

**One sentence was not interpreted.** A sentence mentioning a date and the Union
market in wording the builder does not recognise is recorded verbatim rather than
guessed at. `on-notice --unresolved` prints it.

**The register is a scan, not the law.** It covers Commission regulations amending
Regulation (EC) No 1223/2009 from 2013 onward, read from EUR-Lex: 52 listed, 52
read, 0 that could not be downloaded. 120 dated provisions found, 703 substance
links made, of which 21 are dated after the build and shipped. 9 provisions could
not be tied to named substances; every one has a date already in the past, so none
reaches the shipped register. National rules, rules outside the Cosmetics
Regulation, and anything adopted after the build date are outside it.

**A quiet answer is not a clean bill.** The tool prints what it could not see on
every run, including runs that find nothing.

## How the register is built

`scripts/build_register.py` reads each regulation from EUR-Lex, parses the annex
tables, links footnote markers to the entries carrying them, and extracts the
dates. Four things about those documents broke a first attempt, all silently:

- Regulation 2023/1545 states its deadline as "may be placed on the Union market
  until 31 July 2026", not as "shall not be". A parser looking only for the
  negative form reports nothing for every substance in it.
- A footnote can put two dates and two restrictions in consecutive sentences. A
  pattern crossing the sentence boundary pairs the first date with the second
  restriction, and every sell-through date comes out wrong.
- EUR-Lex serves two different markups for footnotes and prints the same marker
  three ways.
- Annex attribution reads from lead-in wording that takes several forms, so
  entries were filed under the wrong annex while looking entirely correct.

One fetch returned HTTP 200 with an empty body, and the build reported it as a
regulation read with no deadlines in it, which is indistinguishable from the
truth. Responses are now checked for Official Journal markup before being
accepted, and a bad one is recorded as a failure rather than cached.

`docs/how-it-reads-the-source.md` records what these documents actually look like.

## Install

```bash
pip install on-notice
```

Python 3.9 or later. No dependencies. The register ships inside the package, so
the tool works offline and nothing about your formulation leaves your machine.

## Licence

MIT.

## Elsewhere

The rest of these tools, and the writing about what real files did to them, is at
[waiga.github.io](https://waiga.github.io).
