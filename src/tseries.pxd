cdef extern from "heclib.h":

	ctypedef struct zStructTimeSeries:
		int structType
		char *pathname
		int *times
		float *floatValues
		double *doubleValues
		int sizeEachValueRead
		int precision
		char *timeZoneName
		int numberValues
		char *type
		char *units
		int timeGranularitySeconds
		int timeIntervalSeconds
		int julianBaseDate
		int startJulianDate
		int endJulianDate
		int startTimeSeconds
		int endTimeSeconds
		char *pathnameInternal
		int boolRetrieveAllTimes

	#zstruct timeseries

	zStructTimeSeries* zstructTsNewRegFloats(
		const char* pathname, float *floatValues, int numberValues,
		const char *startDate, const char *startTime, const char *units, 
		const char *type
		)
	zStructTimeSeries* zstructTsNewRegDoubles(
		const char* pathname, double *doubleValues, int numberValues,
		const char *startDate, const char *startTime, 
		const char *units, const char *type
		)

	zStructTimeSeries* zstructTsNewIrregFloats(
		const char* pathname, float *floatValues, int numberValues, 
		int *itimes, int timeGranularitySeconds, const char* startDateBase, 
		const char *units, const char *type
		)

	zStructTimeSeries* zstructTsNewIrregDoubles(
		const char* pathname, double *doubleValues, int numberValues,
		int *itimes, int timeGranularitySeconds, const char* startDateBase, 
		const char *units, const char *type
		)



	# [time series ]
	
	zStructTimeSeries* zstructTsNew(const char* pathname)

	int ztsStore(long long *ifltab, zStructTimeSeries *tss, int storageFlag)
	
	int ztsRetrieve(
			long long *ifltab, zStructTimeSeries *tss,
			int retrieveFlag, int retrieveDoublesFlag, int boolRetrieveQualityNotes
		)
