# ppar Correctness Roadmap: Phase 11 Implementation

Status: Complete  
Implementation date: September 1, 2026

## Outcome

Phase 11 makes attribution heatmaps preserve the mathematical distinction established
by Phase 4. A zero-net mapped group with defined nonzero portfolio contribution now
remains visible. A mathematically undefined portfolio or active return remains masked
and unannotated instead of being displayed as zero.

An absent date/classification pivot cell remains distinct from an explicit null source
value. Absence retains the attribution model's defined zero, while explicit null
means the requested metric is unavailable. Ordinary missing portfolio holdings remain
omitted from portfolio-only heatmaps.

## Test-first evidence

Five focused test methods were added before production changes. Their parameterized
cases produced six failures against the Phase 10 implementation:

- the real mapped zero-net `Hedge` group was missing from the portfolio-contribution
  heatmap despite retaining contribution `0.05` in the tabular attribution result;
- the same group was missing from the portfolio-return heatmap;
- its null active return was converted to zero;
- an explicit null source value and an absent pivot cell both became zero;
- the ordinary heatmap annotated an undefined cell as `0.0000`; and
- the large raster heatmap also annotated the undefined cell as zero.

The mapped tests construct the public `Analytics` and `Attribution` workflow from
offsetting long and short constituents rather than supplying only a hand-built chart
frame. Additional cases cover a real zero metric, an ordinary missing portfolio
holding, an absent classification/date pair, default metric sorting, duplicate
display names, and the existing stable-identity behavior.

## Implementation

### Measure-aware portfolio filtering

Portfolio-only heatmaps no longer discard every zero-weight row. A row is omitted
only when portfolio weight is zero and its selected metric is a defined zero, which
is the ordinary missing-holding representation. A nonzero selected metric or an
explicitly null metric remains visible even when mapped constituent weights net to
zero.

This keeps the filter tied to the selected measure. In particular, contribution
availability is not inferred from net weight.

### Null-preserving pivot preparation

Before pivoting, an explicit null calculated metric is represented internally as
`NaN`. Polars still represents a genuinely absent pivot cell as null, so the existing
pivot fill converts only absence to zero. Sorting uses defined values and treats the
masked cells as neutral solely for the private row-order key; it does not change the
rendered data.

Seaborn masks the resulting `NaN` cells in the ordinary heatmap path and creates no
text annotation for them. The large raster path reads the same mesh mask and skips
those cells while continuing to annotate every defined value, including a real zero.

### Documentation

The heatmap API docstrings and methodology now explain the distinction among
zero-net defined contribution, undefined returns, absent cells, and ordinary missing
portfolio holdings.

## Validation

The focused chart suite passed with 11 tests. The combined chart, mapped
classification, calculation-invariant, and public-output selection passed with 58
tests.

`./.venv/bin/python scripts/check_project.py` passed with:

- 358 tests and 439 subtests;
- Mypy clean across 38 source files;
- Pyright reporting 0 errors and 0 warnings;
- Pylint error and unused-code checks clean;
- all documentation-image and provenance checks current;
- wheel build, Twine validation, isolated installation, and `pip check` passing; and
- both installed setup demonstrations producing their unchanged ordered bundles of
  11 reports.

The documentation gallery was regenerated for the corrected chart-source fingerprint.
All 12 retained images remain in the documented inventory; no image or report was
added or removed.

The unchanged 500x reporting safety gate passed:

- large-site 500x median paired ratio: 1.095x, above the unchanged 1.05x warning
  boundary and below the unchanged 1.10x failure boundary;
- selected-workload 10x ratio: 1.948x, below the unchanged 2.10x warning and 2.20x
  failure boundaries; and
- genuine long-history 5x ratio: 1.275x, below the unchanged 1.58x warning and 1.65x
  failure boundaries.

No PNG filename, public tabular schema, report inventory, financial formula,
established tolerance, test threshold, or performance gate was changed or relaxed.
