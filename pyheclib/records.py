'''
	Record types of a dss file.

	A record holds its pathname, data and all metadata. Records are created
	independently of a file and written with DssFile.write(record);
	DssFile.read(path) returns the same record types.
'''

from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np
import pandas as pd

from .dsspath import DssPath


DATA_TYPES = ("INST-VAL", "INST-CUM", "PER-AVER", "PER-CUM", "FREQ")
GRID_TYPES = ("UNDEFINED", "HRAP", "ALBERS", "SPECIFIED")


def check_type(data_type):
	data_type = data_type.upper()
	if data_type not in DATA_TYPES:
		raise ValueError(f"type must be one of {DATA_TYPES}")
	return data_type


def as_1d(values, name):
	values = np.asarray(values, dtype=np.float64)
	if values.ndim != 1 or values.size == 0:
		raise ValueError(f"{name} must be a non empty one dimensional array")
	return values


# the regular intervals (E part) heclib accepts
REGULAR_INTERVALS = {
	**{f"{n}SECOND": pd.Timedelta(seconds=n) for n in (1, 2, 3, 4, 5, 6, 10, 15, 20, 30)},
	**{f"{n}MINUTE": pd.Timedelta(minutes=n) for n in (1, 2, 3, 4, 5, 6, 10, 12, 15, 20, 30)},
	**{f"{n}HOUR": pd.Timedelta(hours=n) for n in (1, 2, 3, 4, 6, 8, 12)},
	"1DAY": pd.Timedelta(days=1),
	"1WEEK": pd.Timedelta(weeks=1),
	"1MONTH": pd.DateOffset(months=1),
	"1YEAR": pd.DateOffset(years=1),
}

# periods of these intervals start on fixed days of each month
MONTH_SPLITS = {"SEMI-MONTH": (1, 16), "TRI-MONTH": (1, 11, 21)}


def check_regular_interval(e_part):
	if e_part.upper() not in REGULAR_INTERVALS and e_part.upper() not in MONTH_SPLITS:
		raise ValueError(f"Unsupported regular interval '{e_part}', use one of "
			f"{', '.join(list(REGULAR_INTERVALS) + list(MONTH_SPLITS))}")


def check_irregular_interval(e_part):
	if not e_part.upper().startswith(("IR-", "~")):
		raise ValueError(f"Irregular E part must start with IR- or ~ (e.g. IR-MONTH), got '{e_part}'")


def interval_offset(e_part):
	''' regular interval E part (e.g. 15MINUTE, 1HOUR, 1MONTH) -> pandas offset '''
	check_regular_interval(e_part)
	if e_part.upper() in MONTH_SPLITS:
		raise ValueError(f"'{e_part}' has no fixed offset, periods start on fixed days of each month")
	return REGULAR_INTERVALS[e_part.upper()]


def regular_times(start, e_part, periods):
	''' times of a regular series, start is the first time '''
	days = MONTH_SPLITS.get(e_part.upper())
	if days is None:
		return pd.date_range(start, periods=periods, freq=interval_offset(e_part), name="Time")

	# period start days of enough months from the month before start
	months = pd.date_range(start.normalize() - pd.offsets.MonthBegin(1),
		periods=periods // len(days) + 2, freq="MS")
	times = pd.DatetimeIndex([month + pd.Timedelta(days=day - 1) for month in months for day in days])
	times = times + (start - start.normalize())
	return times[times >= start][:periods].rename("Time")



@dataclass
class RegularTs:
	'''
		Regular interval time series, interval comes from the E part
		of the path (e.g. 1HOUR). start is the time of the first value.
		Missing values are NaN.

		Monthly & yearly values that end a period are stamped at 2400 of the
		last day, i.e. the first instant of the next period (01FEB2020 0000 for
		January 2020); heclib moves a month end start (31JAN2020 0000) there.
	'''
	path: DssPath
	values: np.ndarray
	start: pd.Timestamp
	unit: str = ""
	type: str = "INST-VAL"
	time_zone: str = ""
	save_as_float: bool = False
	quality: Optional[np.ndarray] = None   # read from the file, the bundled heclib doesn't write it

	def __post_init__(self):
		self.path = DssPath(self.path)
		self.values = as_1d(self.values, "values")
		self.start = pd.Timestamp(self.start)
		self.type = check_type(self.type)
		check_regular_interval(self.interval)

	@property
	def interval(self):
		return self.path.E

	@property
	def times(self):
		return regular_times(self.start, self.interval, self.values.size)

	def to_series(self):
		return pd.Series(self.values, index=self.times, name=self.path.C)

	@classmethod
	def from_series(cls, path, series, unit="", type="INST-VAL", **kwargs):
		''' pandas Series indexed by uniformly spaced times '''
		series = series.sort_index()
		return cls(path, series.values, series.index[0], unit, type, **kwargs)



@dataclass
class IrregularTs:
	'''
		Irregular interval time series (E part like IR-MONTH or ~1DAY).
		Missing values are NaN.
	'''
	path: DssPath
	times: pd.DatetimeIndex
	values: np.ndarray
	unit: str = ""
	type: str = "INST-VAL"
	time_zone: str = ""
	save_as_float: bool = False
	quality: Optional[np.ndarray] = None   # read from the file, the bundled heclib doesn't write it

	def __post_init__(self):
		self.path = DssPath(self.path)
		self.values = as_1d(self.values, "values")
		self.times = pd.DatetimeIndex(self.times, name="Time")
		self.type = check_type(self.type)
		check_irregular_interval(self.path.E)

		if self.times.size != self.values.size:
			raise ValueError("times and values size mismatch")
		if not self.times.is_monotonic_increasing or not self.times.is_unique:
			raise ValueError("times must be unique and sorted ascending")

	def to_series(self):
		return pd.Series(self.values, index=self.times, name=self.path.C)

	@classmethod
	def from_series(cls, path, series, unit="", type="INST-VAL", **kwargs):
		series = series.sort_index()
		return cls(path, series.index, series.values, unit, type, **kwargs)



@dataclass
class PairedData:
	'''
		Paired data (e.g. rating curves). x shape: [n_ordinates],
		y shape: [n_ordinates] or [n_curves, n_ordinates]
	'''
	path: DssPath
	x: np.ndarray
	y: np.ndarray
	x_unit: str = ""
	y_unit: str = ""
	x_type: str = "Linear"
	y_type: str = "Linear"
	labels: List[str] = field(default_factory=list)
	time_zone: str = ""

	def __post_init__(self):
		self.path = DssPath(self.path)
		self.x = as_1d(self.x, "x")
		self.y = np.atleast_2d(np.asarray(self.y, dtype=np.float64))
		self.labels = [str(label) for label in self.labels]

		if self.y.ndim != 2 or self.y.shape[1] != self.x.size:
			raise ValueError("y shape must be [n_curves, n_ordinates] matching x")
		if self.labels and len(self.labels) != self.n_curves:
			raise ValueError("number of labels must match number of curves")

	@property
	def n_curves(self):
		return self.y.shape[0]

	def to_dataframe(self):
		''' DataFrame indexed by x, one column per curve '''
		names = self.path.C.split('-', 1)
		x_name = names[0] or "X"
		y_name = names[1] if len(names) > 1 else "Y"

		if self.labels:
			columns = self.labels
		elif self.n_curves == 1:
			columns = [y_name]
		else:
			columns = [f"{y_name}_{i+1}" for i in range(self.n_curves)]

		return pd.DataFrame(self.y.T, columns=columns, index=pd.Index(self.x, name=x_name))

	@classmethod
	def from_dataframe(cls, path, df, x_unit="", y_unit="", **kwargs):
		''' DataFrame indexed by x, one column per curve (column names are labels) '''
		kwargs.setdefault("labels", [str(c) for c in df.columns])
		return cls(path, df.index.values, df.values.T, x_unit, y_unit, **kwargs)



@dataclass
class GriddedData:
	'''
		Gridded data. data is a north-up 2d array [rows, cols], NaN is nodata.
		xll, yll: lower left corner of the grid, origin: lower left corner of
		cell (0, 0) of the grid system. D & E parts of the path are the start &
		end time (e.g. 01JAN2020:0000), leave both empty for time invariant grids.
	'''
	path: DssPath
	data: np.ndarray
	cell_size: float
	xll: float
	yll: float
	unit: str = ""
	type: str = "INST-VAL"
	grid_type: str = "SPECIFIED"
	srs_wkt: str = ""
	srs_name: str = ""
	origin: tuple = (0.0, 0.0)
	nodata: float = float(np.finfo(np.float32).min)
	data_source: str = ""
	time_zone: str = ""
	time_zone_offset: int = 0

	def __post_init__(self):
		self.path = DssPath(self.path)
		self.data = np.asarray(self.data, dtype=np.float32)
		self.type = check_type(self.type)
		self.grid_type = self.grid_type.upper()
		self.origin = (float(self.origin[0]), float(self.origin[1]))

		if self.data.ndim != 2 or self.data.size == 0:
			raise ValueError("data must be a non empty 2d array")
		if self.cell_size <= 0:
			raise ValueError("cell_size must be positive")
		if self.grid_type not in GRID_TYPES:
			raise ValueError(f"grid_type must be one of {GRID_TYPES}")

		for corner, orig in ((self.xll, self.origin[0]), (self.yll, self.origin[1])):
			cells = (corner - orig) / self.cell_size
			if abs(cells - round(cells)) > 1e-6:
				raise ValueError("lower left corner must be aligned to origin by cell_size")

	@property
	def shape(self):
		return self.data.shape

	@property
	def lower_left_cell(self):
		''' lower left cell index relative to origin '''
		return (int(round((self.xll - self.origin[0]) / self.cell_size)),
				int(round((self.yll - self.origin[1]) / self.cell_size)))

	@property
	def extent(self):
		''' (xmin, xmax, ymin, ymax) '''
		rows, cols = self.data.shape
		return (self.xll, self.xll + cols*self.cell_size, self.yll, self.yll + rows*self.cell_size)

	@property
	def start_time(self):
		return self.path.D or None

	@property
	def end_time(self):
		return self.path.E or None
