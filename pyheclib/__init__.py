'''
	pyheclib: python interface for HEC-DSS (version 7) files

	    import pyheclib as phl

	    rts = phl.RegularTs("/BASIN/GAGE/FLOW//1HOUR/OBS/", values, "2020-01-01 01:00", unit="cfs")

	    dss_file = phl.open("example.dss")
	    dss_file.write(rts)
	    rts = dss_file.read("/BASIN/GAGE/FLOW//1HOUR/OBS/")
	    dss_file.close()
'''

from ._core import api_version, set_message_level
from .dsspath import DssPath
from .records import RegularTs, IrregularTs, PairedData, GriddedData
from .dssfile import open, DssFile

import os

__version__ = '0.4.1'


def message_level_from_env():
	''' heclib message level from DSS_MESSAGE_LEVEL (0 to 15), 1 if not set or invalid '''
	try:
		level = int(os.environ.get("DSS_MESSAGE_LEVEL", ""))
	except ValueError:
		return 1
	return level if 0 <= level <= 15 else 1


set_message_level(message_level_from_env())
