''' package & bundled hecdss version strings '''
import os

import pyheclib as phl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_hecdss_version_matches_bundled_library():
	with open(os.path.join(ROOT, "heclib", "version.txt")) as f:
		assert f"(hecdss) {phl.__hecdss_version__} " in f.readline()
	assert phl.api_version()
