# Axys/APX Common-Core Export Reference

This note sketches a PPAR-normalized Axys/APX extract shape for analytics and
performance auditing. It is an extraction-planning aid, not an official
Axys/APX schema, executable export recipe, or generic implementation contract.

See [Performance Comparison Design Notes](../audit/performance_comparison_design.md)
for the stable comparison model and the
[Audit MVP plan](../audit/mvp_plan.md) for current implementation scope.

Axys/APX installations vary by site. The current evidence does not establish a
universal IMEX object catalog, performance object names, field mnemonics,
profile names, command syntax, or REP layouts. In particular, `portperf.csv`
and `secperf.csv` are PPAR-normalized filenames, not verified native object or
profile names.

## Extraction Planning Worksheet

Use this table when speaking with an Axys/APX administrator or report writer.
Do not turn it into an IMEX command script until the local installation proves
the exact object/profile names, fields, parameters, and date/currency basis.

| PPAR dataset | Practical first source | Local questions to resolve |
| --- | --- | --- |
| `portperf.csv` | REP performance report preferred. | Which report reproduces the reported portfolio return? Is the value stored or report-calculated? What are its date, currency, and gross/net bases? |
| `secperf.csv` | REP security-performance or attribution report preferred. | Does it provide security return and portfolio/security keys? Do weights and contributions foot to the portfolio report? |
| `holdings.csv` | IMEX positions/holdings export or REP appraisal report. | Are values local or portfolio-base? Is accrued income included in market value or stated separately? Can both beginning and ending dates be produced? |
| `transactions.csv` | IMEX transaction export first; REP/custom report fallback. | Are transaction code, amount, security, and economic date present? For ambiguous codes, are source/destination and special-security fields available? |
| `splits.csv` | `split.inf` or an equivalent local split-factor export. | Is the factor a multiplier or inverse? Which date is represented? |
| `secmast.csv` | IMEX security-information export or security-master report. | Which identifier is stable, and which classification/currency fields are current rather than historical? |

## Field and Contract Ownership

This planning aid does not maintain a second field dictionary. Use:

- [Chapter 15 — Data Dictionary](reference/Chapter_15_Data_Dictionary.md) for
  observed Axys/APX fields, artifacts, aliases, and confidence;
- [generated extract requirements](contracts/demo_extract_availability.md) for
  PPAR dataset requirements and likely IMEX/REP source paths;
- [transaction semantics YAML](contracts/transaction_semantics_matrix.yaml) for
  executable PPAR transaction treatment; and
- the local comparison YAML column mappings for the accepted site-specific
  source labels.

Keep this file limited to the administrator/report-writer discovery worksheet.
Add candidate labels to the data dictionary, not here.
