'''
	DssFile: open a dss (version 7) file, write records & read them back.

	    dss_file = pyheclib.open("example.dss")
	    dss_file.write(record)
	    record = dss_file.read(path)
	    dss_file.close()
'''

import re
import numpy as np
import pandas as pd

from . import _core
from .dsspath import DssPath
from .records import RegularTs, IrregularTs, PairedData, GriddedData


# DSS julian day 1 is 01Jan1900
DSS_EPOCH = pd.Timestamp("1899-12-31")

# -FLT_MAX marks a missing value, -901 & -902 are legacy flags
MISSING = float(np.finfo(np.float32).min)
MISSING_FLAGS = (MISSING, -901.0, -902.0)

# heclib codes
GRID_TYPE_CODES = {"UNDEFINED": 400, "HRAP": 410, "ALBERS": 420, "SPECIFIED": 430}
GRID_DATA_TYPE_CODES = {"PER-AVER": 0, "PER-CUM": 1, "INST-VAL": 2, "INST-CUM": 3, "FREQ": 4}

# record type codes, from hec_dss_recordType in hecdss.h
REGULAR_TS = (100, 105)       # float, double
IRREGULAR_TS = (110, 115)     # float, double
TIME_SERIES = REGULAR_TS + IRREGULAR_TS
PAIRED = (200, 205)           # float, double
GRID = (400, 401, 410, 411, 420, 421, 430, 431)   # grid type, +1 without time reference

# listed in hecdss.h but not supported by pyheclib
UNSUPPORTED_TYPES = {101: "regular time series pattern", 111: "irregular time series pattern", 300: "text"}

# D part of a condensed time series path, e.g. 01JAN2020-01MAR2020
DATE_RANGE = re.compile(r"\d{2}[A-Za-z]{3}\d{4}-\d{2}[A-Za-z]{3}\d{4}")


def open(filename):
	''' open (or create) a dss version 7 file '''
	return DssFile(filename)



class DssFile:

	def __init__(self, filename):
		self.filename = filename
		self._dss = _core.DssHandle(filename)

	def __repr__(self):
		state = "open" if self.is_open else "closed"
		return f"<DssFile {state} '{self.filename}'>"

	def __enter__(self):
		return self

	def __exit__(self, *exc):
		self.close()

	@property
	def is_open(self):
		return self._dss.is_open

	def close(self):
		self._dss.close()

	def version(self):
		return self._dss.version()

	def catalog(self, path_filter="", condensed=False, with_types=False):
		'''
			list of DssPath in the file, path_filter may use * wild characters.

			condensed=True combines the dated blocks of each time series into
			one path with the date range as D part (e.g. 01JAN2020-01MAR2020),
			other records are listed as they are.

			with_types=True returns (DssPath, record type code) pairs
		'''
		entries = [(DssPath(path), code) for path, code in self._dss.catalog(path_filter)]

		if condensed:
			entries = condense_catalog(entries)

		return entries if with_types else [path for path, _ in entries]

	def find(self, path):
		'''
			DssPath of stored records matching path.

			path may use * wild characters at the start or end of any part,
			e.g. /A/*/FLOW/*/*/*/ or /A/B/FL*/*/*/*/. A time series path with an
			empty D part matches all dated blocks of the series, a condensed D part
			(01JAN2020-01MAR2020) the blocks within that range.
		'''
		path = DssPath(path)

		if "*" in str(path) or (path.D and not DATE_RANGE.fullmatch(path.D)):
			return self.catalog(str(path))

		if path.D:
			first, last = pd.to_datetime(path.D.split("-"), format="%d%b%Y")

		matches = []
		for found, code in self.catalog(str(path.replace(D="*")), with_types=True):
			if code in TIME_SERIES and found.D:
				block_date = pd.to_datetime(found.D, format="%d%b%Y")
				if not path.D or first <= block_date <= last:
					matches.append(found)
			elif not found.D:
				matches.append(found)

		return matches

	def delete(self, path):
		''' delete records matching path (see find for * wild characters), returns the deleted paths '''
		matches = self.find(path)
		if not matches:
			raise KeyError(f"No record matches '{path}'")

		for found in matches:
			status = self._dss.delete(str(found))
			if status != 0:
				raise IOError(f"Unable to delete '{found}' status {status}")

		return matches

	def record_type(self, path):
		''' heclib record type code, see REGULAR_TS, IRREGULAR_TS, PAIRED & GRID '''
		path = DssPath(path)

		if path.D and not DATE_RANGE.fullmatch(path.D):
			code = self._dss.record_type(str(path))
		else:
			# empty or condensed D part: a time series data set or an undated record
			found = self._dss.catalog(str(path.replace(D="*")))
			code = found[0][1] if found else -1

		if code < 0:
			raise KeyError(f"Record '{path}' not found")
		return code


	# ** write **

	def write(self, record):
		'''
			write a RegularTs, IrregularTs, PairedData or GriddedData record.
			Existing data is replaced: time series values in the time span of
			the record, paired & gridded records completely.
		'''
		if isinstance(record, RegularTs):
			status = self._write_regular_ts(record)
		elif isinstance(record, IrregularTs):
			status = self._write_irregular_ts(record)
		elif isinstance(record, PairedData):
			status = self._write_paired(record)
		elif isinstance(record, GriddedData):
			status = self._write_gridded(record)
		else:
			raise TypeError(f"Unknown record type {type(record).__name__}")

		if status != 0:
			raise IOError(f"Failed to write '{record.path}' status {status}")

	def _write_regular_ts(self, rec):
		return self._dss.ts_store_regular(str(rec.path),
			rec.start.strftime("%d%b%Y"), rec.start.strftime("%H:%M:%S"),
			to_dss_values(rec.values), rec.unit, rec.type, rec.time_zone, rec.save_as_float)

	def _write_irregular_ts(self, rec):
		# times are stored as integer minutes (or seconds) from the first day
		base_day = rec.times[0].normalize()
		seconds = ((rec.times - base_day) // pd.Timedelta(seconds=1)).values.astype(np.int64)
		granularity = 60 if np.all(seconds % 60 == 0) else 1

		if seconds[-1] // granularity > np.iinfo(np.intc).max:
			raise ValueError("time span too long for heclib integer times")

		times = np.ascontiguousarray(seconds // granularity, dtype=np.intc)

		return self._dss.ts_store_irregular(str(rec.path), base_day.strftime("%d%b%Y"),
			times, granularity, to_dss_values(rec.values),
			rec.unit, rec.type, rec.time_zone, rec.save_as_float)

	def _write_paired(self, rec):
		return self._dss.pd_store(str(rec.path), np.ascontiguousarray(rec.x), to_dss_values(rec.y),
			rec.x_unit, rec.x_type, rec.y_unit, rec.y_type, rec.labels, rec.time_zone)

	def _write_gridded(self, rec):
		is_time_stamped = bool(rec.path.D)

		# heclib stores rows south -> north
		grid = np.flipud(rec.data)
		valid = grid[~np.isnan(grid)]

		if valid.size:
			stats = {"min": valid.min(), "max": valid.max(), "mean": valid.mean()}
			range_limits = np.linspace(stats["min"], stats["max"], 10).astype(np.float32)
			range_counts = np.array([(valid >= limit).sum() for limit in range_limits], dtype=np.intc)
		else:
			stats = {"min": rec.nodata, "max": rec.nodata, "mean": rec.nodata}
			range_limits = np.array([rec.nodata], dtype=np.float32)
			range_counts = np.zeros(1, dtype=np.intc)

		header = {
			"grid_type": GRID_TYPE_CODES[rec.grid_type] + (0 if is_time_stamped else 1),
			"data_type": GRID_DATA_TYPE_CODES[rec.type],
			"lower_left_cell": rec.lower_left_cell,
			"nx": grid.shape[1], "ny": grid.shape[0],
			"cell_size": rec.cell_size, "origin": rec.origin, "nodata": rec.nodata,
			"unit": rec.unit, "data_source": rec.data_source,
			"srs_name": rec.srs_name, "srs_wkt": rec.srs_wkt,
			"time_zone": rec.time_zone, "time_zone_offset": rec.time_zone_offset,
			"is_time_stamped": is_time_stamped,
			"is_interval": is_time_stamped and bool(rec.path.E),
			**stats,
		}

		data = np.where(np.isnan(grid), rec.nodata, grid).astype(np.float32).ravel()
		return self._dss.grid_store(str(rec.path), header, range_limits, range_counts, data)


	# ** read **

	def read(self, path, start=None, end=None):
		'''
			read a record, returns RegularTs, IrregularTs, PairedData or GriddedData.
			For time series an empty D part reads all data, start & end limit the time window.
		'''
		path = DssPath(path)
		code = self.record_type(path)

		if code in REGULAR_TS:
			return self._read_ts(path, start, end, RegularTs)
		if code in IRREGULAR_TS:
			return self._read_ts(path, start, end, IrregularTs)
		if code in PAIRED:
			return self._read_paired(path)
		if code in GRID:
			return self._read_gridded(path)

		if code in UNSUPPORTED_TYPES:
			raise ValueError(f"Record type {code} ({UNSUPPORTED_TYPES[code]}) of '{path}' is not supported")
		raise ValueError(f"Record type {code} of '{path}' is not specified in hecdss.h")

	def _read_ts(self, path, start, end, record_class):
		if (start is None) != (end is None):
			raise ValueError("both start and end are required for a time window")

		# D part is ignored, data is read by time window
		path = str(path.without_date())

		if start is None:
			first_day, first_sec, last_day, last_sec = self._dss.ts_date_range(path)
			start = DSS_EPOCH + pd.Timedelta(days=first_day, seconds=first_sec)
			end = DSS_EPOCH + pd.Timedelta(days=last_day, seconds=last_sec)
			window = None
		else:
			start, end = pd.Timestamp(start), pd.Timestamp(end)
			window = (start.strftime("%d%b%Y"), start.strftime("%H:%M:%S"),
					end.strftime("%d%b%Y"), end.strftime("%H:%M:%S"))

		size, quality_size = self._dss.ts_size(path,
			start.strftime("%d%b%Y"), start.strftime("%H:%M:%S"),
			end.strftime("%d%b%Y"), end.strftime("%H:%M:%S"))

		raw = self._dss.ts_retrieve(path, window, size, quality_size > 0)

		values = from_dss_values(raw["values"])
		times = DSS_EPOCH + pd.Timedelta(days=raw["julian_base"]) \
			+ pd.to_timedelta(raw["times"].astype(np.int64) * raw["granularity"], unit="s")
		quality = raw["quality"]

		if window is None:
			# heclib pads whole blocks with missing values, trim them
			valid = np.flatnonzero(~np.isnan(values))
			keep = slice(valid[0], valid[-1] + 1) if valid.size else slice(0, 0)
			values, times = values[keep], times[keep]
			quality = quality[keep] if quality is not None else None

		meta = {"unit": raw["unit"], "type": raw["type"] or "INST-VAL",
				"time_zone": raw["time_zone"], "quality": quality}

		if record_class is RegularTs:
			return RegularTs(path, values, times[0], **meta)
		return IrregularTs(path, times, values, **meta)

	def _read_paired(self, path):
		raw = self._dss.pd_retrieve(str(path))
		return PairedData(path, raw["x"], from_dss_values(raw["y"]),
			raw["x_unit"], raw["y_unit"], raw["x_type"], raw["y_type"],
			raw["labels"] if all(raw["labels"]) else [], raw["time_zone"])

	def _read_gridded(self, path):
		raw = self._dss.grid_retrieve(str(path))

		grid = raw["data"].reshape(raw["ny"], raw["nx"]).copy()
		grid[(grid == raw["nodata"]) | (grid == np.float32(MISSING))] = np.nan

		grid_types = {code: name for name, code in GRID_TYPE_CODES.items()}
		data_types = {code: name for name, code in GRID_DATA_TYPE_CODES.items()}

		cell_size = float(raw["cell_size"])
		origin = tuple(float(v) for v in raw["origin"])
		llx, lly = raw["lower_left_cell"]

		return GriddedData(path,
			data=np.flipud(grid),   # north-up
			cell_size=cell_size,
			xll=origin[0] + llx * cell_size,
			yll=origin[1] + lly * cell_size,
			unit=raw["unit"],
			type=data_types.get(raw["data_type"], "INST-VAL"),
			grid_type=grid_types.get(raw["grid_type"] // 10 * 10, "UNDEFINED"),
			srs_wkt=raw["srs_wkt"],
			srs_name=raw["srs_name"],
			origin=origin,
			nodata=float(raw["nodata"]),
			data_source=raw["data_source"],
			time_zone=raw["time_zone"],
			time_zone_offset=raw["time_zone_offset"])



def to_dss_values(values):
	''' NaN -> heclib missing flag, as contiguous float64 '''
	values = np.array(values, dtype=np.float64)
	values[np.isnan(values)] = MISSING
	return np.ascontiguousarray(values)


def from_dss_values(values):
	''' heclib missing flags -> NaN '''
	values = np.array(values, dtype=np.float64)
	values[np.isin(values, MISSING_FLAGS)] = np.nan
	return values


def condense_catalog(entries):
	''' combine dated blocks of time series, entries are (DssPath, code) pairs '''
	condensed = {}   # path without date -> [code, block dates], keeps catalog order

	for path, code in entries:
		if code in TIME_SERIES and path.D:
			key = path.without_date()
			condensed.setdefault(key, [code, []])[1].append(path.D)
		else:
			condensed[path] = [code, []]

	result = []
	for path, (code, dates) in condensed.items():
		if dates:
			dates = sorted(pd.to_datetime(dates, format="%d%b%Y"))
			d_part = dates[0].strftime("%d%b%Y").upper()
			if len(dates) > 1:
				d_part += "-" + dates[-1].strftime("%d%b%Y").upper()
			path = path.replace(D=d_part)
		result.append((path, code))

	return result
