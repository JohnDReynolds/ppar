# ppar Generic workspace

This vendor-neutral workspace is ready to run:

```bash
ppar run .
```

Replace the demonstration CSV files in `input/`, then edit `ppar.yaml` to match their
paths and reporting settings. Performance files use the narrow columns `from_date`,
`thru_date`, `identifier`, `weight`, and `return`. Classification and mapping files
are headerless two-column CSV files. Output is always replaced atomically in
`output/`.
