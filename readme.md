<img src="https://raw.githubusercontent.com/nzahasan/pyheclib/main/assets/pyheclib_banner.png" alt="pyheclib">

# pyheclib
[![Python: Version](https://img.shields.io/badge/python-3.8|3.9|3.10|3.11|3.12|3.13|3.14-blue.svg)](#)
[![Action: Test](https://github.com/nzahasan/pyheclib/actions/workflows/test.yml/badge.svg)](https://github.com/nzahasan/pyheclib/actions/workflows/test.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Docs](https://img.shields.io/badge/docs-nzahasan.github.io%2Fpyheclib-blue.svg)](https://nzahasan.github.io/pyheclib)

**Documentation: [nzahasan.github.io/pyheclib](https://nzahasan.github.io/pyheclib)**

Read and write [HEC-DSS](https://www.hec.usace.army.mil/software/hec-dss/) files from Python.

HEC-DSS is the database format used by HEC-HMS, HEC-RAS and other tools from the
[US Army Corps of Engineers' Hydrologic Engineering Center](https://www.hec.usace.army.mil/).
pyheclib works with **DSS version 7** files. It bundles the official HEC-DSS C library for
Linux (x86_64), macOS (Apple Silicon, macOS 14+) and Windows (x64).

> DSS version 6 files are not supported. Convert them to version 7 with
> [HEC-DSSVue](https://www.hec.usace.army.mil/software/hec-dssvue/) first.

## Install

```bash
pip install pyheclib
```

Requires Python 3.8 or newer. Depends on `numpy` and `pandas`.

## Quick start

Every record is a Python object that holds its pathname, data and metadata.
Create a record, `write` it to a file, and `read` gives you the same kind of object back.

| Record        | Use it for                  | Data                                               | Convert                                              |
|---------------|-----------------------------|----------------------------------------------------|------------------------------------------------------|
| `RegularTs`   | fixed-interval time series  | `values` (numpy), `start` time                     | `to_series()` / `RegularTs.from_series()` (pandas)   |
| `IrregularTs` | time series with any timing | `times`, `values` (numpy)                          | `to_series()` / `IrregularTs.from_series()` (pandas) |
| `PairedData`  | curves, e.g. rating tables  | `x` (numpy 1d), `y` (numpy 2d `[curves, points]`)  | `to_dataframe()` / `PairedData.from_dataframe()`     |
| `GriddedData` | rasters, e.g. radar or DEM  | `data` (numpy 2d `float32`, north-up, `NaN` = no data) | it's already a numpy array                       |

### Open a file

```python
import numpy as np
import pandas as pd
import pyheclib as phl

dss_file = phl.open("example.dss")     # opens the file, or creates it
```

You can also use it as a context manager: `with phl.open("example.dss") as dss_file: ...`

### Regular time series

The interval comes from the E part of the pathname, e.g. `1HOUR`, `15MINUTE`, `1DAY`, `1MONTH`.
Missing values are `NaN`.

```python
# from a list of values and the time of the first value
precip = phl.RegularTs("/DEMO/GAGE/PRECIP//1DAY/OBS/", values=[0.0, 12.5, 48.0, 3.1, 0.0],
                       start="2020-01-14", unit="MM", type="PER-CUM")
dss_file.write(precip)

# from a pandas Series
hours = pd.date_range("2020-01-14 01:00", periods=96, freq="h")
flow = pd.Series(40 + 50*np.exp(-((np.arange(96) - 40) / 12.0)**2), index=hours)
flow.iloc[70:76] = np.nan
dss_file.write(phl.RegularTs.from_series("/DEMO/OUTLET/FLOW//1HOUR/OBS/", flow, unit="CFS", type="INST-VAL"))

# read the whole series (leave the D part empty)
rts = dss_file.read("/DEMO/OUTLET/FLOW//1HOUR/OBS/")          # -> RegularTs
print(rts.unit, rts.type, rts.interval, rts.start)            # CFS INST-VAL 1HOUR 2020-01-14 01:00:00
series = rts.to_series()                                      # pandas Series indexed by time

# or just a time window
window = dss_file.read("/DEMO/OUTLET/FLOW//1HOUR/OBS/", start="2020-01-15 12:00", end="2020-01-15 18:00")
```

![Regular time series](https://raw.githubusercontent.com/nzahasan/pyheclib/main/assets/readme/regular_ts.png)

### Irregular time series

Use an E part that starts with `IR-` (or `~`), e.g. `IR-MONTH`. Times are stored to the second.
Writing replaces any stored values inside the time span of the new record.

```python
stage = phl.IrregularTs("/DEMO/OUTLET/STAGE//IR-MONTH/OBS/",
                        times=pd.to_datetime(["2020-01-14 08:13:00", "2020-01-15 07:30:15", "2020-01-16 16:45:00"]),
                        values=[3.1, 4.6, 3.4], unit="FT", type="INST-VAL")
dss_file.write(stage)

its = dss_file.read("/DEMO/OUTLET/STAGE//IR-MONTH/OBS/")      # -> IrregularTs
its.times, its.values, its.to_series()
```

![Irregular time series](https://raw.githubusercontent.com/nzahasan/pyheclib/main/assets/readme/irregular_ts.png)

### Paired data

All curves share one `x` array. `y` has one row per curve. `labels` (optional) names the curves.

```python
h = np.linspace(0, 12, 49)
rating = phl.PairedData("/DEMO/OUTLET/STAGE-FLOW///RATING/", x=h,
                        y=np.vstack([5.2*h**1.80, 5.6*h**1.75, 6.1*h**1.70]),
                        x_unit="FT", y_unit="CFS", labels=["2018", "2019", "2020"])
dss_file.write(rating)

pd_rec = dss_file.read("/DEMO/OUTLET/STAGE-FLOW///RATING/")   # -> PairedData
pd_rec.n_curves, pd_rec.labels
df = pd_rec.to_dataframe()                                    # index: x, one column per curve
```

![Paired data](https://raw.githubusercontent.com/nzahasan/pyheclib/main/assets/readme/paired_data.png)

### Gridded data

`data` is a 2d numpy array, stored as `float32`:

- the first row is the northern-most row (north-up)
- `NaN` means no data
- `xll`, `yll` is the lower-left corner of the grid, in the grid's coordinate system
- the D and E parts are the start and end time; leave both empty for grids that don't change over time (e.g. a DEM)

```python
yy, xx = np.mgrid[0:90, 0:140]
field = (38*np.exp(-(((xx - 85)/22.0)**2 + ((yy - 40)/14.0)**2))).astype(np.float32)
field[((xx - 70)/68.0)**2 + ((yy - 45)/44.0)**2 > 1] = np.nan       # outside the basin

grid = phl.GriddedData("/SHG/DEMO/PRECIP/15JAN2020:0000/15JAN2020:0600/RADAR/", field,
                       cell_size=2000.0, xll=-180000.0, yll=1320000.0, unit="MM", type="PER-CUM",
                       grid_type="ALBERS", srs_name="SHG", time_zone="UTC")
dss_file.write(grid)

g = dss_file.read("/SHG/DEMO/PRECIP/15JAN2020:0000/15JAN2020:0600/RADAR/")   # -> GriddedData
g.data.shape, g.cell_size, g.extent, g.lower_left_cell, g.start_time
```

![Gridded data](https://raw.githubusercontent.com/nzahasan/pyheclib/main/assets/readme/gridded_data.png)

### Pathnames and the catalog

A DSS pathname has six parts: `/A/B/C/D/E/F/`. `DssPath` lets you work with the parts.
Anywhere a pathname is expected, you can pass a `DssPath` or a plain string.

```python
path = phl.DssPath("/DEMO/OUTLET/FLOW/01JAN2020/1HOUR/OBS/")
path.C                        # 'FLOW'
path.replace(F="SIM")         # DssPath('/DEMO/OUTLET/FLOW/01JAN2020/1HOUR/SIM/')
path.without_date()           # DssPath('/DEMO/OUTLET/FLOW//1HOUR/OBS/')
phl.DssPath.from_parts(A="DEMO", C="STAGE-FLOW", F="RATING")

dss_file.catalog()                      # every record (a long time series is split into blocks)
dss_file.catalog(condensed=True)        # one path per time series, D part = date range,
                                        # e.g. 01JAN2020-01MAR2020
dss_file.catalog("/DEMO/*/FLOW/*/*/*/", condensed=True, with_types=True)
dss_file.read(dss_file.catalog(condensed=True)[0])   # a condensed path reads the whole series
```

### Find and delete

Use `*` at the start or end of any pathname part as a wildcard.
`delete` returns the paths it removed.

```python
dss_file.find("/DEMO/*/*/*/*/OBS/")                    # every OBS record in DEMO
dss_file.find("/*/*/STAGE*/*/*/*/")                    # STAGE and STAGE-FLOW records

dss_file.delete("/DEMO/OUTLET/STAGE-FLOW///RATING/")   # one record
dss_file.delete("/DEMO/OUTLET/FLOW//1HOUR/OBS/")       # a whole time series (all blocks)
dss_file.delete("/SHG/*/*/*/*/*/")                     # everything with A part SHG
dss_file.close()
```

## Limitations

- Quality flags are read when present, but not written.
- Gridded data is always stored as `float32`.
- Only DSS version 7 files.

## Quick reference

A compact summary of the API, useful for scripts and AI coding agents.

```text
import pyheclib as phl

phl.open(filename) -> DssFile                 # creates the file if missing; context manager
DssFile.write(record)                         # replaces existing data at that path
DssFile.read(path, start=None, end=None)      # -> RegularTs | IrregularTs | PairedData | GriddedData
DssFile.catalog(path_filter="", condensed=False, with_types=False) -> list[DssPath]
DssFile.find(path) -> list[DssPath]           # '*' wildcard at start/end of a part
DssFile.delete(path) -> list[DssPath]         # raises KeyError if nothing matches
DssFile.record_type(path) -> int              # 105 regular ts, 115 irregular ts, 205 paired, 4xx grid
DssFile.close()

RegularTs(path, values, start, unit="", type="INST-VAL", time_zone="")
    .interval  .times  .to_series()  RegularTs.from_series(path, series, unit, type)
IrregularTs(path, times, values, unit="", type="INST-VAL", time_zone="")
    .to_series()  IrregularTs.from_series(path, series, unit, type)
PairedData(path, x, y, x_unit="", y_unit="", labels=[])
    .n_curves  .to_dataframe()  PairedData.from_dataframe(path, df, x_unit, y_unit)
GriddedData(path, data, cell_size, xll, yll, unit="", type="INST-VAL",
            grid_type="SPECIFIED", srs_wkt="", srs_name="", origin=(0, 0), time_zone="")
    .shape  .extent  .lower_left_cell  .start_time  .end_time

DssPath(path) | DssPath.from_parts(A=, B=, C=, D=, E=, F=)
    .A .. .F  .parts()  .replace(**parts)  .without_date()
```

Rules worth knowing:

- `type` is one of `INST-VAL`, `INST-CUM`, `PER-AVER`, `PER-CUM`, `FREQ`.
- `grid_type` is one of `UNDEFINED`, `HRAP`, `ALBERS`, `SPECIFIED`.
- Regular time series: the E part sets the interval. Irregular: E part starts with `IR-` or `~`.
- Leave the D part empty to read a whole time series; use `start` / `end` for a window.
- Missing values are `NaN` for all record types.
- HEC-DSS log output is set by the `DSS_MESSAGE_LEVEL` environment variable (0 = none to 15 = debug); default and fallback is 1 (critical only).
- Gridded `xll`, `yll` must line up with `origin` in whole multiples of `cell_size`.

## Tools

Command-line tools in [`tools/`](https://github.com/nzahasan/pyheclib/blob/main/tools):

```bash
python3 tools/dss_browser.py file.dss [--port 8765] [--no-browser]   # browse a file in your web browser
python3 tools/dss_catalog.py file.dss [filter] [--condensed]         # list records
python3 tools/dssrec2csv.py file.dss pathname out.csv                # export one record to csv
```

The browser opens one or more files in tabs (or drag files onto the page). Search records by
text or by part (`B=GAGE C=FLOW*`), view metadata, statistics, a graph or table of the data,
and download a record as csv. Each record has its own link (`/?file=1&path=/A/B/C/D/E/F/`).

![dss browser, light mode](https://raw.githubusercontent.com/nzahasan/pyheclib/main/assets/readme/dss_browser_light.png)

![dss browser, dark mode](https://raw.githubusercontent.com/nzahasan/pyheclib/main/assets/readme/dss_browser.png)

## Examples and notebooks

- [examples/example.dss](https://github.com/nzahasan/pyheclib/blob/main/examples/example.dss) has every record type to try things on
  (rebuild it with `python3 examples/make_example_dss.py`).
- [examples/make_readme_figures.py](https://github.com/nzahasan/pyheclib/blob/main/examples/make_readme_figures.py) draws the figures in this README.
- Notebooks, each writes records, reads them back and checks the result:
  [regular time series](https://github.com/nzahasan/pyheclib/blob/main/notebooks/01_regular_timeseries.ipynb),
  [irregular time series](https://github.com/nzahasan/pyheclib/blob/main/notebooks/02_irregular_timeseries.ipynb),
  [paired data](https://github.com/nzahasan/pyheclib/blob/main/notebooks/03_paired_data.ipynb),
  [gridded data](https://github.com/nzahasan/pyheclib/blob/main/notebooks/04_gridded_data.ipynb),
  [catalog, paths and delete](https://github.com/nzahasan/pyheclib/blob/main/notebooks/05_catalog_paths_delete.ipynb).

## Development

```bash
git clone https://github.com/nzahasan/pyheclib && cd pyheclib
pip install -r requirements.txt
python3 setup.py build_ext --inplace    # rebuild after editing src/*.pyx or src/*.pxd
pytest                                  # also runs the code in this README
```

Code layout:

- `pyheclib/records.py`: record classes
- `pyheclib/dsspath.py`: `DssPath`
- `pyheclib/dssfile.py`: `open` and `DssFile`
- `src/_core.pyx`: thin Cython wrapper around the HEC-DSS C API

## Resources

- [Documentation](https://nzahasan.github.io/pyheclib)
- [HEC-DSS](https://www.hec.usace.army.mil/software/hec-dss/)
- [HEC-DSSVue](https://www.hec.usace.army.mil/software/hec-dssvue/), a desktop viewer for DSS files
