import pytest
import pyheclib as phl


@pytest.fixture
def dss(tmp_path):
	dss_file = phl.open(str(tmp_path / "test.dss"))
	yield dss_file
	dss_file.close()
