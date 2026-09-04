# Audit Todo — what is still open

One finding is open, and it is a behavioural claim rather than a broken mechanism: the mechanism
it asked for shipped on 2026-09-04 and has not yet been measured with live agents. The 52 closed
findings, with the evidence that proved each and the note recording what closed it, are in
[AUDIT_ARCHIVE.md](AUDIT_ARCHIVE.md).

| # | Open finding | Ground | What remains |
|---:|---|---|---|
| 48 | Agents do not volunteer an upcoming sale unless asked | `mcpServer`, measured by `smartwait/` | The mechanism shipped 2026-09-04: `search_catalog` now carries `next_promotion` on every hit, including the ones the agent rejects, and the manifest requires it to be stated. Unmeasured -- re-run `smartwait/runSmartWait.sh` on both models and report the rate against the 0-of-7 baseline. |

---

### [ ] 48. Agents do not volunteer an upcoming sale, though they reason about one when asked

- Evidence, measured across all 44 runs rather than read off two (`scorerun.py` now emits
  `advertised_upcoming_sale` and `mentions_upcoming_sale`). Five runs were told a sale was
  coming. Two mentioned it, and both are B-09 -- the one scenario that *asks*:

      B08_flash   advertised ₹6,000   mentioned: no
      B09_flash   advertised ₹6,000 + ₹5,200   mentioned: yes
      B09_pro     advertised ₹6,000 + ₹5,200   mentioned: yes
      B10_flash   advertised ₹6,000   mentioned: no
      B10_pro     advertised ₹6,000 + ₹5,200   mentioned: no

  Asked, 2 of 2 mention it. Unasked, 0 of 3. That is the finding, and it is narrower than what
  was written here first.
- **Correction.** The original line claimed both B-08 models quoted `SKU-TEST-MON-SALE` and
  received the promotion. `B08_pro` did neither: one `get_live_sku_quote` call, on
  `SKU-MONITOR-301`, and `upcoming_promotions` appears zero times in its transcript. It is not
  evidence of silence about a sale it was never shown.
- The strongest case is B-10, not B-08, and it is unconfounded: B-10 asks the agent to "tell me
  exactly which discounts I got and how much I saved in total", and both models answered that
  question while holding a ₹6,000 sale notice they did not pass on.

**Why it matters:** Smart Wait only reads as a feature if the agent raises it unprompted.

**Partial fix:** `get_live_sku_quote`'s description now requires a non-empty
`upcoming_promotions` to be stated in the final answer, not merely considered. The same
description had also gone stale — it told agents a running sale appears in no field, which was
true only because of item 46.

**Still open:** re-measure. The B-08 confound is worse than
`findings/F02-smart-wait-not-volunteered.md` records. The two monitors are not merely similar,
they are interchangeable: both 27-inch 4K 99%-sRGB USB-C-90W panels at `baseUnitPricePaise`
2400000 from origin pincode 560001, differing only in category and in the promoted one carrying
"height-adjustable stand" and "home office" in its description. "Buy me a 27-inch monitor" was a
coin flip.

**Re-measured 2026-09-04, and the description approach is now measured as insufficient.** The
live description tells an agent, in the strongest terms a description allows: "If
upcoming_promotions is non-empty you MUST tell the buyer the sale exists, what it would save and
when it starts ... Say it in your final answer, not only in your reasoning."

Four fresh runs -- both models, the original prompt as a byte-identical control and a variant
naming a feature only the promoted SKU has -- were each handed a ₹6,000 sale opening ninety
minutes out. **None mentioned it.** With the three unasked runs already on record that is 0 of 7,
against 2 of 2 on B-09, the one scenario that asks.

**Partial fix, placed where the evidence says agents actually read.** `execute_settlement` now
adds a `buyerNotice` to the receipt when the SKU just bought has a sale opening soon
(`settlementExecutor.ts:_upcomingSaleNotice`). The receipt is the part of a settlement agents
relay verbatim -- all four runs printed the payment id, the invoice number and the tax split.
Verified live: buying `SKU-TEST-MON-SALE` returns "This purchase completed shortly before a
merchant sale ... would have saved ₹6000.00 per unit."

**Still open, and narrower than before.** The notice only covers the case where the agent buys
the promoted SKU. The behaviour actually observed is different and harder: the agent is shown a
sale on SKU A, buys SKU B, and never mentions A. In a second batch on the fixed stack, 1 of 4
unasked runs volunteered it -- `B08a_pro` named the campaign, the ₹18,000 expected price and the
₹6,000 saving unprompted. One run is not a rate. Reaching the other three needs the notice to
travel with the *search result* the agent rejected, not only with the receipt for what it bought.

The re-test kit that produced these numbers:

- `smartwait/genPrompts.py` writes two variants -- **B08a**, the original prompt byte-identical as
  a control, and **B08b**, the same prompt plus "with a height-adjustable stand for my home
  office", a clause only the promoted SKU's description answers. No catalog data is edited.
- `smartwait/runSmartWait.sh` runs both on both models from an isolated cwd, and refuses to start
  if `SKU-TEST-MON-SALE` has no upcoming promotion -- the window ages out silently and a run
  against an open window measures nothing.
- `scripts/reauthorSaleWindow.py` moves the window; it is now in the repo rather than a temp
  directory, alongside `scripts/demoNegotiationPolicy.py`.

**2026-09-04: the notice now travels with the search result, which is what the paragraph above
asked for.** `search_catalog` attaches `next_promotion` to every ranked hit whose merchant has a
sale scheduled -- the same field, from the same evaluator, that `browse_catalog` already returned,
now shared by both through `catalog/promotionResolver.ts` so the two discovery surfaces cannot
become two opinions about one campaign. A hit ranked below the one the agent takes carries it
too; that is the whole point, and `searchCatalogSaleNotice.test.ts` pins it with the promoted SKU
deliberately ranked second. A hit this process's catalog does not hold passes through untouched
rather than being dropped, because search ranks a wider index than the in-process store carries.
The manifest description was rewritten in the same change: an agent is now told it MUST state a
sale carried by ANY result, including one it did not buy, and including when the buyer did not ask
about discounts.

**Still open, and now narrower still: this is unmeasured.** Seven unit tests prove the field is
there and correct; not one of them proves an agent says it out loud, and that is the only thing
this finding has ever been about. The description approach has already been measured insufficient
once, at 0 of 7. Closing this item requires re-running `smartwait/runSmartWait.sh` on both models
with the new field live and reporting the rate -- and it should be closed only if the rate moves.

---

## Standing debt

Not defects, so not numbered findings -- but the three places a reader should expect trouble.

- **The unswept ground.** `mcpServer`, `telemetryDashboard/src`, most of `scripts/` and most of
  `tests/` have never had a systematic pass; the Scope table in the archive records how deeply each
  package was actually read. Five findings (32, 44, 46, 47, 51) have since come out of `mcpServer`
  by other routes, which is the argument for sweeping it rather than against.
- **`twoPhaseCommitSaga.py` is 365 lines** with a 76-line `compensateTransfers` and a 44-line
  `verifyAndCapturePhase`. It violated the 300-line/40-line convention before the remediation pass
  and is not in the `TestMilestone2AstAndLayout` allowlist that would enforce it; the category
  wiring added 5 lines to `verifyAndCapturePhase` rather than reducing the debt.
- **`gstrInvoiceEngine.py` (57.4%) and `arithmeticEnclave.py` (72.5%)** hold 89 of the 104
  surviving mutants reported by `python scripts/mutationScore.py`, and both are financial code.

---

## How this file is maintained

- **A new finding takes the next unused number** -- the highest in the archive plus one -- and is
  appended here as `### [ ] N. <what is wrong>` with the `file:line` that proves it. Numbers are
  never reused and never renumbered: code comments cite them.
- **Closing an item means moving it**, not deleting it. Flip `[ ]` to `[x]`, state what fixed it
  naming the file and the regression test, then move the whole item into `AUDIT_ARCHIVE.md` and
  drop its row from the table above. A fix without a test that was *observed to fail* is not
  closed.
- **The table is the file.** If it disagrees with the sections below it, the file is broken.
- **Correct in place, with a date.** When what is known about an open finding changes, rewrite its
  body and say when it was re-measured -- item 48 is the worked example.
