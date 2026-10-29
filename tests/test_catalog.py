import numpy as np
import pandas as pd
import pyheclib as phl
from pyheclib import DssPath


def fill(dss):
	idx = pd.date_range("2020-01-01 01:00", "2020-04-01 00:00", freq="h")   # Jan .. Mar blocks
	dss.write(phl.RegularTs.from_series("/A/B/FLOW//1HOUR/F/", pd.Series(np.arange(idx.size, dtype=float), idx)))
	dss.write(phl.RegularTs("/A/B/TEMP//1DAY/F/", [1.0, 2.0], "2021-06-02"))       # single block
	dss.write(phl.IrregularTs("/A/B/STAGE//IR-YEAR/F/", pd.to_datetime(["2019-05-01", "2021-03-01"]), [1.0, 2.0]))
	dss.write(phl.PairedData("/A/B/STAGE-FLOW///R/", [1.0, 2.0], [3.0, 4.0]))
	dss.write(phl.GriddedData("/SHG/B/PRECIP/01JAN2020:0000/01JAN2020:0100/F/", np.ones((2, 2)), 10.0, 0.0, 0.0))


def test_condensed_catalog(dss):
	fill(dss)
	assert len(dss.catalog()) == 8

	condensed = dss.catalog(condensed=True)
	assert all(isinstance(path, DssPath) for path in condensed)
	assert condensed == [
		"/A/B/FLOW/01JAN2020-01MAR2020/1Hour/F/",
		"/A/B/TEMP/01JAN2021/1Day/F/",      # 1DAY data is stored in yearly blocks
		"/A/B/STAGE/01JAN2019-01JAN2021/IR-Year/F/",
		"/A/B/STAGE-FLOW///R/",
		"/SHG/B/PRECIP/01JAN2020:0000/01JAN2020:0100/F/",
	]

	codes = [code for _, code in dss.catalog(condensed=True, with_types=True)]
	assert codes == [105, 105, 115, 205, 430]   # grid default type is SPECIFIED


def test_condensed_catalog_filter(dss):
	fill(dss)
	assert dss.catalog("/A/B/FLOW/*/*/*/", condensed=True) == ["/A/B/FLOW/01JAN2020-01MAR2020/1Hour/F/"]


def test_read_condensed_path(dss):
	fill(dss)
	for path in dss.catalog(condensed=True):
		record = dss.read(path)
		assert record.path.C == path.C

	flow = dss.read(dss.catalog("/A/B/FLOW/*/*/*/", condensed=True)[0])
	assert flow.values.size == 2184
