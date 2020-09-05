#!/usr/bin/env python3
import numpy as np
import pyheclib as phl

# write regular time series


dss_tseries6 = phl.hecdss("tseries_dss6.dss",6)
dss_tseries7 = phl.hecdss("tseries_dss7.dss",7)



# write regular tseries data 

reg_data = np.array([1.11, 2.12, 45.33, 2.32, 7.486868686, 9.89, 8888888.4440420])



regular_ts = phl.tseries()

regular_ts.regular(
		"/Alpha/Beta/Flow//3Hour/Femta/",
		reg_data,
		"01Jan2020",
		"06:39",
		'cfs',
		'Inst-Val'
		)


dss_tseries6.write(regular_ts)
dss_tseries7.write(regular_ts)



# read tseries
r6 = dss_tseries6.read("/Alpha/Beta/Flow//3Hour/Femta/",phl.record_type.TSERIES)
r7 = dss_tseries6.read("/Alpha/Beta/Flow//3Hour/Femta/",phl.record_type.TSERIES)

print("** v6 **")
print(r6.data())

print("** v7 **")
print(r7.data())


dss_tseries6.close()
dss_tseries7.close()