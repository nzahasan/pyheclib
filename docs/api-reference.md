# API reference

Everything you can use from pyheclib, with a short description of each class and function.
The record type pages have longer examples.

```python
import pyheclib as phl
```

| Name | What it is |
|---|---|
| [`open`](#open) | open or create a DSS file |
| [`DssFile`](#dssfile) | an open DSS file, used to write, read, list and delete records |
| [`RegularTs`](#regularts) | regular time series record |
| [`IrregularTs`](#irregularts) | irregular time series record |
| [`PairedData`](#paireddata) | paired data (curves) record |
| [`GriddedData`](#griddeddata) | gridded data (raster) record |
| [`DssPath`](#dsspath) | a DSS pathname split into its six parts |
| [`set_message_level`](#set_message_level) | set how much the HEC-DSS library logs |
| [`message_level_from_env`](#message_level_from_env) | read the log level from `DSS_MESSAGE_LEVEL` |
| [`api_version`](#api_version) | version of the bundled HEC-DSS library |

## Files

### open

```python
phl.open(filename) -> DssFile
```

Opens a DSS version 7 file. If the file does not exist, it is created.
Returns a [`DssFile`](#dssfile).

| Parameter | Type | Description |
|---|---|---|
| `filename` | `str` | path of the `.dss` file |

```python
dss_file = phl.open("example.dss")

with phl.open("example.dss") as dss_file:    # closed for you at the end of the block
    ...
```

### DssFile

An open DSS file. Create it with [`phl.open`](#open). It works as a context manager,
so you can use it in a `with` block.

#### Attributes

| Name | Type | Description |
|---|---|---|
| `filename` | `str` | path of the file |
| `is_open` | `bool` | `True` until the file is closed |

#### write

```python
dss_file.write(record) -> None
```

Saves a record to the file. `record` is a `RegularTs`, `IrregularTs`, `PairedData` or `GriddedData`.

Existing data at the same pathname is replaced:

- time series: only the values inside the time span of the new record
- paired and gridded data: the whole record

Raises `TypeError` for an unknown record type and `IOError` if HEC-DSS cannot write it.

#### read

```python
dss_file.read(path, start=None, end=None) -> RegularTs | IrregularTs | PairedData | GriddedData
```

Loads a record. The kind of record you get back depends on what is stored at `path`.

| Parameter | Type | Description |
|---|---|---|
| `path` | `str` or `DssPath` | pathname of the record |
| `start` | `str`, `datetime` or `None` | time series only: start of the time window |
| `end` | `str`, `datetime` or `None` | time series only: end of the time window |

For a time series, an empty D part reads the whole series. Give both `start` and `end`
to read only part of it. Raises `KeyError` if the record does not exist.

#### catalog

```python
dss_file.catalog(path_filter="", condensed=False, with_types=False) -> list
```

Lists the records in the file as a list of [`DssPath`](#dsspath).

| Parameter | Type | Description |
|---|---|---|
| `path_filter` | `str` | only list matching pathnames, `*` matches many values |
| `condensed` | `bool` | list each time series once, with its date range in the D part (like `01JAN2020-01MAR2020`) instead of once per block |
| `with_types` | `bool` | return `(DssPath, record type code)` pairs |

A condensed pathname can be passed to `read`, `find` and `delete`.

#### find

```python
dss_file.find(path) -> list[DssPath]
```

Returns the pathnames of stored records that match `path`.

- `*` at the start or end of a part matches many values, like `/A/*/FLOW/*/*/*/` or `/A/B/FL*/*/*/*/`.
- A time series pathname with an empty D part matches every block of that series.
- A date range in the D part, like `01JAN2020-01MAR2020`, matches the blocks inside that range.

#### delete

```python
dss_file.delete(path) -> list[DssPath]
```

Deletes every record that matches `path` (same matching rules as [`find`](#find))
and returns the pathnames it deleted. Raises `KeyError` if nothing matches.

#### record_type

```python
dss_file.record_type(path) -> int
```

Returns the HEC-DSS record type code of a record. Raises `KeyError` if the record does not exist.

| Code | Record type |
|---|---|
| 105 | regular time series |
| 115 | irregular time series |
| 205 | paired data |
| 4xx | gridded data (420, 430 and so on, by grid type) |

#### version

```python
dss_file.version() -> int
```

Returns the DSS file version. Always `7`.

#### close

```python
dss_file.close() -> None
```

Closes the file. A `with` block calls this for you.

## Records

Records are plain Python objects. Create one, then save it with [`write`](#write).
[`read`](#read) gives you the same kind of object back. You can also read and change
every field directly, like `record.unit` or `record.values`.

### RegularTs

```python
phl.RegularTs(path, values, start, unit="", type="INST-VAL", time_zone="", save_as_float=False)
```

A time series with one value per fixed time step. The E part of the pathname sets the
time step. Only the HEC-DSS standard intervals are accepted, any other E part raises `ValueError`:

- `1SECOND`, `2SECOND`, `3SECOND`, `4SECOND`, `5SECOND`, `6SECOND`, `10SECOND`, `15SECOND`, `20SECOND`, `30SECOND`
- `1MINUTE`, `2MINUTE`, `3MINUTE`, `4MINUTE`, `5MINUTE`, `6MINUTE`, `10MINUTE`, `12MINUTE`, `15MINUTE`, `20MINUTE`, `30MINUTE`
- `1HOUR`, `2HOUR`, `3HOUR`, `4HOUR`, `6HOUR`, `8HOUR`, `12HOUR`
- `1DAY`, `1WEEK`, `SEMI-MONTH` (periods start on the 1st and 16th), `TRI-MONTH` (1st, 11th and 21st), `1MONTH`, `1YEAR`

| Parameter | Type | Description |
|---|---|---|
| `path` | `str` or `DssPath` | pathname, like `/BASIN/GAGE/FLOW//1HOUR/OBS/` |
| `values` | list or 1d array | the values, `NaN` for missing |
| `start` | `str` or `datetime` | time of the first value |
| `unit` | `str` | unit, like `CFS` |
| `type` | `str` | data type, see [data types](#data-types) |
| `time_zone` | `str` | time zone name, like `UTC` |
| `save_as_float` | `bool` | store as 32 bit floats to save space |

| Attribute or method | Description |
|---|---|
| `interval` | the time step, taken from the E part |
| `times` | pandas `DatetimeIndex` with the time of each value |
| `quality` | quality flags as a numpy array, only when read and present in the file |
| `to_series()` | returns a pandas `Series` indexed by time |
| `RegularTs.from_series(path, series, unit="", type="INST-VAL", **options)` | creates a record from a pandas `Series` with evenly spaced times |

Monthly and yearly values that cover a whole period are stamped at the start of the next
period. For example, the January 2020 value is at `01FEB2020 00:00`.

### IrregularTs

```python
phl.IrregularTs(path, times, values, unit="", type="INST-VAL", time_zone="", save_as_float=False)
```

A time series with values at any times. The E part starts with `IR-` or `~` and sets the
storage block size, like `IR-DAY`, `IR-MONTH` or `IR-YEAR`.

| Parameter | Type | Description |
|---|---|---|
| `path` | `str` or `DssPath` | pathname, like `/BASIN/GAGE/STAGE//IR-MONTH/OBS/` |
| `times` | list of times or `DatetimeIndex` | time of each value, sorted and unique |
| `values` | list or 1d array | the values, `NaN` for missing |
| `unit`, `type`, `time_zone`, `save_as_float` | | same as [`RegularTs`](#regularts) |

Times are stored to the second. Raises `ValueError` if `times` and `values` have different
lengths, or if the times are not sorted and unique.

| Attribute or method | Description |
|---|---|
| `quality` | quality flags as a numpy array, only when read and present in the file |
| `to_series()` | returns a pandas `Series` indexed by time |
| `IrregularTs.from_series(path, series, unit="", type="INST-VAL", **options)` | creates a record from a pandas `Series` with a time index |

### PairedData

```python
phl.PairedData(path, x, y, x_unit="", y_unit="", x_type="Linear", y_type="Linear", labels=[], time_zone="")
```

One or more curves that share the same x values, like a rating table.

| Parameter | Type | Description |
|---|---|---|
| `path` | `str` or `DssPath` | pathname, like `/BASIN/GAGE/STAGE-FLOW///RATING/` |
| `x` | list or 1d array | x values, shared by all curves |
| `y` | 1d or 2d array | y values, shape `[number of curves, number of points]`. A 1d array is one curve. |
| `x_unit`, `y_unit` | `str` | units of x and y |
| `x_type`, `y_type` | `str` | axis type, like `Linear` or `Log` |
| `labels` | list of `str` | a name for each curve, optional |
| `time_zone` | `str` | time zone name |

Raises `ValueError` if `y` does not match the length of `x`, or if the number of labels
does not match the number of curves.

| Attribute or method | Description |
|---|---|
| `n_curves` | number of curves |
| `to_dataframe()` | returns a pandas `DataFrame` with x as the index and one column per curve |
| `PairedData.from_dataframe(path, df, x_unit="", y_unit="", **options)` | creates a record from a `DataFrame`. The index is x, each column is a curve, column names become labels. |

### GriddedData

```python
phl.GriddedData(path, data, cell_size, xll, yll, unit="", type="INST-VAL", grid_type="SPECIFIED",
                srs_wkt="", srs_name="", origin=(0, 0), data_source="", time_zone="")
```

A raster, like a radar rainfall grid or a DEM. The D and E parts are the start and end time,
like `15JAN2020:0000`. Leave both empty for a grid that does not change over time.

| Parameter | Type | Description |
|---|---|---|
| `path` | `str` or `DssPath` | pathname, like `/SHG/BASIN/PRECIP/15JAN2020:0000/15JAN2020:0600/RADAR/` |
| `data` | 2d array | grid values with shape `[rows, columns]`. The first row is the northern most. `NaN` means no data. Stored as `float32`. |
| `cell_size` | `float` | width and height of a cell |
| `xll`, `yll` | `float` | x and y of the lower left corner of the grid |
| `unit` | `str` | unit, like `MM` |
| `type` | `str` | data type, see [data types](#data-types) |
| `grid_type` | `str` | `UNDEFINED`, `HRAP`, `ALBERS` or `SPECIFIED` |
| `srs_wkt` | `str` | coordinate system as WKT text |
| `srs_name` | `str` | coordinate system name, like `SHG` |
| `origin` | `(x, y)` | origin of the grid system. `xll` and `yll` must be a whole number of cells away from it. |
| `data_source` | `str` | where the data came from |
| `time_zone` | `str` | time zone name, like `UTC` |

Raises `ValueError` if `data` is not a non empty 2d array, `cell_size` is not positive,
`grid_type` is unknown, or the corner does not line up with `origin`.

| Attribute | Description |
|---|---|
| `shape` | `(rows, columns)` of the grid |
| `extent` | `(xmin, xmax, ymin, ymax)`, handy for `matplotlib.pyplot.imshow(g.data, extent=g.extent)` |
| `lower_left_cell` | `(x, y)` cell index of the lower left cell, counted in cells from `origin` |
| `start_time` | D part of the pathname, or `None` |
| `end_time` | E part of the pathname, or `None` |

## Pathnames

### DssPath

```python
phl.DssPath(path)
phl.DssPath.from_parts(A="", B="", C="", D="", E="", F="")
```

A DSS pathname, `/A/B/C/D/E/F/`, split into its six parts. Every function that takes a
pathname accepts a `DssPath` or a plain string, and `catalog`, `find` and `delete` return
`DssPath` objects.

A `DssPath` cannot be changed. Use `replace` to get a new one. Two pathnames are equal
when they match without looking at upper or lower case, and a `DssPath` can be compared
with a string.

Raises `ValueError` if the pathname does not have six parts, is longer than 393 characters,
or has a part longer than 64 characters.

| Attribute or method | Description |
|---|---|
| `A`, `B`, `C`, `D`, `E`, `F` | the parts as strings |
| `parts()` | the parts as a dict, `{"A": ..., "F": ...}` |
| `replace(**parts)` | a new pathname with some parts changed, like `path.replace(F="SIM")` |
| `without_date()` | a new pathname with an empty D part, which means the whole time series |
| `from_parts(A=..., F=...)` | builds a pathname from parts, missing parts are empty |
| `str(path)` | the pathname as a string |

```python
path = phl.DssPath("/DEMO/OUTLET/FLOW/01JAN2020/1HOUR/OBS/")
path.C                    # 'FLOW'
path.replace(F="SIM")     # DssPath('/DEMO/OUTLET/FLOW/01JAN2020/1HOUR/SIM/')
path.without_date()       # DssPath('/DEMO/OUTLET/FLOW//1HOUR/OBS/')
```

## Settings

### set_message_level

```python
phl.set_message_level(level) -> int
```

Sets how many log messages the HEC-DSS library prints, from `0` (nothing) to `15` (everything).
`1` prints only critical errors, `3` gives general information. Returns `0` on success.

When pyheclib is imported, the level is set from [`message_level_from_env`](#message_level_from_env).

### message_level_from_env

```python
phl.message_level_from_env() -> int
```

Reads the `DSS_MESSAGE_LEVEL` environment variable. Returns its value if it is a whole number
from 0 to 15, otherwise returns `1`.

```bash
DSS_MESSAGE_LEVEL=3 python my_script.py
```

### api_version

```python
phl.api_version() -> str
```

Returns the version of the bundled HEC-DSS C library API, like `0.3.0`.

### \_\_version\_\_

`phl.__version__` is the pyheclib version, like `0.4.1`.

## Values you can use

### Data types

The `type` option of time series and gridded records is one of:

| Type | Meaning |
|---|---|
| `INST-VAL` | instant value at that time, like stage or flow |
| `INST-CUM` | running total at that time, like a rain gage counter |
| `PER-AVER` | average over the period ending at that time |
| `PER-CUM` | total over the period ending at that time, like hourly rainfall |
| `FREQ` | frequency value |

### Other rules

- Missing values are `NaN` in every record type.
- Regular time series: the E part sets the time step and must be a [standard interval](#regularts). Irregular: the E part starts with `IR-` or `~`.
- Leave the D part empty to read a whole time series. Use `start` and `end` for part of it.
- Quality flags are read when present, but not written.
