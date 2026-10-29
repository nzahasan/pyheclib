import pytest
import pyheclib as phl
from pyheclib import DssPath


def test_parts():
	path = DssPath("/BASIN/GAGE/FLOW/01JAN2020/1HOUR/OBS/")
	assert (path.A, path.B, path.C, path.D, path.E, path.F) == ("BASIN", "GAGE", "FLOW", "01JAN2020", "1HOUR", "OBS")
	assert path.parts() == {"A": "BASIN", "B": "GAGE", "C": "FLOW", "D": "01JAN2020", "E": "1HOUR", "F": "OBS"}
	assert str(path) == "/BASIN/GAGE/FLOW/01JAN2020/1HOUR/OBS/"
	assert repr(path) == "DssPath('/BASIN/GAGE/FLOW/01JAN2020/1HOUR/OBS/')"


def test_from_parts_replace_without_date():
	path = DssPath.from_parts(A="BASIN", C="STAGE-FLOW", F="RATING")
	assert str(path) == "/BASIN//STAGE-FLOW///RATING/"

	ts = DssPath("/BASIN/GAGE/FLOW/01JAN2020/1HOUR/OBS/")
	assert str(ts.replace(F="SIM", B="OUTLET")) == "/BASIN/OUTLET/FLOW/01JAN2020/1HOUR/SIM/"
	assert str(ts.without_date()) == "/BASIN/GAGE/FLOW//1HOUR/OBS/"
	assert ts.D == "01JAN2020"   # unchanged, paths are immutable

	with pytest.raises(ValueError):
		ts.replace(G="x")
	with pytest.raises(AttributeError):
		ts.A = "OTHER"


def test_equality_is_case_insensitive():
	path = DssPath("/Basin/Gage/Flow//1Hour/Obs/")
	assert path == "/BASIN/GAGE/FLOW//1HOUR/OBS/"
	assert path == DssPath("/basin/gage/flow//1hour/obs/")
	assert len({path, DssPath("/BASIN/GAGE/FLOW//1HOUR/OBS/")}) == 1
	assert path != DssPath("/BASIN/GAGE/FLOW//1HOUR/SIM/")


@pytest.mark.parametrize("bad", ["", "/A/B/C/", "A/B/C/D/E/F/", "/A/B/C/D/E/F", "/" + "x" * 65 + "/B/C/D/E/F/"])
def test_invalid(bad):
	with pytest.raises(ValueError):
		DssPath(bad)


def test_records_accept_dsspath(dss):
	path = DssPath.from_parts("A", "B", "FLOW", "", "1DAY", "F")
	rts = phl.RegularTs(path, [1.0, 2.0], "2020-01-02")
	assert isinstance(rts.path, DssPath) and rts.path.C == "FLOW"

	dss.write(rts)
	out = dss.read(path)
	assert out.path == path and out.values.tolist() == [1.0, 2.0]
