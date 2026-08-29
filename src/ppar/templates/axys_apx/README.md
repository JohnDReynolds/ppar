# ppar Axys/APX demonstration

Run the tutorial-style demonstration script from any working directory:

```bash
python __PPAR_DEMO_PATH__
```

To run with your own data, replace the demonstration CSV files in `input/` with your
Axys/APX exports, then edit `ppar_demo.py` to match their paths, columns, portfolio,
benchmark, dates, classification, calculation assumptions, and selected reports. Each
successful run atomically replaces the contents of `output/`; a failed run leaves the
previous output intact.
