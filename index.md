## Install pyheclib

```bash
# on ubuntu 18.04/20.04
$ pip3 install https://github.com/nzahasan/pyheclib/zipball/master 
```


## Open & close dss file






## Read Write Time-Series 

#### Reading & writing of regular time series data

```python
import numpy as np
import pyheclib as phl

# open a hec dss file will be crated automatically if dosent exists
dss_tseries = phl.hecdss("tseries_dss6.dss")

# creating a dataset for input
reg_data = np.array([1.11, 2.12, 45.33, 2.32, 7.486868686, 9.89, 8888888.4440420])

# create a tseries container
regular_ts = phl.tseries()

# add regular data to tseries
regular_ts.regular(
		"/Subbasin/Location/Flow//3Hour/Test/",
		reg_data,     # numpy array containing values
		"01Jan2020",  # start date of time series
		"06:39",      # start time of time series
		'cfs',        # unit of rec
		'Inst-Val'    # type of series
		)

# write tseries container to dss file
dss_tseries.write(regular_ts)



# read tseries this is also similar fo irregular tseries
rec = dss_tseries.read(
		"/Subbasin/Location/Flow//3Hour/Test/", # path of the record
		phl.record_type.TSERIES           # what type of record TSERIES/PARIED etc
		)

# read returns a pandas dataframe 
# depending on the record type

print(rec.data())

# close the dss file
dss_tseries.close()
```
Writing and reading irregular time series record in dss file:

```python


import numpy as np
import pyheclib as phl
from datetime import datetime as dt

# write regular time series

# open a version 7 file 
dss_tseries = phl.hecdss("tseries_ir_dss.dss",7)


# generate data of irregular tseries data 
ireg_data = np.array([1.11, -502.12, 4500.33, ])
ireg_time = np.array([ dt(2020,1,2,3,44), dt(2020,1,4,4,43),dt(2020,1,6,7,56),])


# create a timeseries container
regular_ts = phl.tseries()

# add data irregular data in container
regular_ts.irregular(
		"/Alpha/Beta/Flow//IR-DAY/Femta/", # path name
		ireg_data,                         # numpy array of values
		ireg_time,                         # numpy array containing datetime 
		'cfs',                             # unit
		'Inst-Val'                         # tseries type
		)


dss_tseries.write(regular_ts)

# read tseries
rec = dss_tseries.read("/Alpha/Beta/Flow//IR-DAY/Femta/",phl.record_type.TSERIES)

print(rec.data())

dss_tseries.close()

```


### Resources  

- [HEC-DSS C Library](https://www.hec.usace.army.mil/software/hec-dss/downloads.aspx) 
- [HEC-DSSVue (A java based gui)](https://www.hec.usace.army.mil/software/hec-dssvue/)

