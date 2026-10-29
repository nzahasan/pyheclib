''' delete & find with * wild characters '''
import numpy as np
import pandas as pd
import pytest
import pyheclib as phl


def fill(dss):
	hours = pd.date_range("2020-01-01 01:00", "2020-04-01 00:00", freq="h")     # Jan .. Mar blocks
	series = pd.Series(np.arange(hours.size, dtype=float), hours)
	for basin in ("NORTH", "SOUTH"):
		dss.write(phl.RegularTs.from_series(f"/{basin}/GAGE1/FLOW//1HOUR/OBS/", series))
		dss.write(phl.RegularTs.from_series(f"/{basin}/GAGE1/FLOW//1HOUR/SIM/", series))
		dss.write(phl.RegularTs.from_series(f"/{basin}/GAGE2/STAGE//1HOUR/OBS/", series))
		dss.write(phl.PairedData(f"/{basin}/GAGE1/STAGE-FLOW///RATING/", [0.0, 1.0], [0.0, 5.0]))
	dss.write(phl.GriddedData("/SHG/NORTH/PRECIP/01JAN2020:0000/01JAN2020:0100/RADAR/", np.ones((2, 2)), 1.0, 0.0, 0.0))


def test_find(dss):
	fill(dss)
	assert len(dss.find("/NORTH/*/*/*/*/*/")) == 10                            # 3 series x 3 blocks + rating
	assert len(dss.find("/*/GAGE1/FLOW/*/*/OBS/")) == 6
	assert dss.find("/NORTH/GAGE1/STAGE-FLOW///RATING/") == ["/NORTH/GAGE1/STAGE-FLOW///RATING/"]
	assert dss.find("/NORTH/GAGE1/FLOW/01FEB2020/1HOUR/OBS/") == ["/NORTH/GAGE1/FLOW/01Feb2020/1Hour/OBS/"]
	assert len(dss.find("/NORTH/GAGE1/FLOW//1HOUR/OBS/")) == 3                  # all blocks of the series
	assert len(dss.find("/NORTH/GAGE1/FLOW/01FEB2020-01MAR2020/1HOUR/OBS/")) == 2
	assert len(dss.find("/*/*/*/*/*/RAD*/")) == 1                               # partial part match
	assert dss.find("/NOWHERE/*/*/*/*/*/") == []


def test_delete_wildcard(dss):
	fill(dss)
	deleted = dss.delete("/SOUTH/*/*/*/*/*/")
	assert len(deleted) == 10
	assert all(path.A == "SOUTH" for path in deleted)
	assert dss.find("/SOUTH/*/*/*/*/*/") == []
	assert len(dss.find("/NORTH/*/*/*/*/*/")) == 10


def test_delete_parts_and_suffix(dss):
	fill(dss)
	dss.delete("/*/*/FLOW/*/*/SIM/")
	assert dss.find("/*/*/*/*/*/SIM/") == []
	assert len(dss.find("/*/*/FLOW/*/*/OBS/")) == 6

	dss.delete("/*/*/STAGE*/*/*/*/")                                           # STAGE & STAGE-FLOW
	assert {path.C for path in dss.catalog()} == {"FLOW", "PRECIP"}


def test_delete_time_series(dss):
	fill(dss)
	path = "/NORTH/GAGE1/FLOW//1HOUR/OBS/"

	dss.delete("/NORTH/GAGE1/FLOW/01JAN2020-01FEB2020/1HOUR/OBS/")             # condensed range
	assert dss.read(path).start == pd.Timestamp("2020-03-01 01:00")

	dss.delete(path)                                                            # whole series
	with pytest.raises(KeyError):
		dss.read(path)
	assert len(dss.find("/NORTH/GAGE1/FLOW//1HOUR/SIM/")) == 3                 # other series untouched


def test_delete_single_records(dss):
	fill(dss)
	assert dss.delete("/NORTH/GAGE1/STAGE-FLOW///RATING/") == ["/NORTH/GAGE1/STAGE-FLOW///RATING/"]
	dss.delete("/SHG/NORTH/PRECIP/01JAN2020:0000/01JAN2020:0100/RADAR/")
	assert dss.find("/SHG/*/*/*/*/*/") == []
	assert dss.find("/SOUTH/GAGE1/STAGE-FLOW///RATING/") != []


def test_delete_nothing_matches(dss):
	fill(dss)
	with pytest.raises(KeyError):
		dss.delete("/NOWHERE/*/*/*/*/*/")
