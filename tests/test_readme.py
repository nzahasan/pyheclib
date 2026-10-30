''' the README code examples run and its images exist '''
import os
import re

import matplotlib
matplotlib.use("Agg")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = open(os.path.join(ROOT, "readme.md")).read()


def test_readme_examples_run(tmp_path, monkeypatch):
	# ```python blocks run, the ```py quick reference only lists signatures
	blocks = re.findall(r"```python\n(.*?)```", README, re.S)
	assert len(blocks) >= 6

	monkeypatch.chdir(tmp_path)
	namespace = {}
	for block in blocks:
		exec(compile(block, "readme.md", "exec"), namespace)

	assert os.path.exists(tmp_path / "example.dss")
	assert not namespace["dss_file"].is_open


def test_readme_images_exist():
	# images use raw github links so they also show on pypi, they must exist in the repo
	raw = "https://raw.githubusercontent.com/nzahasan/pyheclib/main/"
	images = [img for img in re.findall(r"(?:!\[[^\]]*\]\(|src=\")([^)\"]+)", README) if img.startswith(raw)]
	assert len(images) == 7
	for image in images:
		assert os.path.exists(os.path.join(ROOT, image[len(raw):])), image
