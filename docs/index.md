# pyheclib

Read and write [HEC-DSS](https://www.hec.usace.army.mil/software/hec-dss/) files from Python.

HEC-DSS is the database format used by HEC-HMS, HEC-RAS and other tools from the
[US Army Corps of Engineers' Hydrologic Engineering Center](https://www.hec.usace.army.mil/).
pyheclib works with **DSS version 7** files and gives you the data as numpy arrays
and pandas objects.

## What you can store

| Record type | Use it for | Page |
|---|---|---|
| `RegularTs` | time series with a fixed interval, like hourly flow | [Regular time series](records/regular-time-series.md) |
| `IrregularTs` | time series with any timing, like field readings | [Irregular time series](records/irregular-time-series.md) |
| `PairedData` | curves, like rating or storage tables | [Paired data](records/paired-data.md) |
| `GriddedData` | rasters, like radar rainfall or a DEM | [Gridded data](records/gridded-data.md) |

## Install

```bash
pip install pyheclib
```

Works on Python 3.8 or newer. Prebuilt packages are available for:

- Linux (x86_64)
- macOS (Apple Silicon, macOS 14 or newer)
- Windows (64 bit)

!!! note
    DSS version 6 files are not supported. Open them in
    [HEC-DSSVue](https://www.hec.usace.army.mil/software/hec-dssvue/) and save them as version 7 first.

## A short example

```python
import pyheclib as phl

with phl.open("example.dss") as dss_file:
    flow = phl.RegularTs("/BASIN/GAGE/FLOW//1HOUR/OBS/", values=[10.0, 12.5, 15.0],
                         start="2020-01-01 01:00", unit="CFS")
    dss_file.write(flow)

    record = dss_file.read("/BASIN/GAGE/FLOW//1HOUR/OBS/")
    print(record.to_series())
```

Next, read [Getting started](getting-started.md) to learn how files and pathnames work.
