import numpy as np
import pandas as pd
import pytest
import pyheclib as phl

PATH = "/ALPHA/BETA/STAGE-FLOW///RATING/"


def test_single_curve(dss):
	x = np.arange(0, 100, 0.1)
	y = np.sin(x)
	dss.write(phl.PairedData(PATH, x, y, x_unit="FT", y_unit="CFS"))

	out = dss.read(PATH)
	assert isinstance(out, phl.PairedData)
	assert out.n_curves == 1
	np.testing.assert_allclose(out.x, x)
	np.testing.assert_allclose(out.y[0], y)
	assert (out.x_unit, out.y_unit) == ("FT", "CFS")

	df = out.to_dataframe()
	assert df.index.name == "STAGE" and list(df.columns) == ["FLOW"]


def test_multi_curve_labels(dss):
	x = np.linspace(0, 10, 11)
	y = np.vstack([x, x ** 2, np.sqrt(x)])
	y[1, 3] = np.nan

	dss.write(phl.PairedData(PATH, x, y, "FT", "CFS", "Linear", "Log", labels=["low", "mid", "high"]))
	out = dss.read(PATH)

	np.testing.assert_allclose(out.y, y)
	assert out.labels == ["low", "mid", "high"]
	assert out.y_type == "Log"


def test_dataframe_roundtrip(dss):
	df = pd.DataFrame({"a": [1.0, 2.0, 4.0], "b": [3.0, 5.0, 7.0]}, index=[0.0, 1.0, 2.0])
	dss.write(phl.PairedData.from_dataframe(PATH, df, "FT", "CFS"))
	out = dss.read(PATH).to_dataframe()
	np.testing.assert_allclose(out.values, df.values)
	assert list(out.columns) == ["a", "b"]


def test_shape_mismatch():
	with pytest.raises(ValueError):
		phl.PairedData(PATH, np.arange(5.0), np.arange(4.0))
