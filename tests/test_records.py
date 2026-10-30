''' record classes on their own, no dss file involved '''
import numpy as np
import pandas as pd
import pytest
import pyheclib as phl
from pyheclib import DssPath
from pyheclib.records import interval_offset


@pytest.mark.parametrize("e_part, second", [
	("1MINUTE", "2020-01-31 00:01"), ("15MINUTE", "2020-01-31 00:15"), ("6HOUR", "2020-01-31 06:00"),
	("1DAY", "2020-02-01"), ("1WEEK", "2020-02-07"), ("1MONTH", "2020-02-29"), ("1YEAR", "2021-01-31"),
])
def test_regular_times_from_interval(e_part, second):
	rts = phl.RegularTs(f"/A/B/C//{e_part}/F/", [1.0, 2.0, 3.0], "2020-01-31")
	assert rts.interval == e_part
	assert rts.times[0] == pd.Timestamp("2020-01-31")
	assert rts.times[1] == pd.Timestamp(second)
	assert rts.times.size == 3 and rts.times.name == "Time"


@pytest.mark.parametrize("e_part, times", [
	("1SECOND", ["2020-01-01 00:00:00", "2020-01-01 00:00:01", "2020-01-01 00:00:02", "2020-01-01 00:00:03"]),
	("SEMI-MONTH", ["2020-01-16", "2020-02-01", "2020-02-16", "2020-03-01"]),
	("TRI-MONTH", ["2020-01-21", "2020-02-01", "2020-02-11", "2020-02-21"]),
])
def test_regular_times_any_interval(e_part, times):
	start = times[0]
	rts = phl.RegularTs(f"/A/B/C//{e_part}/F/", [1.0, 2.0, 3.0, 4.0], start)
	assert rts.times.equals(pd.DatetimeIndex(times, name="Time"))


def test_unsupported_interval():
	with pytest.raises(ValueError):
		interval_offset("IR-MONTH")
	for e_part in ("IR-MONTH", "15MIN", "7HOUR", "2DAY"):        # heclib rejects these
		with pytest.raises(ValueError):
			phl.RegularTs(f"/A/B/C//{e_part}/F/", [1.0], "2020-01-01")
	for e_part in ("1HOUR", "1DAY"):                            # irregular needs IR- or ~
		with pytest.raises(ValueError):
			phl.IrregularTs(f"/A/B/C//{e_part}/F/", ["2020-01-01"], [1.0])
	phl.IrregularTs("/A/B/C//~1DAY/F/", ["2020-01-01"], [1.0])


def test_regular_ts_fields():
	rts = phl.RegularTs("/A/B/FLOW//1HOUR/F/", [1, 2, np.nan], "2020-01-01 06:00", unit="cfs", type="per-aver")
	assert isinstance(rts.path, DssPath)
	assert rts.values.dtype == np.float64
	assert rts.type == "PER-AVER"                     # type is normalised to upper case
	assert rts.start == pd.Timestamp("2020-01-01 06:00")
	assert rts.quality is None and not rts.save_as_float

	series = rts.to_series()
	assert series.name == "FLOW" and series.index[-1] == pd.Timestamp("2020-01-01 08:00")
	assert np.isnan(series.iloc[-1])


def test_regular_from_series_sorts():
	idx = pd.date_range("2020-01-01", periods=4, freq="D")
	series = pd.Series([1.0, 2.0, 3.0, 4.0], index=idx)[::-1]
	rts = phl.RegularTs.from_series("/A/B/C//1DAY/F/", series, "cfs", "INST-VAL", time_zone="UTC")
	assert rts.start == idx[0] and rts.values.tolist() == [1.0, 2.0, 3.0, 4.0]
	assert rts.time_zone == "UTC"


def test_irregular_ts_validation():
	times = pd.to_datetime(["2020-01-01", "2020-01-05"])
	its = phl.IrregularTs("/A/B/STAGE//IR-MONTH/F/", times, [1, 2])
	assert its.to_series().name == "STAGE"
	assert its.times.name == "Time"

	with pytest.raises(ValueError):
		phl.IrregularTs("/A/B/C//IR-MONTH/F/", times, [1.0])                   # size mismatch
	with pytest.raises(ValueError):
		phl.IrregularTs("/A/B/C//IR-MONTH/F/", times[[0, 0]], [1.0, 2.0])      # duplicate times
	with pytest.raises(ValueError):
		phl.IrregularTs("/A/B/C//IR-MONTH/F/", times, [1.0, 2.0], type="BAD")


def test_paired_dataframe_columns():
	x = [0.0, 1.0, 2.0]
	assert list(phl.PairedData("/A/B/STAGE-FLOW///R/", x, [1, 2, 3]).to_dataframe().columns) == ["FLOW"]
	assert list(phl.PairedData("/A/B/STAGE-FLOW///R/", x, [[1, 2, 3], [4, 5, 6]]).to_dataframe().columns) == ["FLOW_1", "FLOW_2"]
	assert list(phl.PairedData("/A/B/STAGE-FLOW///R/", x, [[1, 2, 3], [4, 5, 6]], labels=["a", 2]).to_dataframe().columns) == ["a", "2"]

	df = phl.PairedData("/A/B/ELEVATION///R/", x, [1, 2, 3]).to_dataframe()
	assert df.index.name == "ELEVATION" and list(df.columns) == ["Y"]


def test_paired_validation():
	with pytest.raises(ValueError):
		phl.PairedData("/A/B/C///R/", [0.0, 1.0], [[1.0, 2.0]], labels=["a", "b"])
	with pytest.raises(ValueError):
		phl.PairedData("/A/B/C///R/", [], [])


def test_paired_from_dataframe():
	df = pd.DataFrame({"low": [1.0, 2.0], "high": [3.0, 4.0]}, index=[0.5, 1.5])
	rec = phl.PairedData.from_dataframe("/A/B/STAGE-FLOW///R/", df, "FT", "CFS", y_type="Log")
	assert rec.labels == ["low", "high"] and rec.n_curves == 2
	np.testing.assert_allclose(rec.y, df.values.T)
	assert (rec.x_unit, rec.y_unit, rec.y_type) == ("FT", "CFS", "Log")


def test_gridded_properties():
	grid = phl.GriddedData("/A/B/PRECIP/01JAN2020:0000/01JAN2020:0100/F/", np.zeros((3, 4)),
		cell_size=10.0, xll=120.0, yll=50.0, origin=(100.0, 20.0), grid_type="albers", type="per-cum")
	assert grid.data.dtype == np.float32
	assert grid.shape == (3, 4)
	assert grid.lower_left_cell == (2, 3)
	assert grid.extent == (120.0, 160.0, 50.0, 80.0)
	assert (grid.grid_type, grid.type) == ("ALBERS", "PER-CUM")
	assert (grid.start_time, grid.end_time) == ("01JAN2020:0000", "01JAN2020:0100")

	dem = phl.GriddedData("/A/B/ELEVATION///F/", np.zeros((2, 2)), 1.0, 0.0, 0.0)
	assert dem.start_time is None and dem.end_time is None


@pytest.mark.parametrize("kwargs", [
	{"cell_size": 0.0}, {"grid_type": "LATLON"}, {"data": np.zeros(4)}, {"data": np.zeros((0, 3))},
	{"xll": 5.0}, {"type": "NONE"},
])
def test_gridded_validation(kwargs):
	args = {"path": "/A/B/C///F/", "data": np.zeros((2, 2)), "cell_size": 10.0, "xll": 0.0, "yll": 0.0}
	args.update(kwargs)
	with pytest.raises(ValueError):
		phl.GriddedData(**args)
