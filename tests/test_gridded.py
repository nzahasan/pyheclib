import numpy as np
import pytest
import pyheclib as phl

PATH = "/SHG/BASIN/PRECIP/01JAN2020:0000/01JAN2020:0100/TEST/"
WKT = 'PROJCS["USA_Contiguous_Albers_Equal_Area_Conic_USGS_version"]'


def test_grid_roundtrip(dss):
	rng = np.random.default_rng(1)
	data = rng.random((40, 60)).astype(np.float32) * 25
	data[:3, :5] = np.nan

	grid = phl.GriddedData(PATH, data, cell_size=2000.0, xll=-120000.0, yll=400000.0,
		unit="MM", type="PER-CUM", grid_type="ALBERS", srs_wkt=WKT, srs_name="SHG", time_zone="UTC")
	dss.write(grid)

	out = dss.read(PATH)
	assert isinstance(out, phl.GriddedData)
	np.testing.assert_array_equal(np.isnan(out.data), np.isnan(data))
	np.testing.assert_allclose(out.data, data)
	assert (out.grid_type, out.type, out.unit) == ("ALBERS", "PER-CUM", "MM")
	assert (out.cell_size, out.xll, out.yll) == (2000.0, -120000.0, 400000.0)
	assert out.lower_left_cell == (-60, 200)
	assert (out.srs_wkt, out.srs_name, out.time_zone) == (WKT, "SHG", "UTC")
	assert out.start_time == "01JAN2020:0000"
	assert out.extent == grid.extent


def test_time_invariant_grid(dss):
	path = "/UTM/BASIN/ELEVATION///DEM/"
	data = np.arange(12, dtype=float).reshape(3, 4)
	dss.write(phl.GriddedData(path, data, 30.0, 300.0, 600.0, "M"))

	out = dss.read(path)
	assert out.grid_type == "SPECIFIED"
	assert out.start_time is None
	assert dss.record_type(path) == 431
	np.testing.assert_allclose(out.data, data)


def test_misaligned_lower_left():
	with pytest.raises(ValueError):
		phl.GriddedData(PATH, np.ones((2, 2)), 10.0, 5.0, 0.0)
