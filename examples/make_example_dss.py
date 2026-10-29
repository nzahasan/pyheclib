#!/usr/bin/env python3
'''
	Creates an example dss file with every record type pyheclib supports.

	    python examples/make_example_dss.py [output.dss]

	output defaults to examples/example.dss. Records (synthetic data of a
	small basin, 2020):

	    regular ts     hourly flow (2 gauges, obs & sim), 15 minute stage,
	                   daily rainfall, monthly volume, yearly peak flow
	    irregular ts   manual stage readings, water quality samples
	    paired data    rating curves (3 years), reservoir elevation-storage
	    gridded data   6 hourly radar rainfall grids (SHG), a DEM (time invariant)
'''

import os
import sys

import numpy as np
import pandas as pd

# run from a clone without installing: use the repo's in-place build
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.isfile(os.path.join(REPO, "pyheclib", "__init__.py")):
	sys.path.insert(0, REPO)

import pyheclib as phl


SHG_WKT = ('PROJCS["USA_Contiguous_Albers_Equal_Area_Conic_USGS_version",'
	'GEOGCS["GCS_North_American_1983",DATUM["D_North_American_1983",'
	'SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],'
	'UNIT["Degree",0.0174532925199433]],PROJECTION["Albers"],'
	'PARAMETER["False_Easting",0.0],PARAMETER["False_Northing",0.0],'
	'PARAMETER["Central_Meridian",-96.0],PARAMETER["Standard_Parallel_1",29.5],'
	'PARAMETER["Standard_Parallel_2",45.5],PARAMETER["Latitude_Of_Origin",23.0],'
	'UNIT["Meter",1.0]]')

rng = np.random.default_rng(2020)



def rainfall():
	''' daily rainfall of 2020 with a few large storms '''
	days = pd.date_range("2020-01-02", "2021-01-01", freq="D")    # PER-CUM, value at end of day
	rain = np.where(rng.random(days.size) < 0.22, rng.gamma(1.1, 7.0, days.size), 0.0)
	for day, depth in (("2020-01-15", 48.0), ("2020-03-03", 62.0), ("2020-06-20", 85.0), ("2020-10-11", 54.0)):
		rain[days.get_loc(pd.Timestamp(day))] = depth
	return pd.Series(rain.round(1), index=days)


def flow_response(rain, base, scale):
	''' hourly flow from daily rainfall with a simple unit hydrograph '''
	hours = pd.date_range("2020-01-01 01:00", "2021-01-01 00:00", freq="h")
	hourly_rain = np.repeat(rain.values, 24)[:hours.size] / 24
	kernel = np.exp(-np.arange(240) / 40.0) * (np.arange(240) / 15.0)
	seasonal = base * (1 + 0.3 * np.sin(2 * np.pi * (hours.dayofyear - 60) / 366))
	flow = seasonal + scale * np.convolve(hourly_rain, kernel)[:hours.size]
	return pd.Series(flow + rng.normal(0, base * 0.01, hours.size), index=hours)


def stage_from_flow(flow):
	''' 2020 rating: flow = 6.1 * stage^1.7 '''
	return (flow / 6.1) ** (1 / 1.7)


def regular_ts(rain):
	records = [phl.RegularTs("/DEMO/GAGE1/PRECIP//1DAY/OBS/", rain.values, rain.index[0], "MM", "PER-CUM")]

	for gauge, base, scale in (("OUTLET", 40.0, 2.2), ("UPSTREAM", 18.0, 1.1)):
		obs = flow_response(rain, base, scale)
		obs[(obs.index >= "2020-08-03") & (obs.index < "2020-08-06")] = np.nan     # gauge outage
		sim = flow_response(rain, base, scale * 0.92)
		records.append(phl.RegularTs.from_series(f"/DEMO/{gauge}/FLOW//1HOUR/OBS/", obs.round(2), "CFS", "INST-VAL"))
		records.append(phl.RegularTs.from_series(f"/DEMO/{gauge}/FLOW//1HOUR/SIM/", sim.round(2), "CFS", "INST-VAL"))

	# 15 minute stage at the outlet for the June storm
	quarter = pd.date_range("2020-06-15", "2020-06-30 23:45", freq="15min")
	flow = flow_response(rain, 40.0, 2.2).reindex(quarter, method="nearest")
	records.append(phl.RegularTs.from_series("/DEMO/OUTLET/STAGE//15MINUTE/OBS/",
		stage_from_flow(flow).round(3), "FT", "INST-VAL"))

	# monthly runoff volume & yearly peak flow
	hourly = flow_response(rain, 40.0, 2.2)
	volume = hourly[:"2020-12-31 23:00"].resample("MS").sum() * 3600 / 43560   # cfs-hours -> acre-feet
	# monthly values are stamped at the end of the month, 31JAN2020 2400 = 01FEB2020 0000
	records.append(phl.RegularTs("/DEMO/OUTLET/VOLUME//1MONTH/OBS/", volume.values.round(1),
		"2020-02-01 00:00", "AC-FT", "PER-CUM"))
	records.append(phl.RegularTs("/DEMO/OUTLET/FLOW-PEAK//1YEAR/OBS/", [hourly.max().round(1)],
		"2020-12-31 00:00", "CFS", "INST-VAL"))
	return records


def irregular_ts(rain):
	flow = flow_response(rain, 40.0, 2.2)

	# manual stage readings, a few per week
	minutes = np.sort(rng.choice(np.arange(0, 366 * 24 * 60, 13), 140, replace=False))
	times = pd.Timestamp("2020-01-01") + pd.to_timedelta(minutes, unit="min")
	stage = stage_from_flow(flow.reindex(times, method="nearest")).values + rng.normal(0, 0.02, times.size)

	# water quality samples at seconds resolution
	sample_times = pd.Timestamp("2020-01-01") + pd.to_timedelta(
		np.sort(rng.choice(np.arange(0, 366 * 86400, 17), 36, replace=False)), unit="s")
	temperature = 12 + 9 * np.sin(2 * np.pi * (sample_times.dayofyear.to_numpy() - 110) / 366) + rng.normal(0, 0.4, sample_times.size)

	return [
		phl.IrregularTs("/DEMO/OUTLET/STAGE//IR-MONTH/MANUAL/", times, stage.round(2), "FT", "INST-VAL"),
		phl.IrregularTs("/DEMO/OUTLET/TEMP-WATER//IR-YEAR/SAMPLE/", sample_times, temperature.round(1), "DEG C", "INST-VAL"),
	]


def paired_data():
	h = np.linspace(0, 12, 49)
	elevation = np.arange(100.0, 131.0, 2.0)
	return [
		phl.PairedData("/DEMO/OUTLET/STAGE-FLOW///RATING/", h,
			np.vstack([5.2 * h ** 1.80, 5.6 * h ** 1.75, 6.1 * h ** 1.70]).round(2),
			"FT", "CFS", labels=["2018", "2019", "2020"]),
		phl.PairedData("/DEMO/RESERVOIR/ELEVATION-STORAGE///TABLE/", elevation,
			(2.4 * (elevation - 100) ** 2.1).round(1), "FT", "AC-FT"),
	]


def gridded_data():
	ny, nx = 90, 140
	yy, xx = np.mgrid[0:ny, 0:nx]
	outside_basin = ((xx - 70) / 68.0) ** 2 + ((yy - 45) / 44.0) ** 2 > 1
	records = []

	# a storm cell crossing the basin, one grid per hour
	start = pd.Timestamp("2020-06-20 00:00")
	for hour in range(6):
		cx, cy = 25 + hour * 18, 60 - hour * 4
		field = 22 * np.exp(-(((xx - cx) / 20.0) ** 2 + ((yy - cy) / 13.0) ** 2)) + rng.gamma(0.8, 0.5, (ny, nx))
		field[outside_basin] = np.nan
		t0, t1 = start + pd.Timedelta(hours=hour), start + pd.Timedelta(hours=hour + 1)
		# DSS grid times use 2400 for midnight at the end of a day
		path = f"/SHG/DEMO/PRECIP/{t0:%d%b%Y:%H%M}/{t1:%d%b%Y:%H%M}/RADAR/".upper()
		records.append(phl.GriddedData(path, field.astype(np.float32), 2000.0, -180000.0, 1320000.0,
			"MM", "PER-CUM", grid_type="ALBERS", srs_wkt=SHG_WKT, srs_name="SHG", time_zone="UTC"))

	# time invariant terrain on the same grid
	dem = 250 + 0.6 * (ny - yy) + 25 * np.sin(xx / 12.0) * np.cos(yy / 15.0) + rng.normal(0, 0.8, (ny, nx))
	dem[outside_basin] = np.nan
	records.append(phl.GriddedData("/SHG/DEMO/ELEVATION///DEM/", dem.astype(np.float32), 2000.0,
		-180000.0, 1320000.0, "M", "INST-VAL", grid_type="ALBERS", srs_wkt=SHG_WKT, srs_name="SHG"))
	return records



def main(filename=os.path.join(REPO, "examples", "example.dss")):
	if os.path.exists(filename):
		os.remove(filename)

	rain = rainfall()
	records = regular_ts(rain) + irregular_ts(rain) + paired_data() + gridded_data()

	with phl.open(filename) as dss_file:
		for record in records:
			dss_file.write(record)

		for path, code in dss_file.catalog(condensed=True, with_types=True):
			print(f"{code:4d}  {path}")

	print(f"\n{len(records)} records written to {filename}")
	return filename


if __name__ == "__main__":
	main(*sys.argv[1:2])
