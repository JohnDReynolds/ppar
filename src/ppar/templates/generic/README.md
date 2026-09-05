# ppar vendor-neutral demonstration

Run the tutorial-style demonstration script from any working directory:

```bash
python __PPAR_DEMO_PATH__
```

To run with your own data, replace the demonstration CSV files in `input/`, then edit
`ppar_demo.py` to match their paths, dates, calculation assumptions, classification,
and selected reports. Reports are written to `output/`.

## Performance files

The portfolio and benchmark CSV files in `input/performance/` contain one row per
identifier and input period. They use these columns:

| Column | Meaning |
| --- | --- |
| `from_date` | First date of the input period, in `YYYY-MM-DD` form. |
| `thru_date` | Last date of the input period, in `YYYY-MM-DD` form. |
| `identifier` | Security or other holding identifier. |
| `weight` | Holding weight as a decimal; `0.25` means 25%. |
| `return` | Holding return as a decimal; `0.05` means 5%. |
| `name` | Optional display name for the identifier. |

Within each period, rows must be unique by `identifier`, weights must sum to 1.0,
and input periods must not overlap. ppar calculates the total return as the sum of
`weight * return`. The portfolio and benchmark must have compatible histories with
at least one common selected period. `FROM_DATE` and `THRU_DATE` set the inclusive
reporting range. An input period is included when its `thru_date` falls within that
range.

## Classifications and mappings

Files in `input/classifications/` and `input/mappings/` are headerless CSV files.
Classification files and ordinary static mappings contain exactly two columns:

| File | First column | Second column |
| --- | --- | --- |
| `Security.csv` | Performance identifier | Display name |
| Classification file | Classification identifier | Display name |
| Mapping file | Performance identifier | Classification identifier |

A mapping file may instead contain four columns in this order:

```text
from_date, thru_date, performance identifier, classification identifier
```

Use either two columns for every row or four columns for every row. Dates include both
endpoints. Each input period must fit within one dated assignment; ppar does not divide
a period when its classification changes.

Each performance identifier should be named in `Security.csv` and mapped to an
identifier in the selected classification file.

Performance identifiers and both mapping columns are treated as textual identities.
Leading zeroes and meaningful internal spaces are preserved. Surrounding whitespace
is removed, and values that are then blank are rejected.

Common setup errors include misspelled headings, percentages entered as whole
numbers, weights that do not sum to 1.0, duplicate or overlapping periods, and
identifiers that differ between files.
