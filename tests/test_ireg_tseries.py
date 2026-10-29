import numpy as np
import pandas as pd
import pytest
import pyheclib as phl

PATH = "/BASIN/LOCATION/STAGE//IR-MONTH/TEST/"


def test_irregular_roundtrip(dss):
	times = pd.to_datetime([
		"2019-12-31 23:59:00", "2020-01-01 00:13:00", "2020-01-05 07:30:15",
		"2020-02-29 12:00:00", "2020-03-01 00:00:00", "2020-07-04 18:45:00",
	])
	values = [1.1, 2.2, np.nan, 4.4, 5.5, 6.6]

	dss.write(phl.IrregularTs(PATH, times, values, unit="ft", type="INST-VAL"))

	out = dss.read(PATH)
	assert isinstance(out, phl.IrregularTs)
	assert out.times.equals(pd.DatetimeIndex(times, name="Time"))
	np.testing.assert_allclose(out.values, values)
	assert out.unit == "ft"


def test_irregular_from_series(dss):
	rng = np.random.default_rng(0)
	offsets = np.sort(rng.choice(np.arange(1, 400 * 24 * 60), 2000, replace=False))
	idx = pd.Timestamp("2020-01-01") + pd.to_timedelta(offsets, unit="min")
	series = pd.Series(rng.normal(size=idx.size), index=idx)

	dss.write(phl.IrregularTs.from_series(PATH, series, "ft"))
	out = dss.read(PATH).to_series()

	assert out.index.equals(series.index.rename("Time"))
	np.testing.assert_allclose(out.values, series.values)


def test_unsorted_times_rejected():
	with pytest.raises(ValueError):
		phl.IrregularTs(PATH, pd.to_datetime(["2020-01-02", "2020-01-01"]), [1.0, 2.0])
