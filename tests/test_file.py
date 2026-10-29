import numpy as np
import pytest
import pyheclib as phl

DAILY = "/A/B/FLOW//1DAY/F/"


def test_open_close_context(tmp_path):
	fname = str(tmp_path / "ctx.dss")
	with phl.open(fname) as dss_file:
		assert dss_file.version() == 7 and dss_file.is_open
		dss_file.write(phl.RegularTs(DAILY, np.arange(3.0), "2020-01-02", "cfs", "PER-AVER"))
	assert not dss_file.is_open
	with pytest.raises(ValueError):
		dss_file.catalog()

	# reopen existing file
	with phl.open(fname) as dss_file:
		assert dss_file.catalog() == ["/A/B/FLOW/01Jan2020/1Day/F/"]


def test_catalog_delete_missing(dss):
	dss.write(phl.RegularTs(DAILY, np.arange(3.0), "2020-01-02", "cfs", "PER-AVER"))
	dss.write(phl.PairedData("/A/B/STAGE-FLOW///R/", [1.0, 2.0], [3.0, 4.0], "FT", "CFS"))

	assert {str(path): code for path, code in dss.catalog(with_types=True)} == {
		"/A/B/FLOW/01Jan2020/1Day/F/": 105, "/A/B/STAGE-FLOW///R/": 205}
	assert dss.catalog("/A/B/STAGE*/*/*/*/") == ["/A/B/STAGE-FLOW///R/"]

	dss.delete("/A/B/STAGE-FLOW///R/")
	assert dss.catalog() == ["/A/B/FLOW/01Jan2020/1Day/F/"]

	with pytest.raises(KeyError):
		dss.read("/A/B/MISSING//1DAY/F/")


def test_write_unknown_type(dss):
	with pytest.raises(TypeError):
		dss.write(np.arange(3))


def test_reject_non_dss_file(tmp_path):
	fname = tmp_path / "not.dss"
	fname.write_bytes(b"\0" * 4096)
	with pytest.raises((ValueError, IOError)):
		phl.open(str(fname))
