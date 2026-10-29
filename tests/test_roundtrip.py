''' write / read round trips through a dss file '''
import numpy as np
import pandas as pd
import pytest
import pyheclib as phl


def write_all(dss_file):
	records = [
		phl.RegularTs("/A/B/FLOW//1HOUR/F/", np.arange(48.0), "2020-01-31 01:00", "CFS", "INST-VAL"),
		phl.IrregularTs("/A/B/STAGE//IR-MONTH/F/", pd.to_datetime(["2020-01-01 03:00:00", "2020-02-02 04:05:06"]),
						[1.5, 2.5], "FT", "INST-VAL"),
		phl.PairedData("/A/B/STAGE-FLOW///R/", [0.0, 1.0, 2.0], [[0.0, 10.0, 40.0], [0.0, 12.0, 45.0]],
						"FT", "CFS", labels=["old", "new"]),
		phl.GriddedData("/SHG/B/PRECIP/01JAN2020:0000/01JAN2020:0100/F/", np.arange(6.0).reshape(2, 3),
						2000.0, 0.0, 0.0, "MM", "PER-CUM", grid_type="ALBERS"),
	]
	for record in records:
		dss_file.write(record)
	return records


def assert_same(written, read):
	assert type(written) is type(read)
	if isinstance(written, (phl.RegularTs, phl.IrregularTs)):
		pd.testing.assert_series_equal(written.to_series(), read.to_series(), check_freq=False)
		assert (written.unit, written.type) == (read.unit, read.type)
	elif isinstance(written, phl.PairedData):
		pd.testing.assert_frame_equal(written.to_dataframe(), read.to_dataframe())
		assert (written.x_unit, written.y_unit, written.labels) == (read.x_unit, read.y_unit, read.labels)
	else:
		np.testing.assert_allclose(written.data, read.data)
		assert (written.extent, written.unit, written.type, written.grid_type) == \
			(read.extent, read.unit, read.type, read.grid_type)


def test_all_types_persist_after_reopen(tmp_path):
	fname = str(tmp_path / "all.dss")
	with phl.open(fname) as dss_file:
		records = write_all(dss_file)

	with phl.open(fname) as dss_file:
		for record in records:
			assert_same(record, dss_file.read(record.path))


def test_record_type_codes(dss):
	write_all(dss)
	assert dss.record_type("/A/B/FLOW//1HOUR/F/") == 105
	assert dss.record_type("/A/B/FLOW/01JAN2020/1HOUR/F/") == 105
	assert dss.record_type("/A/B/STAGE//IR-MONTH/F/") == 115
	assert dss.record_type("/A/B/STAGE-FLOW///R/") == 205
	assert dss.record_type("/SHG/B/PRECIP/01JAN2020:0000/01JAN2020:0100/F/") == 420
	with pytest.raises(KeyError):
		dss.record_type("/A/B/NOTHING///R/")


def test_overwrite_regular(dss):
	path = "/A/B/FLOW//1DAY/F/"
	dss.write(phl.RegularTs(path, [1.0, 2.0, 3.0], "2020-01-02"))
	dss.write(phl.RegularTs(path, [9.0], "2020-01-03"))       # replaces the second value only
	assert dss.read(path).values.tolist() == [1.0, 9.0, 3.0]


def test_irregular_replace_and_window(dss):
	path = "/A/B/STAGE//IR-MONTH/F/"
	dss.write(phl.IrregularTs(path, pd.to_datetime(["2020-01-01", "2020-01-10", "2020-04-01"]), [1.0, 2.0, 5.0]))
	# replaces stored values within 05Jan .. 01Mar (10Jan is dropped), keeps the rest
	dss.write(phl.IrregularTs(path, pd.to_datetime(["2020-01-05", "2020-03-01"]), [3.0, 4.0]))

	out = dss.read(path)
	assert out.values.tolist() == [1.0, 3.0, 4.0, 5.0]

	window = dss.read(path, start="2020-01-04", end="2020-03-15")
	assert window.values.tolist() == [3.0, 4.0]


def test_paired_overwrite(dss):
	path = "/A/B/STAGE-FLOW///R/"
	dss.write(phl.PairedData(path, [0.0, 1.0], [0.0, 1.0]))
	dss.write(phl.PairedData(path, [0.0, 1.0, 2.0], [0.0, 2.0, 8.0], labels=["new"]))
	out = dss.read(path)
	assert out.x.tolist() == [0.0, 1.0, 2.0] and out.labels == ["new"]


@pytest.mark.parametrize("grid_type", ["UNDEFINED", "HRAP", "ALBERS", "SPECIFIED"])
@pytest.mark.parametrize("data_type", ["PER-AVER", "PER-CUM", "INST-VAL", "INST-CUM"])
def test_grid_types(dss, grid_type, data_type):
	path = "/G/B/VALUE/01JAN2020:0000/01JAN2020:0100/F/"
	dss.write(phl.GriddedData(path, np.ones((2, 3)), 1000.0, 3000.0, -2000.0, "MM", data_type, grid_type=grid_type))
	out = dss.read(path)
	assert (out.grid_type, out.type) == (grid_type, data_type)
	assert out.lower_left_cell == (3, -2)


def test_grid_nodata_and_origin(dss):
	path = "/G/B/DEPTH///F/"
	data = np.array([[np.nan, 1.0], [2.0, np.nan]])
	dss.write(phl.GriddedData(path, data, 5.0, 510.0, 1020.0, "M", origin=(500.0, 1000.0), nodata=-9999.0))
	out = dss.read(path)
	np.testing.assert_array_equal(np.isnan(out.data), np.isnan(data))
	assert out.nodata == -9999.0 and out.origin == (500.0, 1000.0)
	assert (out.xll, out.yll, out.lower_left_cell) == (510.0, 1020.0, (2, 4))


def test_all_nodata_grid(dss):
	path = "/G/B/EMPTY///F/"
	dss.write(phl.GriddedData(path, np.full((2, 2), np.nan), 1.0, 0.0, 0.0))
	assert np.isnan(dss.read(path).data).all()


def test_empty_file(dss):
	assert dss.catalog() == []
	assert dss.catalog(condensed=True) == []


def test_closed_file(tmp_path):
	dss_file = phl.open(str(tmp_path / "closed.dss"))
	dss_file.close()
	dss_file.close()                                   # closing twice is fine
	record = phl.RegularTs("/A/B/C//1DAY/F/", [1.0], "2020-01-02")
	with pytest.raises(ValueError):
		dss_file.write(record)
	with pytest.raises(ValueError):
		dss_file.read("/A/B/C//1DAY/F/")


def test_delete_then_read(dss):
	dss.write(phl.PairedData("/A/B/STAGE-FLOW///R/", [0.0, 1.0], [0.0, 1.0]))
	dss.delete("/A/B/STAGE-FLOW///R/")
	with pytest.raises(KeyError):
		dss.read("/A/B/STAGE-FLOW///R/")
	with pytest.raises(KeyError):
		dss.delete("/A/B/STAGE-FLOW///R/")
