# pyheclib
<img src="assets/pyheclib_banner.png" alt="pyheclib">

HEC-DSS, is a database system designed by [U.S. Army Corps of Engineers' Hydrologic 
Engineering Center](https://www.hec.usace.army.mil/) to efficiently store and retrieve 
typically sequential scientific data. HEC-DSS is incorporated into most of HEC’s 
major application programs like HEC-HMS, HEC-RAS etc.

record types implemented in pyheclib are:  
	- Time Series Data (Regular & Irragular) 
	- Paired Data


### Install

```bash
# on ubuntu 18.04/20.04
$ pip3 install https://github.com/nzahasan/pyheclib/zipball/master 

# on windows requires MS visual c++ 14 build tools & inter fortran compiler 


```

# Usage

Example given below shows how to read & write regular  time series:

```python
import pyheclib as phl
import numpy as np

reg_data = np.array([13.21, 44.21, 13.24, 55.21,88.76,77.33])

ts_cnt = phl.tseries()

ts_cnt.regular(
	"/BASIN/LOCATION/FLOW//3HOUR/TEST/",
	reg_data,
	"01Jan2020",
	"06:39",
	'cfs',
	'Inst-Val'
)
# opens a dss file default is version 6
# for a version 7 file pass `version=7` as argument 
dssf = phl.hecdss("tseries.dss")
dssf.write(ts_cont)

# * read record *
ret_data = dssf.read(
	"/BASIN/LOCATION/FLOW//3HOUR/TEST/",
	phl.record_type.TSERIES
	)

print(ret_data)

dssf.close()
```

for a detailed documentation visit https://nzahasan.github.io/pyheclib


### Resources  

- [HEC-DSS C Library](https://www.hec.usace.army.mil/software/hec-dss/downloads.aspx) 
- [HEC-DSSVue (A java based gui)](https://www.hec.usace.army.mil/software/hec-dssvue/)

### todo's
- add delete record support
- free struct after writing data
- @ write check if data is empty
- tool for record to csv 