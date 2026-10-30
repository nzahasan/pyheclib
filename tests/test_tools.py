''' command line tools in pyheclib/tools '''
import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pyheclib as phl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_tool(name, *args):
	env = {**os.environ, "PYTHONPATH": ROOT}
	result = subprocess.run([sys.executable, "-m", f"pyheclib.tools.{name}", *args],
		capture_output=True, text=True, env=env, check=True)
	return result.stdout


def make_file(tmp_path):
	fname = str(tmp_path / "tools.dss")
	with phl.open(fname) as dss_file:
		dss_file.write(phl.RegularTs("/A/B/FLOW//1HOUR/F/", np.arange(800.0), "2020-01-01 01:00", "CFS"))
		dss_file.write(phl.PairedData("/A/B/STAGE-FLOW///R/", [0.0, 1.0], [[0.0, 5.0]], "FT", "CFS", labels=["c1"]))
		dss_file.write(phl.GriddedData("/A/B/DEM///F/", np.arange(4.0).reshape(2, 2), 1.0, 0.0, 0.0))
	return fname


def test_catalog_tool(tmp_path):
	fname = make_file(tmp_path)
	full = run_tool("dss_catalog", fname)
	condensed = run_tool("dss_catalog", fname, "--condensed")

	assert "01Feb2020" in full and len(full.splitlines()) == 4
	assert "/A/B/FLOW/01JAN2020-01FEB2020/1Hour/F/" in condensed and len(condensed.splitlines()) == 3
	assert len(run_tool("dss_catalog", fname, "/A/B/STAGE*/*/*/*/").splitlines()) == 1


def test_csv_tool(tmp_path):
	fname = make_file(tmp_path)
	out = tmp_path / "out.csv"

	run_tool("dssrec2csv", fname, "/A/B/FLOW//1HOUR/F/", str(out))
	ts = pd.read_csv(out, index_col=0, parse_dates=True)
	assert ts.shape == (800, 1) and ts.iloc[-1, 0] == 799.0

	run_tool("dssrec2csv", fname, "/A/B/STAGE-FLOW///R/", str(out))
	assert pd.read_csv(out, index_col=0).columns.tolist() == ["c1"]

	run_tool("dssrec2csv", fname, "/A/B/DEM///F/", str(out))
	np.testing.assert_allclose(np.loadtxt(out, delimiter=","), np.arange(4.0).reshape(2, 2))
