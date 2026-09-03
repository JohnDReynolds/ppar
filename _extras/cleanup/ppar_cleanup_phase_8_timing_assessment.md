# ppar Cleanup Phase 8 Timing Assessment

Assessment date: September 1, 2026

## Decision status

The user approved the proposed large-site sampling policy on September 1, 2026. It
has been implemented without changing the workload, comparison, thresholds, other
scale scenarios, or release-candidate composition.

## Previous contract

- Prepare the unchanged 1x and 500x Axys/APX workspaces outside the timed region.
- Run the complete baseline demonstration three consecutive times, followed by the
  complete scaled demonstration three consecutive times.
- Compare `median(scaled samples) / median(baseline samples)`.
- Warn above 1.05x and fail above 1.10x.
- Require identical generated HTML between the 1x and 500x workspaces.
- Keep this gate in the release-candidate workflow.

This is an end-to-end report-bundle contract. It includes interpreter startup, source
loading and filtering, analytics calculations, report rendering, and transactional
publication. It does not claim that the isolated calculation is only 1.10x slower.

## Evidence

Before approval, Phase 8 changed diagnostics only: the existing three raw timings
were printed, and `--diagnostics` added observation-only component and paired-run
measurements without changing the release path.

Observed current-policy ratios on the same otherwise idle system ranged from 1.035x
to 1.149x. One run failed at 1.149x; the other measured runs passed or warned, commonly
between 1.06x and 1.10x. Raw samples showed that the first baseline observation was
sometimes substantially colder or slower than the remaining baseline observations.

Component observations were:

- Python startup: approximately 0.014 to 0.018 seconds.
- Calculation-only: approximately 0.218 to 0.228 seconds at 1x and 0.666 to 0.685
  seconds at 500x.
- Full end-to-end medians: approximately 1.30 to 1.43 seconds at 1x and 1.43 to 1.55
  seconds at 500x in the final assessment runs.

The calculation-only diagnostic confirms that the extra 6,050,874 unselected source
rows have measurable processing cost. The standard report rendering and publication
work is common to both workspaces and dominates the end-to-end baseline. Therefore,
the current 1.10x gate protects the incremental effect of a large unselected site on a
complete standard report bundle.

Two diagnostic runs using one warm-up per workspace and five paired baseline/scaled
observations produced median paired ratios of 1.088x and 1.093x. These were much more
consistent than the 1.035x-to-1.149x current-policy range, while remaining close
enough to 1.10x that the threshold continues to be meaningful.

## Approved contract

Keep unchanged:

- the 500x source workload;
- generated-HTML equality;
- the 1.05x warning and 1.10x failure thresholds;
- the selected-workload and long-history gates; and
- release-candidate composition.

The approved change affects only the large-site sample policy:

1. Run one untimed warm-up for the baseline and one for the scaled workspace.
2. Collect five paired observations in baseline-then-scaled order.
3. Calculate each pair's `scaled / baseline` ratio.
4. Apply the existing thresholds to the median of the five paired ratios.
5. Continue printing every raw elapsed time and ratio.

## Tradeoff

The approved policy better controls cold-start and temporal drift without loosening
the performance requirement. It increases the scale gate by roughly eight to ten
seconds because large-site executions rise from six timed runs to two warm-ups plus
ten timed runs. A genuine median ratio above 1.10x still fails.

## Approval record

The user explicitly approved the current contract, proposed contract, evidence, and
runtime tradeoff on September 1, 2026. Behavioral tests protect the warm-up and
pairing order, five-pair sample count, median statistic, and unchanged boundaries.

## Implementation validation

The implemented gate passed two genuine 500x runs:

- The diagnostic run recorded paired ratios of 1.076x, 1.084x, 1.090x, 1.095x, and
  1.119x, with a 1.090x median.
- The complete release-candidate run recorded paired ratios of 1.103x, 1.093x,
  1.070x, 1.102x, and 1.091x, with a 1.093x median.

Both results correctly produced warnings above 1.05x without exceeding the unchanged
1.10x median failure boundary. The complete release-candidate gate passed 337 tests
and 386 subtests, static analysis, documentation and image checks, wheel validation,
installed demonstrations, and all three scale scenarios.
