# Statutory Rates: Where They Live and How They Are Kept True

Tax rates change by government notification, often with weeks of notice and sometimes
retroactively. A codebase that hardcodes them will silently compute the wrong tax the day a
rate moves, and nothing will fail. This document is the procedure that prevents that.

It exists because this repository had exactly that failure: the Section 52 TCS rate sat at the
pre-July-2024 value of 1.00% long after Notification 15/2024-Central Tax reduced it to 0.50%,
the value was duplicated across production code and roughly twenty test assertions, and no
test could have detected the drift because every one of them hardcoded the same stale number.

---

## 1. One definition, and it is not in the tests

Every statutory rate has exactly **one** definition, in
`packages/mandateEngine/constants/settlementConstants.py`. Nothing else may hardcode a rate.

The rule that matters most is the one that is easy to get wrong:

> **Tests must derive statutory expectations from the constant, not restate the number.**

A test that reads

```python
assert tcs["tcsCgstPaise"] == (taxable * 50) // 10000     # ✗ hardcoded rate
```

is not testing the rate — it is a second, unmaintained copy of it. When the rate changes, that
test fails for the *right reason but with the wrong remedy*: the tempting fix is to edit the
literal, which quietly turns the test into a rubber stamp for whatever the code now does. Write
instead:

```python
assert tcs["tcsCgstPaise"] == (taxable * tcsCgstBasisPoints) // basisPointsDivisor   # ✓
```

Now a rate change propagates to production and tests together, and the tests keep verifying the
*relationship* (that CGST equals SGST, that components sum to the total) rather than a snapshot.

**Concrete literals are still allowed** where the point of the test is a worked example — a
GSTR-1 invoice showing ₹418.75 CGST on a specific cart. Those are documentation, and they should
be few. Everything generic derives from the constant.

## 2. Every statutory constant carries a citation and a date

Per rule V-05 in `.agents/rules/verification-standards.md`, each constant records:

- the **notification or section** it derives from,
- what it **changed from and to**, with the effective date,
- the date it was **last verified** against the source, and
- **what would trigger** a re-check.

See the TCS block in `settlementConstants.py` for the reference format. The date is the load-
bearing part: it converts "someone probably checked this once" into a fact with an age you can
judge.

## 3. Verify against the primary source

Tax rates are exactly the wrong thing to take from an AI assistant, a Stack Overflow answer, or
a previous commit. Secondary sources are useful for *finding* the notification number; they are
not the citation.

Order of preference:

1. The CBIC notification PDF (`taxinformation.cbic.gov.in`) or the *Gazette of India*.
2. A CBIC or PIB press release naming the notification number.
3. A reputable tax publication — **only** to locate the notification number, which is then
   recorded and confirmed.

When the primary source cannot be retrieved, say so in the annotation rather than implying it
was checked. The current TCS block does this: the CBIC portal was unreachable at the time of
verification, and the comment says so.

## 4. Rates are inputs, not identities

`computeTcsWithholding` takes the rate from a constant and applies it. It does not know that
0.5% is "the" TCS rate. That is what made the correction a four-line change rather than a
rewrite, and it is why the withholding logic in `splitManifestBuilder` needed no edit at all
when the rate moved.

Keep the same separation for any future rate: **the arithmetic is permanent, the rate is
configuration.**

## 5. If rates ever need to vary by date

The current model assumes one rate in force. That is correct for a hackathon submission and
wrong for a production ledger, because an invoice reissued for a past order must use the rate
in force *on the supply date*, not today's.

The natural extension is to make the rate a function of a date rather than a constant — an
effective-dated table (`[(from, to, rateBps), …]`) resolved by the supply date, defaulting to
the current band. That is a genuine change in shape, so it should be done deliberately rather
than bolted on; note it as a known limitation until then. It is recorded in the README's Scope
& Limitations for exactly that reason.

---

## Current statutory values

| Constant | Value | Authority | Last verified |
|---|---|---|---|
| `tcsRateBasisPoints` | 50 (0.50%) | Notification 15/2024-Central Tax, 10 Jul 2024, amending 52/2018-Central Tax | 2026-08-29 |
| `tcsCgstBasisPoints` | 25 (0.25%) | as above, intra-State | 2026-08-29 |
| `tcsSgstBasisPoints` | 25 (0.25%) | as above, intra-State | 2026-08-29 |
| `tcsIgstBasisPoints` | 50 (0.50%) | Notification 02/2024-Integrated Tax, inter-State | 2026-08-29 |
| `validGstRates` | 0/5/12/18/28% | CGST Act Schedules I–VI | not independently re-verified |

> The CBIC PDF portal could not be fetched directly during the 2026-08-29 verification, so the
> notification number and effect were confirmed from multiple secondary sources that quote it.
> **Confirm against the primary PDF before relying on these in production.**
