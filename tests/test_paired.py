#!/usr/bin/env python3
import pyheclib

import numpy as np
from datetime import datetime as dt,timedelta as delt 


paired_dss6 = pyheclib.hecdss("paired6.dss",version=6)
paired_dss7 = pyheclib.hecdss("paired7.dss",version=7)



x_data = np.arange(0,100,0.1)
y_data = np.sin(x_data)
	


pr = pyheclib.paired(
	"/Alpha/Beta/Stage-Flow/Rating Table//Fempto",
	x_data,
	y_data,
	"CFS",
	"M"
)


# write
paired_dss6.write(pr)
paired_dss7.write(pr)


# rec7 = paired_dss7.read("/Alpha/Beta/Stage-Flow/Rating Table//Fempto",pyheclib.record_type.PAIRED)
# rec6 = paired_dss6.read("/Alpha/Beta/Stage-Flow/Rating Table//Fempto",pyheclib.record_type.PAIRED)

# curves6 = rec6.data()
# curves7 = rec7.data()








paired_dss6.close()
paired_dss7.close()




# import pylab as pl 
