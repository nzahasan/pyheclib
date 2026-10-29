''' the example notebooks run without errors '''
import glob
import os

import pytest

nbformat = pytest.importorskip("nbformat")
nbclient = pytest.importorskip("nbclient")
pytest.importorskip("ipykernel")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOTEBOOKS = sorted(glob.glob(os.path.join(ROOT, "notebooks", "*.ipynb")))


def test_notebooks_exist():
	assert [os.path.basename(nb) for nb in NOTEBOOKS] == [
		"01_regular_timeseries.ipynb", "02_irregular_timeseries.ipynb", "03_paired_data.ipynb",
		"04_gridded_data.ipynb", "05_catalog_paths_delete.ipynb"]


@pytest.mark.parametrize("notebook", NOTEBOOKS, ids=os.path.basename)
def test_notebook_runs(notebook, tmp_path):
	nb = nbformat.read(notebook, as_version=4)
	# run in a copy of the notebooks folder layout so dss files land in tmp_path
	work_dir = tmp_path / "notebooks"
	work_dir.mkdir()
	os.symlink(os.path.join(ROOT, "pyheclib"), tmp_path / "pyheclib")
	nbclient.NotebookClient(nb, timeout=300, kernel_name="python3",
		resources={"metadata": {"path": str(work_dir)}}).execute()

	last_output = "".join(o.get("text", "") for o in nb.cells[-1].outputs)
	assert "all checks passed" in last_output
