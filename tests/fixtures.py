"""Small pieces of Official Journal markup, shaped like the real thing."""

ANNEX_TABLE = """
<body>
<p id="englishTitle">Commission Regulation (EU) 2099/1 of 1 January 2099 amending
Annexes II and III to Regulation (EC) No 1223/2009</p>
<p class="oj-normal">Annex II is amended as follows:</p>
<table class="oj-table" width="100%">
  <tbody>
    <tr class="oj-table">
      <td><p class="oj-tbl-hdr">Reference number</p></td>
      <td colspan="3"><p class="oj-tbl-hdr">Substance identification</p></td>
    </tr>
    <tr class="oj-table">
      <td><p class="oj-tbl-hdr">&nbsp;</p></td>
      <td><p class="oj-tbl-hdr">Chemical name/INN</p></td>
      <td><p class="oj-tbl-hdr">CAS number</p></td>
      <td><p class="oj-tbl-hdr">EC number</p></td>
    </tr>
    <tr class="oj-table">
      <td><p class="oj-tbl-txt">&#8216;1752</p></td>
      <td><p class="oj-tbl-txt">Triphenyl Phosphate (*)</p></td>
      <td><p class="oj-tbl-txt">115-86-6</p></td>
      <td><p class="oj-tbl-txt">204-112-2&#8217;;</p></td>
    </tr>
    <tr class="oj-tblnote">
      <td colspan="4">
        <table><tbody><tr>
          <td><p class="oj-normal">&#8216;(*)</p></td>
          <td><p class="oj-normal"><span class="oj-italic">From 1 January 2027 cosmetic
          products containing Triphenyl Phosphate and not complying with the restrictions
          shall not be placed on the Union market. From 1 July 2028 cosmetic products
          containing Triphenyl Phosphate and not complying with the restrictions shall not
          be made available on the Union market.</span>&#8217;</p></td>
        </tr></tbody></table>
      </td>
    </tr>
  </tbody>
</table>
<p class="oj-normal">Annex III is amended as follows:</p>
<table class="oj-table" width="100%">
  <tbody>
    <tr class="oj-table">
      <td><p class="oj-tbl-hdr">Reference number</p></td>
      <td><p class="oj-tbl-hdr">Chemical Name/INN</p></td>
      <td><p class="oj-tbl-hdr">Name of Common Ingredients Glossary</p></td>
      <td><p class="oj-tbl-hdr">CAS number</p></td>
    </tr>
    <tr class="oj-table">
      <td><p class="oj-tbl-txt">&#8216;75</p></td>
      <td><p class="oj-tbl-txt">2-hydroxybenzoic acid phenylmethyl ester (**)</p></td>
      <td><p class="oj-tbl-txt">Benzyl Salicylate</p></td>
      <td><p class="oj-tbl-txt">118-58-1</p></td>
    </tr>
    <tr class="oj-tblnote">
      <td colspan="4">
        <table><tbody><tr>
          <td><p class="oj-normal">&#8216;(**)</p></td>
          <td><p class="oj-normal">From 1 January 2027 cosmetic products containing these
          substances and not complying with the restrictions shall not be placed on the
          Union market.</p></td>
        </tr></tbody></table>
      </td>
    </tr>
  </tbody>
</table>
</body>
"""

# The same regulation, but the footnote marker is on no entry at all. This is the
# shape that would produce a silent all clear if the builder stayed quiet.
ORPHAN_FOOTNOTE = """
<body>
<p id="englishTitle">Commission Regulation (EU) 2099/2 of 1 January 2099 amending
Annex III to Regulation (EC) No 1223/2009</p>
<p class="oj-normal">Annex III is amended as follows:</p>
<table class="oj-table" width="100%">
  <tbody>
    <tr class="oj-table">
      <td><p class="oj-tbl-hdr">Reference number</p></td>
      <td><p class="oj-tbl-hdr">Chemical Name/INN</p></td>
      <td><p class="oj-tbl-hdr">Name of Common Ingredients Glossary</p></td>
      <td><p class="oj-tbl-hdr">CAS number</p></td>
    </tr>
    <tr class="oj-table">
      <td><p class="oj-tbl-txt">&#8216;91</p></td>
      <td><p class="oj-tbl-txt">Some chemical name</p></td>
      <td><p class="oj-tbl-txt">Harmless Glycol</p></td>
      <td><p class="oj-tbl-txt">1-1-1</p></td>
    </tr>
    <tr class="oj-tblnote">
      <td colspan="4">
        <table><tbody><tr>
          <td><p class="oj-normal">&#8216;(*4)</p></td>
          <td><p class="oj-normal">From 1 March 2028 cosmetic products containing these
          substances shall not be placed on the Union market.</p></td>
        </tr></tbody></table>
      </td>
    </tr>
  </tbody>
</table>
</body>
"""

# The "until" form, which states a last lawful day rather than a first restricted one.
UNTIL_FORM = """
<body>
<p id="englishTitle">Commission Regulation (EU) 2099/3 of 1 January 2099 amending
Annex III to Regulation (EC) No 1223/2009</p>
<p class="oj-normal">Annex III is amended as follows:</p>
<table class="oj-table" width="100%">
  <tbody>
    <tr class="oj-table">
      <td><p class="oj-tbl-hdr">Reference number</p></td>
      <td><p class="oj-tbl-hdr">Chemical Name/INN</p></td>
      <td><p class="oj-tbl-hdr">Name of Common Ingredients Glossary</p></td>
      <td><p class="oj-tbl-hdr">CAS number</p></td>
    </tr>
    <tr class="oj-table">
      <td><p class="oj-tbl-txt">&#8216;88</p></td>
      <td><p class="oj-tbl-txt">d-Limonene ( *1 )</p></td>
      <td><p class="oj-tbl-txt">Limonene</p></td>
      <td><p class="oj-tbl-txt">5989-27-5</p></td>
    </tr>
  </tbody>
</table>
<hr class="oj-note"/>
<p class="oj-note"><a id="ntr*1-L_2099EN.01" href="#ntc*1-L_2099EN.01">(<span
class="oj-super">*1</span>)</a>  Cosmetic products containing that substance that do not
comply with the restrictions may be placed on the Union market until 31 July 2026 and made
available on the Union market until 31 July 2028.</p>
</body>
"""
