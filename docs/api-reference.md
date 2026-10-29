# API reference

A short summary of everything in pyheclib. Each record type page has more detail and examples.

## Functions and classes

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

## Rules worth knowing

- `type` is one of `INST-VAL`, `INST-CUM`, `PER-AVER`, `PER-CUM`, `FREQ`.
- `grid_type` is one of `UNDEFINED`, `HRAP`, `ALBERS`, `SPECIFIED`.
- Regular time series: the E part sets the interval. Irregular: E part starts with `IR-` or `~`.
- Leave the D part empty to read a whole time series; use `start` / `end` for a window.
- Missing values are `NaN` for all record types.
- Gridded `xll`, `yll` must line up with `origin` in whole multiples of `cell_size`.
