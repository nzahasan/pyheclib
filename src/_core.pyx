'''
	Thin Cython wrapper around the HEC-DSS C API (hecdss).
	Only handles C calls & buffers, conversion to records is in dssfile.py
'''

import os
import numpy as np
cimport numpy as np

from hecdss cimport *

np.import_array()

MAX_PATH_LEN = hec_dss_CONSTANT_MAX_PATH_SIZE()


cdef bytes b(str text):
	''' str -> ascii bytes '''
	return text.encode("ascii")


cdef str s(bytearray buf):
	''' null terminated buffer -> str '''
	return bytes(buf).split(b'\0', 1)[0].decode("ascii", "replace").strip()


def api_version():
	return hec_dss_api_version().decode("ascii")


def set_message_level(int level):
	''' heclib message level 0: none, 1: critical, 2: terse, ... '''
	return hec_dss_set_value(b"mlvl", level)



cdef class DssHandle:
	''' an open dss version 7 file '''

	cdef dss_file* dss

	def __cinit__(self, str filename):
		self.dss = NULL

		if os.path.exists(filename):
			version = hec_dss_getFileVersion(b(filename))
			if version == 6:
				raise ValueError(f"'{filename}' is a DSS version 6 file, only version 7 "
					"is supported. Convert it with HEC-DSSVue.")
			if version < 0:
				raise ValueError(f"'{filename}' is not a valid DSS file (status {version})")

		status = hec_dss_open(b(filename), &self.dss)
		if status != 0:
			self.dss = NULL
			raise IOError(f"Failed to open '{filename}' status {status}")

	def __dealloc__(self):
		if self.dss != NULL:
			hec_dss_close(self.dss)
			self.dss = NULL

	cdef dss_file* get(self) except NULL:
		if self.dss == NULL:
			raise ValueError("I/O operation on closed dss file")
		return self.dss

	def close(self):
		if self.dss != NULL:
			hec_dss_close(self.dss)
			self.dss = NULL

	@property
	def is_open(self):
		return self.dss != NULL

	def version(self):
		return hec_dss_getVersion(self.get())

	def record_type(self, str path):
		''' heclib record type code, -1 if not found '''
		return hec_dss_recordType(self.get(), b(path))

	def delete(self, str path):
		return hec_dss_delete(self.get(), b(path))

	def catalog(self, str path_filter=""):
		''' list of (pathname, record type code) '''
		cdef:
			dss_file* dss = self.get()
			int count = hec_dss_record_count(dss)
			bytes c_filter = b(path_filter)
			const char* filter_ptr = NULL
			np.ndarray[int] types

		if count <= 0:
			return []

		if path_filter:
			filter_ptr = c_filter

		paths = bytearray(count * MAX_PATH_LEN)
		types = np.zeros(count, dtype=np.intc)

		n = hec_dss_catalog(dss, paths, &types[0], filter_ptr, count, MAX_PATH_LEN)
		if n < 0:
			raise IOError(f"catalog failed with status {n}")

		return [(s(paths[i*MAX_PATH_LEN:(i+1)*MAX_PATH_LEN]), int(types[i])) for i in range(n)]


	# ** time series **

	def ts_date_range(self, str path):
		''' (first julian, first seconds, last julian, last seconds) of whole data set '''
		cdef int fj = 0, fs = 0, lj = 0, ls = 0
		status = hec_dss_tsGetDateTimeRange(self.get(), b(path), 1, &fj, &fs, &lj, &ls)
		if status != 0:
			raise KeyError(f"Time series '{path}' not found (status {status})")
		return fj, fs, lj, ls

	def ts_size(self, str path, str start_date, str start_time, str end_date, str end_time):
		''' (number of values, quality element size) in time window '''
		cdef int n = 0, quality_size = 0
		status = hec_dss_tsGetSizes(self.get(), b(path), b(start_date), b(start_time),
						b(end_date), b(end_time), &n, &quality_size)
		if status != 0:
			raise KeyError(f"Time series '{path}' not found (status {status})")
		return n, quality_size

	def ts_retrieve(self, str path, window, int size, bint with_quality):
		'''
			window: (start_date, start_time, end_date, end_time) or None for all data
			returns dict of int times, julian base, granularity, values, quality & metadata
		'''
		cdef:
			dss_file* dss = self.get()
			int n_read = 0, julian_base = 0, granularity = 0
			np.ndarray[int] times
			np.ndarray[double] values
			np.ndarray[int] quality
			bytearray units = bytearray(64), data_type = bytearray(64), tz = bytearray(64)
			bytes sd, st, ed, et
			const char* w[4]

		w[0] = w[1] = w[2] = w[3] = NULL
		if window:
			sd, st, ed, et = [b(v) for v in window]
			w[0], w[1], w[2], w[3] = sd, st, ed, et

		size = max(size, 1) + 1
		while True:
			times = np.zeros(size, dtype=np.intc)
			values = np.zeros(size, dtype=np.double)
			quality = np.zeros(size, dtype=np.intc)

			status = hec_dss_tsRetrieve(dss, b(path), w[0], w[1], w[2], w[3],
						&times[0], &values[0], size, &n_read,
						&quality[0], 1 if with_quality else 0,
						&julian_base, &granularity,
						units, len(units), data_type, len(data_type), tz, len(tz))

			if status != 0:
				raise IOError(f"Unable to read time series '{path}' status {status}")

			# heclib truncates silently, retry with larger buffers
			if n_read < size:
				break
			size *= 2

		return {
			"times": times[:n_read], "julian_base": julian_base, "granularity": granularity,
			"values": values[:n_read], "quality": quality[:n_read] if with_quality else None,
			"unit": s(units), "type": s(data_type), "time_zone": s(tz),
		}

	def ts_store_regular(self, str path, str start_date, str start_time,
			np.ndarray[double, mode="c"] values, str unit, str data_type,
			str time_zone, bint save_as_float):

		return hec_dss_tsStoreRegular(self.get(), b(path), b(start_date), b(start_time),
					&values[0], values.shape[0], NULL, 0, save_as_float,
					b(unit), b(data_type), b(time_zone), 0)

	def ts_store_irregular(self, str path, str base_date,
			np.ndarray[int, mode="c"] times, int granularity,
			np.ndarray[double, mode="c"] values, str unit, str data_type,
			str time_zone, bint save_as_float):

		return hec_dss_tsStoreIregular(self.get(), b(path), b(base_date),
					&times[0], granularity, &values[0], values.shape[0], NULL, 0,
					save_as_float, b(unit), b(data_type), b(time_zone), 1)


	# ** paired data **

	def pd_retrieve(self, str path):
		cdef:
			dss_file* dss = self.get()
			int n_ord = 0, n_curves = 0, labels_len = 0
			bytearray x_unit = bytearray(64), y_unit = bytearray(64)
			bytearray x_type = bytearray(64), y_type = bytearray(64), tz = bytearray(64)
			bytearray labels
			np.ndarray[double] x
			np.ndarray[double] y

		status = hec_dss_pdRetrieveInfo(dss, b(path), &n_ord, &n_curves,
					x_unit, 64, y_unit, 64, x_type, 64, y_type, 64, &labels_len)
		if status != 0 or n_ord <= 0:
			raise KeyError(f"Paired data '{path}' not found (status {status})")

		x = np.zeros(n_ord, dtype=np.double)
		y = np.zeros(n_ord * n_curves, dtype=np.double)
		labels = bytearray(max(labels_len, 1))

		status = hec_dss_pdRetrieve(dss, b(path), &x[0], n_ord, &y[0], n_ord * n_curves,
					&n_ord, &n_curves, x_unit, 64, x_type, 64, y_unit, 64, y_type, 64,
					labels, len(labels), tz, 64)
		if status != 0:
			raise IOError(f"Unable to read paired data '{path}' status {status}")

		# labels are stored as null separated strings
		label_list = []
		if labels_len > 0:
			label_list = bytes(labels[:labels_len]).decode("ascii", "replace").split('\0')[:n_curves]

		return {
			"x": x, "y": y.reshape(n_curves, n_ord),
			"x_unit": s(x_unit), "y_unit": s(y_unit), "x_type": s(x_type), "y_type": s(y_type),
			"labels": label_list, "time_zone": s(tz),
		}

	def pd_store(self, str path, np.ndarray[double, mode="c"] x,
			np.ndarray[double, ndim=2, mode="c"] y,
			str x_unit, str x_type, str y_unit, str y_type, list labels, str time_zone):
		cdef:
			int n_curves = y.shape[0], n_ord = y.shape[1]
			bytes c_labels = b''
			const char* labels_ptr = NULL

		if labels:
			c_labels = b('\0'.join(labels) + '\0')
			labels_ptr = c_labels

		return hec_dss_pdStore(self.get(), b(path), &x[0], n_ord, &y[0, 0], n_ord * n_curves,
					n_ord, n_curves, b(x_unit), b(x_type), b(y_unit), b(y_type),
					labels_ptr, len(c_labels), b(time_zone))


	# ** gridded data **

	def grid_retrieve(self, str path):
		''' header dict & data (flat, rows south -> north) '''
		cdef:
			dss_file* dss = self.get()
			int grid_type = 0, data_type = 0, llx = 0, lly = 0, nx = 0, ny = 0, n_ranges = 0
			int srs_type = 0, tz_offset = 0, is_interval = 0, is_stamped = 0
			float cell_size = 0, x0 = 0, y0 = 0, nodata = 0, v_max = 0, v_min = 0, v_mean = 0
			bytearray units = bytearray(64), source = bytearray(128), srs_name = bytearray(256)
			bytearray srs_wkt = bytearray(16384), tz = bytearray(64)
			np.ndarray[float] range_limits = np.zeros(1, dtype=np.single)
			np.ndarray[int] range_counts = np.zeros(1, dtype=np.intc)
			np.ndarray[float] data = np.zeros(1, dtype=np.single)
			int ranges_len = 0, data_len = 0

		# read header first for array sizes, then the data
		for with_data in (0, 1):
			if with_data:
				ranges_len, data_len = n_ranges, nx * ny
				range_limits = np.zeros(max(ranges_len, 1), dtype=np.single)
				range_counts = np.zeros(max(ranges_len, 1), dtype=np.intc)
				data = np.zeros(max(data_len, 1), dtype=np.single)

			status = hec_dss_gridRetrieve(dss, b(path), with_data,
						&grid_type, &data_type, &llx, &lly, &nx, &ny, &n_ranges, &srs_type,
						&tz_offset, &is_interval, &is_stamped,
						units, len(units), source, len(source), srs_name, len(srs_name),
						srs_wkt, len(srs_wkt), tz, len(tz),
						&cell_size, &x0, &y0, &nodata, &v_max, &v_min, &v_mean,
						&range_limits[0], ranges_len, &range_counts[0], &data[0], data_len)

			if status != 0:
				raise KeyError(f"Grid '{path}' not found (status {status})")

		return {
			"grid_type": grid_type, "data_type": data_type, "lower_left_cell": (llx, lly),
			"nx": nx, "ny": ny, "cell_size": cell_size, "origin": (x0, y0), "nodata": nodata,
			"unit": s(units), "data_source": s(source), "srs_name": s(srs_name),
			"srs_wkt": s(srs_wkt), "time_zone": s(tz), "time_zone_offset": tz_offset,
			"data": data[:data_len],
		}

	def grid_store(self, str path, dict h,
			np.ndarray[float, mode="c"] range_limits, np.ndarray[int, mode="c"] range_counts,
			np.ndarray[float, mode="c"] data):
		''' h: header dict, same keys as grid_retrieve returns plus statistics & time flags '''
		return hec_dss_gridStore(self.get(), b(path),
					h["grid_type"], h["data_type"], h["lower_left_cell"][0], h["lower_left_cell"][1],
					h["nx"], h["ny"], range_limits.shape[0], 1 if h["srs_wkt"] else 0,
					h["time_zone_offset"], h["is_interval"], h["is_time_stamped"], 0,
					b(h["unit"]), b(h["data_source"]), b(h["srs_name"]), b(h["srs_wkt"]),
					b(h["time_zone"]), h["cell_size"], h["origin"][0], h["origin"][1], h["nodata"],
					h["max"], h["min"], h["mean"],
					&range_limits[0], &range_counts[0], &data[0])
