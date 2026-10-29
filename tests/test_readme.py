''' the README code examples run and its images exist '''
import os
import re

import matplotlib
matplotlib.use("Agg")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = open(os.path.join(ROOT, "readme.md")).read()


def test_readme_examples_run(tmp_path, monkeypatch):
	blocks = re.findall(r"```python\n(.*?)```", README, re.S)
	assert len(blocks) >= 6

	monkeypatch.chdir(tmp_path)
	namespace = {}
	for block in blocks:
		exec(compile(block, "readme.md", "exec"), namespace)

	assert os.path.exists(tmp_path / "example.dss")
	assert not namespace["dss_file"].is_open


def test_readme_images_exist():
	images = [img for img in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", README) if not img.startswith("http")]
	assert len(images) == 5
	for image in images:
		assert os.path.exists(os.path.join(ROOT, image)), image
