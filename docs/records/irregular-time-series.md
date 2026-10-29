# Irregular time series

An irregular time series has values at any times, like manual stage readings.
In pyheclib it is an `IrregularTs` record.

![Irregular time series](../images/irregular_ts.png)

## Pathname

The E part starts with `IR-` (or `~`) and sets the block size used for storage, for example
`IR-DAY`, `IR-MONTH` or `IR-YEAR`. Pick a block size that holds a sensible number of values.
Leave the D part empty.

```text
/DEMO/OUTLET/STAGE//IR-MONTH/OBS/
```

## Write

From times and values:

```python
import pandas as pd
import pyheclib as phl

dss_file = phl.open("example.dss")

stage = phl.IrregularTs("/DEMO/OUTLET/STAGE//IR-MONTH/OBS/",
                        times=pd.to_datetime(["2020-01-14 08:13:00",
                                              "2020-01-15 07:30:15",
                                              "2020-01-16 16:45:00"]),
                        values=[3.1, 4.6, 3.4], unit="FT", type="INST-VAL")
dss_file.write(stage)
```

From a pandas Series with a time index:

```python
series = pd.Series([3.1, 4.6, 3.4], index=pd.to_datetime(["2020-01-14 08:13",
                                                           "2020-01-15 07:30",
                                                           "2020-01-16 16:45"]))
dss_file.write(phl.IrregularTs.from_series("/DEMO/OUTLET/STAGE//IR-MONTH/OBS/", series, unit="FT"))
```

Times are stored to the second. Writing replaces stored values inside the time span
of the new record. Values outside that span are kept.

## Read

```python
its = dss_file.read("/DEMO/OUTLET/STAGE//IR-MONTH/OBS/")   # IrregularTs
its.times         # pandas DatetimeIndex
its.values        # numpy array
its.to_series()   # pandas Series
```

Read only a time window with `start` and `end`:

```python
its = dss_file.read("/DEMO/OUTLET/STAGE//IR-MONTH/OBS/", start="2020-01-15", end="2020-01-16")
```

## Delete

An empty D part deletes the whole series:

```python
dss_file.delete("/DEMO/OUTLET/STAGE//IR-MONTH/OBS/")
```

## Options

| Option | Default | Meaning |
|---|---|---|
| `unit` | `""` | unit of the values, like `FT` |
| `type` | `"INST-VAL"` | `INST-VAL`, `INST-CUM`, `PER-AVER`, `PER-CUM` or `FREQ` |
| `time_zone` | `""` | time zone name, like `UTC` |
| `save_as_float` | `False` | store values as 32 bit floats to save space |
