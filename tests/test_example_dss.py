''' examples/make_example_dss.py creates a file with every record type '''
import importlib.util
import os

import numpy as np
import pandas as pd
import pyheclib as phl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_script():
	spec = importlib.util.spec_from_file_location("make_example_dss", os.path.join(ROOT, "examples", "make_example_dss.py"))
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def test_example_file(tmp_path):
	script = load_script()
	fname = script.main(str(tmp_path / "example.dss"))

	with phl.open(fname) as dss_file:
		codes = [code for _, code in dss_file.catalog(condensed=True, with_types=True)]
		assert codes.count(105) == 8 and codes.count(115) == 2
		assert codes.count(205) == 2 and codes.count(420) == 6 and codes.count(421) == 1

		# every record reads back as the record type it was written with
		for path in dss_file.catalog(condensed=True):
			record = dss_file.read(path)
			assert record.path.C == path.C

		flow = dss_file.read("/DEMO/OUTLET/FLOW//1HOUR/OBS/").to_series()
		assert flow.index[0] == pd.Timestamp("2020-01-01 01:00") and flow.size == 366 * 24
		assert flow.isna().sum() == 72

		volume = dss_file.read("/DEMO/OUTLET/VOLUME//1MONTH/OBS/")
		assert volume.values.size == 12
		assert volume.times[0] == pd.Timestamp("2020-02-01") and volume.times[-1] == pd.Timestamp("2021-01-01")

		grids = [dss_file.read(path) for path in dss_file.find("/SHG/DEMO/PRECIP/*/*/RADAR/")]
		assert len(grids) == 6 and all(g.shape == (90, 140) and g.grid_type == "ALBERS" for g in grids)
		assert np.isnan(grids[0].data).any()

		assert dss_file.read("/DEMO/OUTLET/STAGE-FLOW///RATING/").labels == ["2018", "2019", "2020"]
		assert dss_file.read("/SHG/DEMO/ELEVATION///DEM/").start_time is None
