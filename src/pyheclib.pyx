''' 
	Cython wrapper around heclib for 
	r/w access to hec-dss file
'''


import os, sys
import numpy as np 
cimport numpy as np
from pandas import DataFrame 
from datetime import datetime as dt,timedelta as delt


from general cimport * 
from tseries cimport *
from paired cimport *
from spatial cimport *

__version__='0.1.0'

# vars & enums
cdef int IFLTAB_SIZE = 250
cdef int MAX_PATH_LEN = 391
cdef int MAX_PART_LEN = 64
cpdef DSS_BASE_DATE = dt(1900,1,1)

cpdef enum record_type:
	TSERIES = 0
	PAIRED  = 1
	GRIDDED = 2


cdef dict record_type_s = {
	record_type.TSERIES : "TSERIES", 
	record_type.PAIRED  : "PAIRED",  
	record_type.GRIDDED : "GRIDDED",
}


# record data types
cpdef enum data_type:
	INST_VAL = 0
	INST_CUM = 1
	PER_AVER = 2
	PER_CUM  = 3

cdef dict data_type_s = {

	data_type.INST_VAL : "INST-VAL",
	data_type.INST_CUM : "INST-CUM",
	data_type.PER_AVER : "PER-AVER",
	data_type.PER_CUM  : "PER-CUM",
}


cpdef enum axis_type:
	LINEAR = 1
	

cdef dict axis_type_s = {
	axis_type.LINEAR :"Linear", 
}


cpdef enum granularity:
	SECOND = 1
	MINUTE = 60
	HOUR   = 3600
	DAY    = 86400




'''
Dss version 6 outputs log messages 
even after explicitly setting message level
source: https://stackoverflow.com/questions/5081657/

'''

''' * messes up ipython and bpython * '''
cpdef redir_stdout():
	sys.stdout.flush()
	newstdout = os.dup(1)
	devnull = os.open(os.devnull, os.O_WRONLY)
	os.dup2(devnull, 1)
	os.close(devnull)
	sys.stdout = os.fdopen(newstdout, 'w')


# log file
# zl_status = zopenLog(bytes("/dev/null",encoding="ascii"));


cdef int rec_data_type(np.ndarray[long long, mode="c"] ifltab,char* pathname):
	
	return zdataType (&ifltab[0], pathname)



''' ** healper funcions ** '''


cdef b2str(char * char_bytes):
	'''Convert bytes to ASCII string'''
	return char_bytes.decode(encoding="ascii")

cdef str2b(str asc_str):
	'''Convert ASCII string to bytes'''
	return bytes(asc_str,encoding="ascii")


cdef path2parts(str full_path):
	# * this dosent check for path len 
	# * use check path for that

	_,PART_A,PART_B,PART_C,PART_D,PART_E,PART_F,_ = full_path.split('/')

	return {'A':PART_A,'B':PART_B,'C':PART_C,'D':PART_D,'E':PART_E,'F':PART_F}

cdef parts2path(str A,str B, str C, str D, str E, str F):

	return f'/{A}/{B}/{C}/{D}/{E}/{F}/'


cdef int check_path(str full_path) except? -99:

	if full_path.startswith('/') and full_path.endswith('/'):

		if len(full_path) > MAX_PATH_LEN:
			return -10

		path_parts = path2parts(full_path)

		for part in path_parts.keys():
			if len(path_parts[part])>64:
				return -20

	else:
		return -1
	


''' ** controlling message level ** '''
# in windows this function oddly outputs a newline
zset(str2b("mess"),str2b("general"),0)


''' ** wrapper for hec-dss C functions ** '''

cdef int dss_open(np.ndarray[long long, mode="c"] ifltab, 
	char* filename,int dss_version) except? -20:
	
	cdef int status=0
	
	if dss_version==6:
		status = zopen6(&ifltab[0],filename)
	elif dss_version==7:
		status = zopen7(&ifltab[0],filename)

	if status<0:
		raise Exception("file open failed status code ",status)

	return status

cdef int dss_version(np.ndarray[long long, mode="c"] ifltab):
	return zgetVersion(&ifltab[0])



cdef int dss_close(np.ndarray[long long, mode="c"] ifltab):
	return zclose(&ifltab[0])

# timeseries wrapper functions
cdef zStructTimeSeries* gen_double_regts_struct( char* pathname, 
				np.ndarray[double, mode="c",ndim=1] doubleValues,
				int numberValues, char *startDate, char *startTime,
				char *units, char *_type
				):
	
	return zstructTsNewRegDoubles(
				pathname, &doubleValues[0], numberValues,
				startDate, startTime, units, _type
			)


cdef zStructTimeSeries* gen_float_regts_struct( char* pathname, 
				np.ndarray[float, mode="c",ndim=1] floatValues,
				int numberValues, char *startDate, char *startTime,
				char *units, char *_type
				):
	
	return zstructTsNewRegFloats(
				pathname, &floatValues[0], 
				numberValues,startDate, startTime, units, _type
			)

cdef zStructTimeSeries* gen_double_iregts_struct(char* pathname,
			np.ndarray[double, mode="c",ndim=1] doubleValues,
			int numberValues, np.ndarray[int, mode="c",ndim=1] itimes,
			int timeGranularitySeconds, char* startDateBase,
			char* units, char * _type
			):
		

		return zstructTsNewIrregDoubles(pathname, &doubleValues[0], numberValues,
		&itimes[0], timeGranularitySeconds, startDateBase, units, _type)


# ** catalog ** 

cdef zStructCatalog* dss_catalog(np.ndarray[long long, mode="c"] ifltab, 
	char* search_path) except? NULL:
	# print(search_path)
	cdef:
		zStructCatalog* catalog_ptr = zstructCatalogNew()
		int status = zcatalog(&ifltab[0],search_path,catalog_ptr,1)
		# int status = zcollectionCat(&ifltab[0], <char*>0, catalog_ptr)


	if status <0 :
		raise Exception('failed to retrive catalog with error ',status)

	return catalog_ptr


cdef int write_tseries(np.ndarray[long long, mode="c"] ifltab,  tseries container) except? -99:

	if container.zstruct_ts == NULL:
		raise Exception("Incomplete time-series record")
	return ztsStore(&ifltab[0],container.zstruct_ts,0)


cdef int read_tseries(np.ndarray[long long, mode="c"] ifltab,char* pathname,dssrec record_obj) except? -55:
		
	cdef:
		zStructTimeSeries* ts_ptr =  zstructTsNew(pathname)
		int status = 0
		np.ndarray values_array
		np.ndarray times_array
		np.ndarray datetime_array
		char cdate[13], ctime[10]

	
	# retrive all time cordinate in both cases of
	# regular and irregular * simplify reding time series
	ts_ptr.boolRetrieveAllTimes=True

	status = ztsRetrieve(&ifltab[0], ts_ptr, -1, 1, 0)

	if status == 0 :
	
		if ts_ptr.doubleValues != NULL:
			values_array = np.asarray(<double [:ts_ptr.numberValues]> ts_ptr.doubleValues)
			
		elif ts_ptr.floatValues != NULL:
			values_array = np.asarray(<float [:ts_ptr.numberValues]> ts_ptr.floatValues)

		times_array = np.asarray(<int [:ts_ptr.numberValues]> ts_ptr.times)
	

		datetime_array = np.empty(ts_ptr.numberValues,dtype=dt)
		
		for ti in range(ts_ptr.numberValues):

			getDateAndTime(ts_ptr.times[ti], ts_ptr.timeGranularitySeconds, 
						ts_ptr.julianBaseDate,
						cdate, sizeof(cdate), 
						ctime, sizeof(ctime)
						)

			_hrs,_mins = int(ctime[:2]),int(ctime[2:])

			# dtstr = b2str(cdate)+'_'+b2str(ctime)
			# in this case dtstr may results in  01Jan2020_2400 
			# which is a non standard representation of time
			
			datetime_array[ti] = dt.strptime(b2str(cdate),"%d%b%Y") \
								+ delt(hours=_hrs,minutes=_mins) 

		
		# store tseries in record object
		record_obj.TSERIES( b2str(pathname), datetime_array, values_array, 
						b2str(ts_ptr.units), b2str(ts_ptr.type)
						)


	return status
	


''' gridded data read '''

cdef int read_gridded(np.ndarray[long long, mode="c"] ifltab, char * rec_path_name) except? -99:

	cdef: 
		zStructSpatialGrid* gird_ptr = zstructSpatialGridNew(rec_path_name)
		int status = 0


	# print(gird_ptr.pathname )

	status = zspatialGridRetrieve(&ifltab[0], gird_ptr, 1)

	# if status != STATUS_OKAY:
	# 	print("failed")


	return status



''' ** Paired data wrapper function ** '''

cdef zStructPairedData* gen_double_paired_struct(char* pathname,
							np.ndarray[ double, mode='c'] x_vals,
							np.ndarray[ double, mode='c'] y_vals,
							int numberOrdinates, int numberCurves,
							char* x_unit, char* x_type,
							char* y_unit, char* y_type,
							):

	return zstructPdNewDoubles(pathname, &x_vals[0], &y_vals[0], numberOrdinates,
							numberCurves, x_unit, x_type,
							y_unit, y_type
						)

cdef int write_paired(np.ndarray[long long,mode='c'] ifltab, paired container):

	# store as doubles
	return zpdStore(&ifltab[0], container.paired_ptr,  0)


cdef int read_paried(np.ndarray[long long, mode="c"] ifltab, 
		char* path_name, dssrec record_obj) except? -55:

	cdef:
		int status =0
		zStructPairedData* paired_ptr = zstructPdNew(path_name)
		np.ndarray x_vals
		np.ndarray y_vals
	
	# always read as doubles
	status = zpdRetrieve(&ifltab[0], paired_ptr , 2); 


	if status==0:
		
		if paired_ptr.doubleOrdinates != NULL and paired_ptr.doubleValues != NULL:
			x_vals = np.asarray(<double [:paired_ptr.numberOrdinates]> paired_ptr.doubleOrdinates)
			y_vals = np.asarray(<double [:paired_ptr.numberOrdinates]> paired_ptr.doubleValues)

		# reshape arrays based on numberCurves

		record_obj.PAIRED(
			b2str(paired_ptr.pathname),
			x_vals,
			y_vals,
			b2str(paired_ptr.unitsIndependent),
			b2str(paired_ptr.unitsDependent),
			b2str(paired_ptr.typeIndependent),
			b2str(paired_ptr.typeDependent),
		)

	return status




''' **** handler classes **** '''

cdef class hecdss():
	'''	hecdss(str filename,int version)
		Container class for open/close dss file
		& read/write record form dss 
	'''
	cdef:
		np.ndarray ifltab
		zStructTimeSeries zstruct_ts
		str filename
		int fl_status

	
	def __cinit__(self,filename,version=6):
		self.ifltab = np.ascontiguousarray( 
						np.zeros((IFLTAB_SIZE),dtype=np.longlong),
						dtype=np.longlong
					)
		
		self.filename = filename
		
		# should return 0
		fl_status = dss_open(self.ifltab,str2b(filename),version)		

		if fl_status<0:
			raise Exception("Failed to open file",filename,"status",fl_status)
	
	cpdef rt(self,str path_name):

		return rec_data_type(self.ifltab,str2b(path_name))
	
	cpdef dssrec read(self, str path_name, int _record_type, 
		str start_date=None, str end_date=None):
		
		cdef:
			int status
			dssrec rec_obj = dssrec()


		if _record_type == record_type.TSERIES:

			if start_date == None and end_date == None:
				# read all record
				status = read_tseries(self.ifltab,str2b(path_name),rec_obj)
		
		elif _record_type == record_type.GRIDDED:
			# status = read_gridded(self.ifltab,str2b(path_name))
			pass

		elif _record_type == record_type.PAIRED:

			status = read_paried(self.ifltab,str2b(path_name),rec_obj)

		else:
			raise Exception("Unsupported record type")

		if status != 0:
			raise Exception("Unable to read record status code", status)

		return rec_obj
		

	# write record in dss
	cpdef int write(self, rec_container) except? -999:

		if isinstance(rec_container,tseries):
			return write_tseries(self.ifltab, rec_container)
		
		elif isinstance(rec_container,paired):
			return write_paired(self.ifltab, rec_container)

		else:
			raise TypeError("Unknown container type")


		
	cpdef int close(self):
		return dss_close(self.ifltab)	


	cpdef list catalog(self,str search_path=''):

		cdef list cat_list = []

		catalog_ptr = dss_catalog(self.ifltab, str2b(search_path))

		if catalog_ptr == NULL: 
			return cat_list

		for i in range(catalog_ptr.numberPathnames):
			cat_list.append(b2str(catalog_ptr.pathnameList[i]))

		return cat_list
		
	cpdef int version(self):

		return dss_version(self.ifltab)

	def __repr__(self):
		return f'<pyheclib: V{__version__}>'


	def __enter__(self):
		return self

	def __exit__(self,ex_type, ex_val, ex_trace):
		self.close()




cdef class dssrec():
	'''
		Container class for retrived record from hecdss
		returns a pandas dataframe

	'''
	cdef:
		str pathname
		int record_type

		# timeseries
		np.ndarray times
		np.ndarray values 
		str unit 
		str value_type

		# paired
		np.ndarray x_vals
		np.ndarray y_vals
		str x_unit
		str y_unit
		str x_type
		str y_type
		int n_curve  # number of curve



	cpdef TSERIES(self,path_name,times,values,unit,val_type):
		self.pathname = path_name
		self.unit = unit
		self.times = times
		self.values = values
		self.value_type = val_type # Inst-Cum , Inst-Val
		self.record_type = record_type.TSERIES

	cpdef PAIRED(self, path_name, x_vals, y_vals, x_unit, y_unit, x_type, y_type):
		self.pathname = path_name
		self.x_vals = x_vals
		self.y_vals = y_vals
		self.x_unit = x_unit
		self.y_unit = y_unit
		self.x_type = x_type
		self.y_type = y_type

		self.record_type = record_type.PAIRED


	cpdef GRIDDED(self):
		pass

	

	cpdef data(self,curve_no=0):
		'''
		curve_no is used for paired data and ignored other data types.
		iterate n_curve times to get all the curves
		return : dataframe based on record type
		'''

		# should be safe!
		_,PART_A,PART_B,PART_C,PART_D,PART_E,PART_F,_ = self.pathname.split('/') 
		
		ret_df = DataFrame()

		if self.record_type == record_type.TSERIES:
			ret_df['Time'] = self.times
			ret_df[PART_C] = self.values
			# ret_df.set_index('Time',inplace=True)

		elif self.record_type == record_type.PAIRED:
			_x_name,_y_name= PART_C.strip().split('-')
			ret_df[_x_name] = self.x_vals
			ret_df[_y_name] = self.y_vals


		elif self.record_type == record_type.GRIDDED:
			pass

		return ret_df


	cdef str ts_repr(self):
		return f'(\n\tPathname: {self.pathname},\n'+\
				f'\tUnit: {self.unit},\n'+\
				f'\tType: {self.value_type.upper()},\n'+\
				f'\tRecord: {record_type_s[self.record_type]},\n)'

	def __repr__(self):

		if self.record_type==record_type.TSERIES: return self.ts_repr()




cdef class tseries():
	''' 
		Container class for time series
		for passing to dss.write for storing
		in hec-dss
	'''
	cdef: 
		zStructTimeSeries* zstruct_ts	
		int has_data
		str ts_type
		# str ts_dtype


	# det regular or iregular form time series not necessary
	# may be use path name at read time to determine what type of container
	
	def __cinit__(self):
		self.zstruct_ts = NULL

	cpdef int regular(self, str rec_path, rec_vals, # must be a numpy array
				str start_date, str start_time, 
				str ts_unit, str ts_type) except?-99:


		if not isinstance(rec_vals,np.ndarray) or rec_vals.ndim != 1:
			raise Exception("values must be a numpy array with single dimension")

		cdef int rec_size = rec_vals.shape[0]

		# determine type zstruct from numpy
		if rec_vals.dtype==np.half or rec_vals.dtype==np.single or \
			rec_vals.dtype==np.int8 or rec_vals.dtype==np.int16 or \
			rec_vals.dtype==np.int32:

			self.zstruct_ts= gen_float_regts_struct( str2b(rec_path),
								np.ascontiguousarray(rec_vals,dtype=np.single), 
								rec_size, str2b(rec_path), str2b(start_time),
								str2b(ts_unit), str2b(ts_type)
								)

		elif rec_vals.dtype ==np.double or rec_vals.dtype==np.float128 or \
			rec_vals.dtype == np.int64 or rec_vals.dtype==np.int128:
			
			self.zstruct_ts = gen_double_regts_struct(str2b(rec_path),
							np.ascontiguousarray(rec_vals, dtype=np.double), 
							rec_size, str2b(start_date), str2b(start_time),
							str2b(ts_unit), str2b(ts_type)
							)


		return 0

	
	
	cpdef int irregular(self, str rec_path, rec_vals, rec_times, # 
		str ts_unit, str ts_type) except? -20:

		if len(rec_vals.shape)!=1 or len(rec_times.shape)!=1:
			raise ValueError('Arrays are not one dimensional') 

		if rec_vals.shape != rec_times.shape:
			raise ValueError('Array shape mismatch')

		cdef int ts_len = rec_vals.shape[0] 
		cdef np.ndarray del_times = np.zeros(ts_len,dtype=np.intc)

		# calculate start date // should be first element
		# base_date = rec_times.min()
		# take base date around center of time series
		# time series should be sorted according to date
		date_base = dt(
						rec_times[ts_len//2].year,
						rec_times[ts_len//2].month,
						rec_times[ts_len//2].day
					)
		start_date = str2b(date_base.strftime("%d%b%Y"))
		
		del_times_obj = rec_times - date_base

		for ti in np.arange(ts_len):
			del_times[ti] = del_times_obj[ti].total_seconds()/60

		# default is MINUTE ** check if second is needed
		ts_granularity = granularity.MINUTE


		self.zstruct_ts = gen_double_iregts_struct(str2b(rec_path),
						np.ascontiguousarray(rec_vals,dtype=np.double),
						ts_len,
						np.ascontiguousarray(del_times,dtype=np.intc), 
						granularity.MINUTE, start_date,
						str2b(ts_unit), str2b(ts_type)
						)

		
		return 0

	# mark the container check on 2nd call if the container is regular or irregular



cdef class paired():

	cdef:
		zStructPairedData* paired_ptr
	
	'''
		x_vals and y_vals shape should be [n_curve,n_ordinate]
	'''

	def __cinit__(self,str pathname, x_vals, y_vals,  # xvals and y vals is numpy array
				x_unit, y_unit, x_type='Linear', y_type='Linear'):
		
		cdef: 
			int num_curve = 1 if len(x_vals.shape)==1 else x_vals.shape[0] 
			int num_ordinate = x_vals.shape[-1]



		if x_vals.shape != y_vals.shape:
			raise ValueError("Size mismatch between x and y values")

		# flatten x_vals ans y_vals

		self.paired_ptr = gen_double_paired_struct(str2b(pathname),
						np.ascontiguousarray(x_vals,dtype=np.double),
						np.ascontiguousarray(y_vals,dtype=np.double),
						num_ordinate, num_curve,
						str2b(x_unit), str2b(x_type),
						str2b(x_type), str2b(y_type)
						)

	
