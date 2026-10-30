''' pyheclib/tools/dss_browser.py web server '''
import os
import threading
import urllib.error
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd
import pytest
import pyheclib as phl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FLOW = "/A/GAGE/FLOW//1HOUR/OBS/"
STAGE = "/A/GAGE/STAGE//IR-MONTH/OBS/"
RATING = "/A/GAGE/STAGE-FLOW///RATING/"
GRID = "/SHG/A/PRECIP/01JAN2020:0000/01JAN2020:0100/RADAR/"


def load_tool():
	from pyheclib.tools import dss_browser
	return dss_browser


@pytest.fixture(scope="module")
def server(tmp_path_factory):
	fname = str(tmp_path_factory.mktemp("browser") / "browser.dss")
	with phl.open(fname) as dss_file:
		hours = pd.date_range("2020-01-01 01:00", "2020-03-01 00:00", freq="h")
		flow = pd.Series(np.sin(np.arange(hours.size) / 30.0), hours)
		flow.iloc[100:110] = np.nan
		dss_file.write(phl.RegularTs.from_series(FLOW, flow, "CFS"))
		dss_file.write(phl.IrregularTs(STAGE, pd.to_datetime(["2020-01-01 03:00:00", "2020-01-02 04:05:06"]), [1.0, 2.0], "FT"))
		dss_file.write(phl.PairedData(RATING, [0.0, 1.0, 2.0], [[0.0, 5.0, 20.0], [0.0, 6.0, 22.0]], "FT", "CFS", labels=["a", "b"]))
		grid = np.arange(12.0).reshape(3, 4)
		grid[0, 0] = np.nan
		dss_file.write(phl.GriddedData(GRID, grid, 2000.0, 0.0, 0.0, "MM", "PER-CUM", grid_type="ALBERS"))

	httpd = load_tool().make_server([fname], port=0)
	thread = threading.Thread(target=httpd.serve_forever, daemon=True)
	thread.start()
	yield f"http://127.0.0.1:{httpd.server_address[1]}"
	httpd.shutdown()
	httpd.workspace.close_all()


def get(server, url, **query):
	query.setdefault("file", "1")
	full = server + url + "?" + urllib.parse.urlencode(query)
	with urllib.request.urlopen(full) as response:
		return response.status, response.headers["Content-Type"], response.read()


def post(server, url, body=b"", **query):
	request = urllib.request.Request(server + url + "?" + urllib.parse.urlencode(query), data=body, method="POST")
	with urllib.request.urlopen(request) as response:
		return response.status, response.read()


def test_page(server):
	status, content_type, body = get(server, "/")
	assert status == 200 and content_type.startswith("text/html")
	assert b"htmx.org" in body and b'hx-get="/catalog"' in body and b"--background" in body
	assert b"IBM+Plex+Sans" in body and b"IBM+Plex+Mono" in body
	assert b'id="offline"' in body and b'fetch("/ping"' in body
	assert b"h-screen" in body and b"overflow-hidden" in body
	assert b'name="file" value="1"' in body and b'href="/?file=1"' in body and b"browser.dss" in body
	assert b'id="picker"' in body and b'"drop"' in body
	assert b'role="listbox"' in body and b'name="kind" value=""' in body and b"<select" not in body


def test_page_with_record(server):
	_, _, body = get(server, "/", path=RATING)
	assert b"PairedData" in body and b"Select a record" not in body
	assert b'hx-push-url="/?file=1&path=' in get(server, "/catalog")[2]


def test_unknown_file(server):
	_, _, body = get(server, "/", file="99")                 # falls back to the first file
	assert b'name="file" value="1"' in body
	with pytest.raises(urllib.error.HTTPError) as error:
		get(server, "/catalog", file="99")
	assert error.value.code == 404


def test_open_and_close(server, tmp_path):
	fname = str(tmp_path / "other.dss")
	with phl.open(fname) as dss_file:
		dss_file.write(phl.IrregularTs(STAGE, pd.to_datetime(["2020-01-01 03:00:00"]), [1.0], "FT"))
	with open(fname, "rb") as f:
		status, body = post(server, "/open", f.read(), name="other.dss")
	file_id = body.decode()
	assert status == 200 and file_id != "1"

	_, _, page = get(server, "/", file=file_id)
	assert b"other.dss" in page and b"browser.dss" in page
	assert "1</span> records" in get(server, "/catalog", file=file_id)[2].decode()

	assert post(server, "/close", file=file_id) == (200, b"ok")
	with pytest.raises(urllib.error.HTTPError):
		get(server, "/catalog", file=file_id)


def test_open_not_dss(server):
	with pytest.raises(urllib.error.HTTPError) as error:
		post(server, "/open", b"not a dss file", name="bad.dss")
	assert error.value.code == 400


def test_no_file_page():
	httpd = load_tool().make_server(port=0)
	thread = threading.Thread(target=httpd.serve_forever, daemon=True)
	thread.start()
	try:
		_, _, body = get(f"http://127.0.0.1:{httpd.server_address[1]}", "/")
		assert b"No file open" in body and b'hx-get="/catalog"' not in body
	finally:
		httpd.shutdown()


def test_ping(server):
	assert get(server, "/ping")[2] == b"ok"


def test_catalog_filters(server):
	_, _, body = get(server, "/catalog")
	text = body.decode()
	assert "4</span> records" in text and "/A/GAGE/FLOW/01JAN2020-01FEB2020/1Hour/OBS/" in text   # always condensed
	page = get(server, "/")[2].decode()
	assert 'name="condensed"' not in page and 'name="part_' not in page

	count = lambda **query: get(server, "/catalog", **query)[2].decode()
	assert "1</span> records" in count(kind="grid")
	assert "1</span> records" in count(search="rating")
	assert "3</span> records" in count(search="/a/gage/")                  # pathname text
	assert "2</span> records" in count(search="C=STAGE*")                  # wild characters: whole part
	assert "2</span> records" in count(search="c=tag")                     # no wild characters: partial
	assert "1</span> records" in count(search="b=gage c=stage f=obs")      # all words must match
	assert "1</span> records" in count(search="C=STAGE /OBS/")
	assert "No records match" in count(search="A=NONE")


@pytest.mark.parametrize("path, expected", [
	(FLOW, ["RegularTs", "<svg", "<polyline", "1HOUR", "Missing"]),
	(STAGE, ["IrregularTs", "<circle", "2020-01-02 04:05:06"]),
	(RATING, ["PairedData", "<polyline", "a, b", "FLOW (CFS)"]),
	(GRID, ["GriddedData", "/grid.png?file=1&path=", "ALBERS", "3 x 4"]),
])
def test_record_views(server, path, expected):
	status, _, body = get(server, "/record", path=path)
	text = body.decode()
	assert status == 200
	has_tabs = 'data-tab="Graph"' in text and 'data-panel="Table"' in text and "<table" in text
	assert has_tabs == (path != GRID)                       # grids only show the image
	for item in expected:
		assert item in text, item


def test_missing_record(server):
	status, _, body = get(server, "/record", path="/NO/SUCH/RECORD///X/")
	assert status == 200 and b"Unable to read record" in body


def test_grid_png(server):
	status, content_type, body = get(server, "/grid.png", path=GRID)
	assert status == 200 and content_type == "image/png"
	assert body[:8] == b"\x89PNG\r\n\x1a\n" and b"IHDR" in body and b"IEND" in body


def test_csv_download(server):
	_, content_type, body = get(server, "/csv", path=RATING)
	assert content_type == "text/csv"
	assert body.decode().splitlines()[0] == "STAGE,a,b"

	lines = get(server, "/csv", path=FLOW)[2].decode().splitlines()
	assert lines[0] == "Time,FLOW" and len(lines) == 1441

	assert len(get(server, "/csv", path=GRID)[2].decode().splitlines()) == 3


def test_unknown_url(server):
	with pytest.raises(urllib.error.HTTPError) as error:
		get(server, "/nothing")
	assert error.value.code == 404


def test_chart_helpers():
	tool = load_tool()
	assert tool.nice_ticks(0, 10) == [0, 2, 4, 6, 8, 10]

	x = np.arange(10000.0)
	y = np.sin(x / 100)
	y[5000] = 50.0                                         # spike must survive decimation
	dx, dy = tool.decimate(x, y)
	assert dx.size <= tool.MAX_CHART_POINTS and dy.max() == 50.0

	png = tool.grid_png(np.full((2, 2), np.nan))
	assert png[:8] == b"\x89PNG\r\n\x1a\n"
