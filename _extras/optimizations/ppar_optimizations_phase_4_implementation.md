# ppar Optimization Roadmap: Phase 4 Implementation

Status: Implementation complete; large-site scale-gate follow-up assigned to Phase 5  
Implementation date: September 2, 2026

## Outcome

Bulk Axys/APX loading now partitions each normalized requested source frame once by
exact portfolio code, instead of filtering both complete selected frames separately
for every account. Partitioning preserves source row order and exact string identity,
including leading zeroes.

Requested portfolios are still reconciled and returned in first-request order.
Repeated requests remain deduplicated, missing portfolio errors retain their existing
facade context, and missing security rows reach the same reconciliation validation as
an empty per-account filter did previously.

A one-account request bypasses partitioning because both loaded frames are already
restricted to that account. For bulk requests, the parent portfolio frame is released
before security loading, and account partitions are popped as reconciliation proceeds.
The source loader continues to restrict its frames to requested codes, so no
unrequested account partitions are retained.

## Test-first evidence

Before implementation, three new regressions failed because no partition helper
existed. The completed coverage verifies:

- one account avoids unnecessary partitioning;
- the normal portfolio/benchmark pair partitions each source exactly once;
- repeated requests deduplicate while preserving first-request order;
- partitions match the former exact per-account filters row-for-row;
- interleaved `001`, `1`, and `A01` rows retain distinct identities and source order;
- the existing absent-code error and date context remain unchanged; and
- all existing reconciliation, security-identity, source-format, and Axys pipeline
  behavior remains intact.

The focused Axys/APX selection passed with 92 tests and 281 subtests. The final full
suite passed with 382 tests and 460 subtests.

## Performance and memory

The repeatable 40-account, 242,520-security-row benchmark measured 0.431 seconds
before implementation and 0.369 seconds afterward, a 14.4% reduction. A seven-sample
alternating comparison in the same process measured:

```text
partitioned: 0.388-second median
former repeated filters: 0.434-second median
improvement: 10.5%
```

The alternating comparison also required exact account keys, display names, and
reconciled performance frames before accepting the timing result.

Fresh-process `ru_maxrss` measurements on the same fixture showed an approximately
120.6 MB increase for the former implementation and 128.3 MB for partitioning. The
approximately 7.5 MB incremental peak is the cost of briefly materializing all
requested partitions together. Releasing the parent frame before loading the larger
security source and popping partitions account-by-account bounds their lifetime. The
tradeoff is appropriate for the expected bulk-account usage and measured 10–14%
elapsed-time reduction.

The ordinary Axys/APX report bundle showed no regression: its five-sample median was
1.120 seconds before and 1.080 seconds after, while analytics-and-attribution
construction measured 0.107 seconds before and 0.101 seconds after. These small
differences are within normal local timing variation. Its final 11-report output was
byte-for-byte identical to the preserved Phase 3 bundle.

## Routine validation

The complete routine product gate passed with:

- 382 tests and 460 subtests;
- Mypy clean across 40 source files;
- Pyright reporting 0 errors and 0 warnings;
- Pylint error and unused-code checks clean;
- all 12 retained README images current;
- wheel build and Twine metadata validation passing;
- isolated wheel installation and `pip check` passing; and
- both installed setup demonstrations producing their unchanged ordered bundles of
  11 reports.

The selected-workload 10x scale scenario passed at 1.965x against its unchanged 2.20x
failure boundary. The long-history 5x scenario passed at 1.453x against its unchanged
1.65x failure boundary.

## Large-site 500x follow-up

The unchanged large-site gate failed after Phase 4 at a 1.108x median against its
1.10x failure boundary. No threshold, workload, sample count, tolerance, or
equivalence check was changed.

Profiling explains why the approved optimization cannot resolve this scenario. The
500x demo requests only the original portfolio and benchmark. The lazy CSV query
therefore selects only those two accounts before `AxysPortfolioLoader` receives the
frames; one-time partitioning has little scaled-only work to remove. The complete
analytics builder measured 0.260 seconds, of which portfolio loading used 0.169
seconds and the two source collections used 0.131 seconds. The remaining cost is
scanning the large CSV to find two requested accounts, not repeatedly filtering many
loaded accounts.

This corrects the Phase 3 hypothesis without hiding the issue. Phase 5 now records the
gate as a remediable TODO. Because changing an established release gate requires the
user's explicit approval, Phase 4 makes no unauthorized threshold or workload change.
