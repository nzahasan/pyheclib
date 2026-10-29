import numpy as np
import pandas as pd
import pytest
import pyheclib as phl

PATH = "/BASIN/LOCATION/FLOW//1HOUR/TEST/"


def test_regular_roundtrip(dss):
	values = np.array([13.21, 44.21, 13.24, 55.21, 88.76, 77.33])
	rts = phl.RegularTs(PATH, values, "2020-01-01 06:00", unit="cfs", type="INST-VAL")
	dss.write(rts)

	out = dss.read(PATH)
	assert isinstance(out, phl.RegularTs)
	np.testing.assert_allclose(out.values, values)
	assert out.start == pd.Timestamp("2020-01-01 06:00")
	assert out.times.equals(rts.times)
	assert (out.unit, out.type, out.interval) == ("cfs", "INST-VAL", "1HOUR")


def test_series_multi_block_and_nan(dss):
	# ~2 years of hourly data spans many monthly DSS blocks
	idx = pd.date_range("2019-03-01 01:00", "2021-02-01 00:00", freq="h")
	series = pd.Series(np.sin(np.arange(idx.size) / 50.0), index=idx)
	series.iloc[[10, 5000, 12000]] = np.nan

	dss.write(phl.RegularTs.from_series(PATH, series, "cfs", "PER-AVER"))
	out = dss.read(PATH).to_series()

	assert out.index.equals(series.index.rename("Time"))
	np.testing.assert_allclose(out.values, series.values)
	assert out.isna().sum() == 3
	# Mar 2019 .. Jan 2021 monthly blocks, 01Feb2021 0000 is 2400 of 31Jan
	assert len(dss.catalog("/BASIN/LOCATION/FLOW/*/1HOUR/TEST/")) == 23


def test_time_window(dss):
	dss.write(phl.RegularTs(PATH, np.arange(96.0), "2020-01-01", unit="cfs"))

	out = dss.read(PATH, start="2020-01-02 00:00", end="2020-01-02 05:00")
	assert out.start == pd.Timestamp("2020-01-02")
	np.testing.assert_allclose(out.values, np.arange(24.0, 30.0))

	with pytest.raises(ValueError):
		dss.read(PATH, start="2020-01-02")


def test_daily_float_storage(dss):
	values = np.arange(5, dtype=np.float32) * 1.5
	dss.write(phl.RegularTs("/A/B/TEMP//1DAY/Q/", values, "2021-01-02", "C", "PER-AVER", save_as_float=True))

	out = dss.read("/A/B/TEMP//1DAY/Q/")
	np.testing.assert_allclose(out.values, values)
	assert out.times[-1] == pd.Timestamp("2021-01-06")
	assert dss.record_type("/A/B/TEMP//1DAY/Q/") == 100


def test_monthly_interval(dss):
	dss.write(phl.RegularTs("/A/B/VOLUME//1MONTH/M/", [1.0, 2.0, 3.0], "2020-02-01", "AF", "PER-CUM"))
	out = dss.read("/A/B/VOLUME//1MONTH/M/")
	np.testing.assert_allclose(out.values, [1.0, 2.0, 3.0])


def test_invalid_records():
	with pytest.raises(ValueError):
		phl.RegularTs("/A/B/C/", [1.0], "2020-01-01")
	with pytest.raises(ValueError):
		phl.RegularTs(PATH, [], "2020-01-01")
	with pytest.raises(ValueError):
		phl.RegularTs(PATH, [1.0], "2020-01-01", type="AVERAGE")
