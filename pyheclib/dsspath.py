'''
	DssPath: a dss pathname /A/B/C/D/E/F/ split into its parts.

	    path = DssPath("/BASIN/GAGE/FLOW/01JAN2020/1HOUR/OBS/")
	    path.C                    -> 'FLOW'
	    path.replace(F="SIM")     -> /BASIN/GAGE/FLOW/01JAN2020/1HOUR/SIM/
	    path.without_date()       -> /BASIN/GAGE/FLOW//1HOUR/OBS/
'''

MAX_PATH_LEN = 393
MAX_PART_LEN = 64
PART_NAMES = ("A", "B", "C", "D", "E", "F")


class DssPath:
	'''
		Immutable dss pathname. Parts are read with path.A ... path.F,
		use replace() to get a path with changed parts.
		Comparison is case insensitive (as in heclib).
	'''

	def __init__(self, path):
		path = str(path)

		if not (path.startswith('/') and path.endswith('/') and path.count('/') == 7):
			raise ValueError(f"Invalid pathname '{path}', expected /A/B/C/D/E/F/")

		if len(path) > MAX_PATH_LEN:
			raise ValueError(f"Pathname longer than {MAX_PATH_LEN} characters")

		parts = tuple(path[1:-1].split('/'))
		for name, part in zip(PART_NAMES, parts):
			if len(part) > MAX_PART_LEN:
				raise ValueError(f"Pathname part {name} longer than {MAX_PART_LEN} characters")

		self._parts = parts

	@classmethod
	def from_parts(cls, A="", B="", C="", D="", E="", F=""):
		return cls(f"/{A}/{B}/{C}/{D}/{E}/{F}/")

	# parts
	A = property(lambda self: self._parts[0])
	B = property(lambda self: self._parts[1])
	C = property(lambda self: self._parts[2])
	D = property(lambda self: self._parts[3])
	E = property(lambda self: self._parts[4])
	F = property(lambda self: self._parts[5])

	def parts(self):
		''' {'A': .., 'B': .., ..., 'F': ..} '''
		return dict(zip(PART_NAMES, self._parts))

	def replace(self, **parts):
		''' new path with some parts changed, e.g. path.replace(D="", F="SIM") '''
		unknown = set(parts) - set(PART_NAMES)
		if unknown:
			raise ValueError(f"Unknown pathname parts {sorted(unknown)}")
		return DssPath.from_parts(**{**self.parts(), **parts})

	def without_date(self):
		''' path with an empty D part (a whole time series data set) '''
		return self.replace(D="")

	def __str__(self):
		return "/" + "/".join(self._parts) + "/"

	def __repr__(self):
		return f"DssPath('{self}')"

	def __eq__(self, other):
		if isinstance(other, (DssPath, str)):
			return str(self).upper() == str(other).upper()
		return NotImplemented

	def __hash__(self):
		return hash(str(self).upper())
