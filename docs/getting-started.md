# Getting started

## Open and close a file

```python
import pyheclib as phl

dss_file = phl.open("example.dss")   # opens the file, or creates it if it does not exist
# ... read and write records ...
dss_file.close()
```

You can also use `with`. The file is closed for you at the end of the block:

```python
with phl.open("example.dss") as dss_file:
    print(dss_file.catalog())
```

## How records work

Every record is a Python object. It holds the pathname, the data and the metadata
(units, data type and so on). The steps are always the same:

1. Create a record object.
2. Save it with `dss_file.write(record)`.
3. Load it with `dss_file.read(pathname)`. You get back the same kind of object.
4. Remove it with `dss_file.delete(pathname)`.

Writing to a pathname that already has data replaces that data.

## Pathnames

Each record is stored under a pathname with six parts: `/A/B/C/D/E/F/`.

| Part | Usual meaning | Example |
|---|---|---|
| A | project or basin | `DEMO` |
| B | location | `OUTLET` |
| C | parameter | `FLOW` |
| D | start date or time | `01JAN2020` |
| E | interval or end time | `1HOUR` |
| F | version or source | `OBS` |

`DssPath` helps you work with the parts. Anywhere a pathname is needed you can pass
a `DssPath` or a plain string.

```python
path = phl.DssPath("/DEMO/OUTLET/FLOW/01JAN2020/1HOUR/OBS/")
path.C                        # 'FLOW'
path.replace(F="SIM")         # DssPath('/DEMO/OUTLET/FLOW/01JAN2020/1HOUR/SIM/')
path.without_date()           # DssPath('/DEMO/OUTLET/FLOW//1HOUR/OBS/')
phl.DssPath.from_parts(A="DEMO", C="STAGE-FLOW", F="RATING")
```

## List the records in a file

```python
dss_file = phl.open("example.dss")
dss_file.catalog()                                  # every record
dss_file.catalog(condensed=True)                    # one line per time series
dss_file.catalog("/DEMO/*/FLOW/*/*/*/")             # only matching records
dss_file.catalog(condensed=True, with_types=True)   # (path, record type code) pairs
```

DSS stores a long time series in blocks, for example one block per month for hourly data.
`catalog()` shows every block. `catalog(condensed=True)` shows each time series once,
with the D part set to its date range, like `01JAN2020-01MAR2020`.

## Find records

`find` returns the pathnames that match. Put `*` at the start or end of any part to match many values.

```python
dss_file.find("/DEMO/*/*/*/*/OBS/")      # every OBS record in DEMO
dss_file.find("/*/*/STAGE*/*/*/*/")      # STAGE and STAGE-FLOW records
```

## Delete records

`delete` removes every record that matches, and returns the pathnames it removed.
It raises `KeyError` if nothing matches. Each record type page shows a delete example.

```text
dss_file.delete("/SHG/*/*/*/*/*/")       # everything with A part SHG
dss_file.close()
```

## Missing values

Missing values are `NaN` in every record type. pyheclib converts them to and from the
DSS missing value for you.
