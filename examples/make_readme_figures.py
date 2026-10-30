#!/usr/bin/env python3
'''
	Generates the README figures.

	Every record type is written to a dss file, read back and the
	figure is drawn from the record that was read, so the graphs show
	real round trip data.

	    python examples/make_readme_figures.py [output_dir]

	output_dir defaults to assets/readme
'''

import os
import sys
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as font_manager
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

import pyheclib as phl


# IBM Plex like the dss browser (https://github.com/IBM/plex), matplotlib caches its
# font list, so register plex files installed after that
for font_file in font_manager.findSystemFonts():
	if os.path.basename(font_file).startswith("IBMPlex"):
		font_manager.fontManager.addfont(font_file)

# ggplot style with the IBM Plex fonts
INK, MUTED = "#222222", "#555555"
COLORS = ["#E24A33", "#348ABD", "#988ED5", "#777777", "#FBC15E", "#8EBA42"]   # the ggplot colors

plt.style.use("ggplot")
plt.rcParams.update({
	"font.family": "sans-serif",
	"font.sans-serif": ["IBM Plex Sans", "Arial", "DejaVu Sans"],
	"font.monospace": ["IBM Plex Mono", "JetBrains Mono", "Menlo", "Consolas", "DejaVu Sans Mono"],
	"font.size": 10,
	"axes.labelsize": 10,
	"legend.fontsize": 9,
	"legend.frameon": True,
	"legend.facecolor": "white",
	"figure.dpi": 100,
	"savefig.dpi": 200,
	"savefig.bbox": "tight",
	"savefig.pad_inches": 0.25,
})

FLOW_PATH = "/DEMO/OUTLET/FLOW//1HOUR/OBS/"
PRECIP_PATH = "/DEMO/GAGE/PRECIP//1DAY/OBS/"
STAGE_PATH = "/DEMO/OUTLET/STAGE//IR-MONTH/OBS/"
RATING_PATH = "/DEMO/OUTLET/STAGE-FLOW///RATING/"
GRID_PATH = "/SHG/DEMO/PRECIP/15JAN2020:0000/15JAN2020:0600/RADAR/"

SHG_WKT = ('PROJCS["USA_Contiguous_Albers_Equal_Area_Conic_USGS_version",'
	'GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",'
	'SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],'
	'UNIT["Degree",0.0174532925199433]],PROJECTION["Albers"],'
	'PARAMETER["False_Easting",0.0],PARAMETER["False_Northing",0.0],'
	'PARAMETER["Central_Meridian",-96.0],PARAMETER["Standard_Parallel_1",29.5],'
	'PARAMETER["Standard_Parallel_2",45.5],PARAMETER["Latitude_Of_Origin",23.0],'
	'UNIT["Meter",1.0]]')



''' ** example records ** '''

def example_records():
	''' one record of each type with synthetic but realistic data '''
	rng = np.random.default_rng(42)

	# daily rainfall with three storms
	days = pd.date_range("2020-01-02", "2020-04-01", freq="D")
	rain = np.where(rng.random(days.size) < 0.25, rng.gamma(1.2, 6.0, days.size), 0.0)
	for storm_day, depth in (("2020-01-15", 48.0), ("2020-02-08", 31.0), ("2020-03-03", 62.0)):
		rain[days.get_loc(pd.Timestamp(storm_day))] = depth
	precip = phl.RegularTs(PRECIP_PATH, rain, days[0], unit="MM", type="PER-CUM")

	# hourly flow responding to the rainfall, with a gauge outage
	hours = pd.date_range("2020-01-01 01:00", "2020-04-01 00:00", freq="h")
	kernel = np.exp(-np.arange(24 * 6) / 30.0) * (np.arange(24 * 6) / 12.0)
	hourly_rain = np.repeat(rain, 24)[:hours.size]
	flow_values = 40 + 0.9 * np.convolve(hourly_rain, kernel)[:hours.size] / 24
	flow_values += rng.normal(0, 0.8, hours.size)
	flow_values[(hours >= "2020-02-20") & (hours < "2020-02-23")] = np.nan
	flow = phl.RegularTs.from_series(FLOW_PATH, pd.Series(flow_values, hours), unit="CFS", type="INST-VAL")

	# manual stage readings at irregular times
	reading_times = pd.Timestamp("2020-01-01") + pd.to_timedelta(
		np.sort(rng.choice(np.arange(0, 91 * 24 * 60, 37), 45, replace=False)), unit="min")
	# stage from the 2019 rating curve, flow = 5.6 * stage^1.75
	flow_at_reading = np.interp(reading_times.asi8, hours.asi8, np.nan_to_num(flow_values, nan=40.0))
	stage_values = (flow_at_reading / 5.6) ** (1 / 1.75) + rng.normal(0, 0.02, reading_times.size)
	stage = phl.IrregularTs(STAGE_PATH, reading_times, stage_values.round(2), unit="FT", type="INST-VAL")

	# rating curves of three years
	h = np.linspace(0, 12, 49)
	rating = phl.PairedData(RATING_PATH, x=h,
		y=np.vstack([5.2 * h ** 1.80, 5.6 * h ** 1.75, 6.1 * h ** 1.70]),
		x_unit="FT", y_unit="CFS", labels=["2018", "2019", "2020"])

	# 6 hour radar precipitation over a basin on the SHG grid (2 km cells)
	ny, nx = 90, 140
	yy, xx = np.mgrid[0:ny, 0:nx]
	field = 38 * np.exp(-(((xx - 85) / 22.0) ** 2 + ((yy - 40) / 14.0) ** 2)) \
		+ 18 * np.exp(-(((xx - 40) / 15.0) ** 2 + ((yy - 60) / 18.0) ** 2)) \
		+ rng.gamma(1.0, 1.2, (ny, nx))
	outside_basin = ((xx - 70) / 68.0) ** 2 + ((yy - 45) / 44.0) ** 2 > 1
	field[outside_basin] = np.nan
	grid = phl.GriddedData(GRID_PATH, field.astype(np.float32), cell_size=2000.0,
		xll=-180000.0, yll=1320000.0, unit="MM", type="PER-CUM",
		grid_type="ALBERS", srs_wkt=SHG_WKT, srs_name="SHG", time_zone="UTC")

	return precip, flow, stage, rating, grid



''' ** figures, drawn from the records read back ** '''

def title(ax, name, path):
	''' the record type, with the dss pathname below it in a smaller mono font '''
	ax.annotate(name, (0, 1), xycoords="axes fraction", xytext=(0, 34), textcoords="offset points",
		fontsize=14, fontweight="semibold", color=INK, va="bottom")
	ax.annotate(path, (0, 1), xycoords="axes fraction", xytext=(0, 16), textcoords="offset points",
		fontsize=9, family="monospace", color=MUTED, va="bottom")


def plot_regular_ts(flow, precip, out_file):
	fig, (ax_rain, ax_flow) = plt.subplots(2, 1, figsize=(10, 5.2), sharex=True,
		gridspec_kw={"height_ratios": [1, 2.4], "hspace": 0.06})

	rain = precip.to_series()
	ax_rain.bar(rain.index - pd.Timedelta(hours=12), rain.values, width=0.85, color=COLORS[1])
	ax_rain.invert_yaxis()
	ax_rain.set_ylabel(f"Rainfall ({precip.unit})")
	title(ax_rain, "Regular time series", f"{flow.path.without_date()}  &  {precip.path.without_date()}")

	q = flow.to_series()
	ax_flow.plot(q.index, q.values, color=COLORS[0], lw=1.1, label=f"Flow, {flow.interval} {flow.type}")
	gap = q[q.isna()]
	ax_flow.axvspan(gap.index[0], gap.index[-1], color="0.6", alpha=0.35, lw=0, label="missing values (NaN)")
	ax_flow.set_ylabel(f"Flow ({flow.unit})")
	ax_flow.legend(loc="upper right")
	ax_flow.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))

	fig.savefig(out_file)
	plt.close(fig)


def plot_irregular_ts(stage, out_file):
	fig, ax = plt.subplots(figsize=(10, 3.6))

	s = stage.to_series()
	ax.plot(s.index, s.values, color=COLORS[2], lw=1, alpha=0.6)
	ax.scatter(s.index, s.values, s=30, color=COLORS[2], edgecolor="white", linewidth=1, zorder=3,
		label=f"{s.size} readings at irregular times")
	ax.set_ylabel(f"Stage ({stage.unit})")
	title(ax, "Irregular time series", stage.path.without_date())
	ax.legend(loc="upper right")
	ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))

	fig.savefig(out_file)
	plt.close(fig)


def plot_paired(rating, out_file):
	fig, ax = plt.subplots(figsize=(6.4, 4.6))

	df = rating.to_dataframe()
	for label in df.columns:
		ax.plot(df[label].values, df.index.values, lw=2, label=label)

	ax.set_xlabel(f"Flow ({rating.y_unit})")
	ax.set_ylabel(f"Stage ({rating.x_unit})")
	title(ax, "Paired data", rating.path)
	legend = ax.legend(title=f"{rating.n_curves} curves", loc="lower right")
	legend.get_title().set_color(MUTED)

	fig.savefig(out_file)
	plt.close(fig)


def plot_gridded(grid, out_file):
	fig, ax = plt.subplots(figsize=(8.4, 5))
	ax.grid(False)

	xmin, xmax, ymin, ymax = (v / 1000 for v in grid.extent)
	cmap = plt.get_cmap("viridis").copy()
	cmap.set_bad("0.85")
	image = ax.imshow(grid.data, extent=(xmin, xmax, ymin, ymax), cmap=cmap, origin="upper")

	bar = fig.colorbar(image, ax=ax, fraction=0.035, pad=0.02)
	bar.outline.set_visible(False)
	bar.set_label(f"{grid.type} ({grid.unit})")
	ax.set_xlabel(f"x ({grid.srs_name}, km)")
	ax.set_ylabel(f"y ({grid.srs_name}, km)")
	title(ax, "Gridded data", grid.path)
	ax.text(0.015, 0.975, f"{grid.shape[0]} x {grid.shape[1]} cells of {grid.cell_size / 1000:g} km\n"
		"grey = nodata (NaN)", transform=ax.transAxes, fontsize=8, va="top", color=MUTED,
		bbox={"facecolor": "white", "edgecolor": "0.7", "boxstyle": "round,pad=0.5"})

	fig.savefig(out_file)
	plt.close(fig)



def main(out_dir="assets/readme"):
	''' writes example records, reads them back & saves the figures, returns figure paths '''
	os.makedirs(out_dir, exist_ok=True)

	with tempfile.TemporaryDirectory() as tmp:
		with phl.open(os.path.join(tmp, "readme.dss")) as dss_file:

			for record in example_records():
				dss_file.write(record)

			figures = {
				"regular_ts.png": lambda f: plot_regular_ts(dss_file.read(FLOW_PATH), dss_file.read(PRECIP_PATH), f),
				"irregular_ts.png": lambda f: plot_irregular_ts(dss_file.read(STAGE_PATH), f),
				"paired_data.png": lambda f: plot_paired(dss_file.read(RATING_PATH), f),
				"gridded_data.png": lambda f: plot_gridded(dss_file.read(GRID_PATH), f),
			}

			paths = []
			for name, draw in figures.items():
				paths.append(os.path.join(out_dir, name))
				draw(paths[-1])

	return paths


if __name__ == "__main__":
	for path in main(*sys.argv[1:2]):
		print("saved", path)
