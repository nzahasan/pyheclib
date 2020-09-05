#!/usr/bin/env python3
import numpy as np
import pyheclib as phl
from datetime import datetime as dt

# write regular time series


dss_tseries6 = phl.hecdss("tseries_ir_dss6.dss",6)
dss_tseries7 = phl.hecdss("tseries_ir_dss7.dss",7)



# write regular tseries data 

ireg_data = np.array([1.11, 2.12, 45.33, 2.32, 7.486868686, 9.89, 8888888.4440420,4.44])
ireg_time = np.array([
					dt(2020,1,2,3,44),
					dt(2020,1,4,4,43),
					dt(2020,1,6,7,56),
					dt(2020,1,11,8,25),
					dt(2020,1,13,11,17),
					dt(2020,1,14,13,30),
					dt(2020,1,20,19,40),
					dt(2020,1,23,0,0),
					])


regular_ts = phl.tseries()

regular_ts.irregular(
		"/Alpha/Beta/Flow//IR-DAY/Femta/",
		ireg_data,
		ireg_time,
		'cfs',
		'Inst-Val'
		)


dss_tseries6.write(regular_ts)
dss_tseries7.write(regular_ts)



# read tseries
r6 = dss_tseries6.read("/Alpha/Beta/Flow//IR-DAY/Femta/",phl.record_type.TSERIES)
r7 = dss_tseries6.read("/Alpha/Beta/Flow//IR-DAY/Femta/",phl.record_type.TSERIES)

print("** v6 **")
print(r6.data())

print("** v7 **")
print(r7.data())


dss_tseries6.close()
dss_tseries7.close()