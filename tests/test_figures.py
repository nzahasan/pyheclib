''' the README figure script runs and writes valid images '''
import importlib.util
import os

import numpy as np
import pyheclib as phl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_script():
	path = os.path.join(ROOT, "examples", "make_readme_figures.py")
	spec = importlib.util.spec_from_file_location("make_readme_figures", path)
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def test_figures_are_written(tmp_path):
	paths = load_script().main(str(tmp_path))

	assert [os.path.basename(p) for p in paths] == \
		["regular_ts.png", "irregular_ts.png", "paired_data.png", "gridded_data.png"]
	for path in paths:
		with open(path, "rb") as f:
			assert f.read(8) == b"\x89PNG\r\n\x1a\n"
		assert os.path.getsize(path) > 20000


def test_example_records_round_trip(dss):
	for record in load_script().example_records():
		dss.write(record)
		read = dss.read(record.path)
		assert type(read) is type(record)
		values = read.data if isinstance(read, phl.GriddedData) else (read.y if isinstance(read, phl.PairedData) else read.values)
		expected = record.data if isinstance(record, phl.GriddedData) else (record.y if isinstance(record, phl.PairedData) else record.values)
		np.testing.assert_allclose(values, expected, rtol=1e-6)
