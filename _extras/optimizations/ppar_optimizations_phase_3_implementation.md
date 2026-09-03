# ppar Optimization Roadmap: Phase 3 Implementation

Status: Implementation complete; 500x scale follow-up assigned to Phase 5  
Implementation date: September 2, 2026

## Outcome

Fixed-frequency analytics now skip consolidation only when a performance stream's
complete ordered sequence of inclusive `(from_date, thru_date)` pairs exactly equals
the aligned reporting-period sequence. Counts, order, start dates, and end dates must
all match.

All frequency-completeness and portfolio/benchmark alignment validation still runs
before the decision. A source with different boundaries, splits, gaps, incomplete
coverage, or additional periods continues through the existing validation or
consolidation path.

The period lists already materialized during alignment are reused locally. No extra
full-history unique-and-sort query or persistent `Analytics` state was added.

## Test-first evidence

Before implementation, exact monthly and quarterly regression cases entered
`_consolidate_subperiods()` and failed the new no-call assertion. The completed tests
cover:

- exact monthly and quarterly boundaries;
- multiple identifiers representing an Asset Class classification in every period;
- a split monthly source that must still consolidate;
- all four attribution views, risk statistics, and audits compared with a forced copy
  of the former consolidation path at the established `1e-12` tolerance; and
- the existing unequal-start, unequal-end, gap, partial-boundary, endpoint,
  mixed-frequency, period-order, conservation, lineage, and regression cases.

The first implementation rematerialized both source-period lists during the shortcut
decision. The existing long-history regression caught this immediately: the
`_period_tuples` count increased from two to four. The final implementation reuses the
two lists already built during alignment, and that established gate passes unchanged.

## Performance results

On the repeatable 121,260-row-per-source exact-monthly workload, the final five-sample
run measured:

```text
[0.133s, 0.126s, 0.120s, 0.124s, 0.127s]; median=0.126s
```

An alternating seven-sample comparison against a deliberately forced copy of the
former consolidation path measured 0.125 seconds versus 0.200 seconds, a 37.4%
reduction. The Phase 0 recorded median was 0.212 seconds.

The standard generic and Axys/APX demonstrations use monthly source data reported
quarterly, so both correctly retain consolidation. Both produced their complete
ordered 11-report bundles. The final generic bundle was byte-for-byte identical to
the preserved Phase 2 bundle.

## Routine validation

The final routine product gate passed with:

- 378 tests and 455 subtests;
- Mypy clean across 40 source files;
- Pyright reporting 0 errors and 0 warnings;
- Pylint error and unused-code checks clean;
- all 12 retained README images current;
- wheel build and Twine metadata validation passing;
- isolated wheel installation and `pip check` passing; and
- both installed setup demonstrations producing their unchanged ordered bundles of
  11 reports.

## 500x scale-gate follow-up

The unchanged 500x gate produced three consecutive full observations during Phase 3:

| Run | Large-site median ratio | Result |
| --- | ---: | --- |
| First | 1.092x | Warning; passed the 1.10x failure boundary |
| Second | 1.108x | Failed the 1.10x boundary |
| Diagnostic rerun | 1.105x | Failed the 1.10x boundary |

The selected 10x and long-history 5x scenarios passed when the full gate reached
them. No threshold, tolerance, sample count, or workflow was changed.

This is not caused by the exact-period shortcut: the standard quarterly large-site
demo does not enter that branch. An alternating five-sample calculation comparison on
the 500x fixture measured a 0.669-second current median and a 0.670-second former-path
median. The absolute scaled end-to-end process also became faster across the runs;
the ratio crossed its narrow boundary because the fixed baseline work became faster
by more than the remaining scaled-only Axys/APX loading work.

Phase 4 proved that repeated in-memory account filtering is material to many-account
usage but is not the dominant cost in this two-requested-account gate. Phase 3 leaves
the established gate intact and records restoring reliable 500x validation as a
remediable Phase 5 requirement. Phase 3 should not be considered fully closed until
the unchanged gate passes or the user explicitly approves an evidence-backed gate
change.
