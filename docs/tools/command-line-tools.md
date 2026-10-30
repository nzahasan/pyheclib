# Command line tools

Installing pyheclib adds these commands on Linux, macOS and Windows. They live in
[`pyheclib/tools`](https://github.com/nzahasan/pyheclib/tree/main/pyheclib/tools) and also run as
`python -m pyheclib.tools.<name>`, for example from a clone with the extension built in place.

## List records: `dss_catalog`

Prints every record in a file with its record type code.

```bash
dss_catalog example.dss
```

Show each time series once instead of once per block:

```bash
dss_catalog example.dss --condensed
```

Show only matching records (use `*` in any part):

```bash
dss_catalog example.dss "/DEMO/*/FLOW/*/*/*/"
```

Record type codes:

| Code | Record type |
|---|---|
| 105 | regular time series |
| 115 | irregular time series |
| 205 | paired data |
| 4xx | gridded data (420, 421 and so on, by grid type) |

## Export to CSV: `dssrec2csv`

Saves one record as a CSV file.

```bash
dssrec2csv example.dss "/DEMO/OUTLET/FLOW//1HOUR/OBS/" flow.csv
```

- Time series: one row per time, with the time and the value.
- Paired data: x in the first column, one column per curve.
- Gridded data: the grid as rows and columns, north at the top.

For a time series, leave the D part empty to export the whole series.

## Example files

The repository also has scripts that create example data:

```bash
python3 examples/make_example_dss.py       # builds examples/example.dss with every record type
python3 examples/make_readme_figures.py    # draws the figures used in these docs
```
