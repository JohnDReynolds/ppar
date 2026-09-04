# ppar Cleanup Phase 8 Implementation

Status: Complete
Date: September 4, 2026
Baseline revision: `5d5d15682b49784c26b9a6aa53756de53f54f3e9`

## Objective

Make the test boundary match the implementation boundary: `perfattr` owns portable
normalization, alignment, mapping, consolidation, and attribution algorithms; ppar
owns host translation, presentation metadata, public results, risk, vendor loading,
workflows, and release integration.

## Test-ownership map

The checked-out `perfattr` suite passed 240 tests in 1.82 seconds before ppar tests
were removed. The following named tests provide the corresponding portable coverage:

| Former ppar duplication | `perfattr` owner | Retained ppar boundary |
| --- | --- | --- |
| Input copying and row/column ordering | `test_prepare_does_not_mutate_any_caller_owned_input`, `test_prepare_is_deterministic_for_shuffled_inputs_and_mappings` | Polars ownership and public result permutation tests |
| Date coercion, inclusive bounds, empty/reversed windows | `test_normalization_accepts_date_objects_and_removes_times`, `test_date_window_filters_whole_periods_by_inclusive_endpoint`, `test_prepare_rejects_invalid_or_empty_date_windows` | One CSV/Polars date-window equivalence test and Analytics date contracts |
| Required fields, identities, finite values, weight totals, duplicate and overlapping periods | `test_normalization_rejects_invalid_frame_shapes`, `test_normalization_rejects_invalid_identity_date_and_financial_values`, `test_normalization_rejects_ambiguous_period_structures` | Representative Polars/filesystem failures translated to `PparError` |
| Derived contribution, day counts, and prepared schema | `test_returns_only_normalization_derives_contribution_and_days`, `test_preparation_result_has_stable_schemas_order_and_dtypes` | Public output schemas, regression results, and ppar's rule that generic contribution input is ignored |
| CSV identity and numeric parsing rules | `test_performance_reader_preserves_master_file_identities_and_provenance`, `test_performance_reader_rejects_invalid_csv_contracts` | CSV/Polars equivalence and numeric-looking identifier tests |
| Pair alignment and reporting-frequency edge cases | `test_native_alignment_keeps_exact_common_periods_only`, `test_fixed_alignment_accepts_different_partitions_of_equal_coverage`, and the fixed-alignment rejection matrix | Representative frequency integration and public Analytics alignment tests |
| Mapping normalization, collisions, zero-weight groups, and conservation | `test_mapping_normalization_trims_deduplicates_and_preserves_leading_zeroes`, `test_mapping_rollup_combines_collisions_and_uses_identity_fallback`, `test_mapping_uses_defined_zero_or_null_for_zero_net_weight`, `test_mapped_consolidation_reconciliation_covers_every_applicable_check` | Public mapping integration, classification presentation, zero-net report rendering, and adapter invariants |
| Attribution calculation and multi-period linking | `test_calculate_attribution_matches_independent_period_detail`, `test_multi_period_linking_matches_independent_detail`, `test_multi_period_horizon_and_cumulative_contract` | ppar regression fixtures, metamorphic invariants, all public views, and automatic audits |

## Changes

- Removed the direct source-loading `Performance` constructor and its duplicate
  single-source adapter function. The internal container can now be populated only by
  the trusted aligned result returned through `Analytics` preparation.
- Renamed `test_performance_normalization.py` to `test_performance_sources.py` and
  reduced it to seven tests of behavior ppar still owns: source-container equivalence,
  caller ownership, textual identity translation, display-name selection, generic
  contribution semantics, and error translation.
- Replaced direct `Performance` and `Classification` construction in retained tests
  with public `Analytics` workflows. Removed tests of direct `Attribution` and
  `RiskStatistics` construction with internal performance containers.
- Removed three standalone preparation arithmetic tests, a duplicate date-filtering
  test, and other validation-matrix cases already covered by the portable suite.
- Retained ppar's independent financial invariants, adapter tests, regression results,
  risk-array tests, output contracts, Axys/APX tests, demonstrations, and scale gates.
- Removed the now-unused source type aliases from `utilities.py`.

The complete ppar suite changed from 367 tests and 517 subtests after Phase 7 to 330
tests and 501 subtests: a net reduction of 37 tests and 16 subtests.

## Validation

- Checked-out `perfattr` suite: 240 tests passed in 1.82 seconds.
- Focused Phase 8 ppar suite: 105 tests and 144 subtests passed in 14.83 seconds.
- Complete ppar suite: 330 tests and 501 subtests passed in 28.94 seconds.
- Mypy: clean across 38 source and script files.
- Pyright: 0 errors and 0 warnings.
- Pylint errors-only and focused unused checks: clean.
- README image regeneration and provenance validation: passed.
- Universal wheel build, Twine validation, isolated installation, dependency check,
  CLI version, generic setup, and Axys/APX setup: passed.
- Both installed demonstrations produced the ordered 11-report bundle.
- The unchanged 500x scale gate passed: the 6,063,000-row large-site workload
  completed at 0.995x baseline time, the selected workload at 2.076x, and the
  thresholded five-times-long-history workload at 1.100x versus warning and failure
  ratios of 1.58x and 1.65x.
- `git diff --check`: passed.
