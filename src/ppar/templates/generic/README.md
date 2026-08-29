# ppar Generic demonstration

Run the tutorial-style demonstration script from any working directory:

```bash
python __PPAR_DEMO_PATH__
```

To run with your own data, replace the demonstration CSV files in `input/`, then edit
`ppar_demo.py` to match their paths, dates, calculation assumptions, classification,
and selected reports. Performance files use the columns `from_date`, `thru_date`,
`identifier`, `weight`, and `return`.
Classification and mapping files are headerless two-column CSV files. Each successful
run atomically replaces the contents of `output/`; a failed run leaves the previous
output intact.
