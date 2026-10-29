''' ** hecdss C API (heclib/include/hecdss.h) declarations ** '''

cdef extern from "hecdss.h" nogil:

	ctypedef struct dss_file:
		pass

	int HEC_DSS_BUFFER_TOO_SMALL

	const char* hec_dss_api_version()
	int hec_dss_CONSTANT_MAX_PATH_SIZE()

	int hec_dss_open(const char* filename, dss_file** dss)
	int hec_dss_close(dss_file* dss)
	int hec_dss_getVersion(dss_file* dss)
	int hec_dss_getFileVersion(const char* filename)

	int hec_dss_set_value(const char* name, const int value)
	int hec_dss_set_string(const char* name, const char* value)

	int hec_dss_record_count(dss_file* dss)
	int hec_dss_catalog(dss_file* dss, char* pathBuffer, int* recordTypes,
		const char* pathFilter, const int count, const int pathBufferItemSize)
	int hec_dss_dataType(dss_file* dss, const char* pathname)
	int hec_dss_recordType(dss_file* dss, const char* pathname)
	int hec_dss_delete(dss_file* dss, const char* pathname)
	int hec_dss_squeeze(const char* pathname)

	# [date]
	int hec_dss_dateToJulian(const char* date)
	void hec_dss_julianToYearMonthDay(const int julian, int* year, int* month, int* day)

	# [time series]
	int hec_dss_tsGetDateTimeRange(dss_file* dss, const char* pathname, const int boolFullSet,
		int* firstValidJulian, int* firstSeconds, int* lastValidJulian, int* lastSeconds)

	int hec_dss_tsGetSizes(dss_file* dss, const char* pathname,
		const char* startDate, const char* startTime,
		const char* endDate, const char* endTime,
		int* numberValues, int* qualityElementSize)

	int hec_dss_tsRetrieve(dss_file* dss, const char* pathname,
		const char* startDate, const char* startTime,
		const char* endDate, const char* endTime,
		int* timeArray, double* valueArray, const int arraySize,
		int* numberValuesRead, int* quality, const int qualityWidth,
		int* julianBaseDate, int* timeGranularitySeconds,
		char* units, const int unitsLength,
		char* type, const int typeLength,
		char* timeZoneName, const int timeZoneNameLength)

	int hec_dss_tsStoreRegular(dss_file* dss, const char* pathname,
		const char* startDate, const char* startTime,
		double* valueArray, const int valueArraySize,
		int* qualityArray, const int qualityArraySize,
		const int saveAsFloat,
		const char* units, const char* type, const char* timeZoneName, int storageFlag)

	int hec_dss_tsStoreIregular(dss_file* dss, const char* pathname,
		const char* startDateBase,
		int* times, const int timeGranularitySeconds,
		double* valueArray, const int valueArraySize,
		int* qualityArray, const int qualityArraySize,
		const int saveAsFloat,
		const char* units, const char* type, const char* timeZoneName, int storageFlag)

	# [paired]
	int hec_dss_pdRetrieveInfo(dss_file* dss, const char* pathname,
		int* numberOrdinates, int* numberCurves,
		char* unitsIndependent, const int unitsIndependentLength,
		char* unitsDependent, const int unitsDependentLength,
		char* typeIndependent, const int typeIndependentLength,
		char* typeDependent, const int typeDependentLength,
		int* labelsLength)

	int hec_dss_pdRetrieve(dss_file* dss, const char* pathname,
		double* doubleOrdinates, const int doubleOrdinatesLength,
		double* doubleValues, const int doubleValuesLength,
		int* numberOrdinates, int* numberCurves,
		char* unitsIndependent, const int unitsIndependentLength,
		char* typeIndependent, const int typeIndependentLength,
		char* unitsDependent, const int unitsDependentLength,
		char* typeDependent, const int typeDependentLength,
		char* labels, const int labelsLength,
		char* timeZoneName, const int timeZoneNameLength)

	int hec_dss_pdStore(dss_file* dss, const char* pathname,
		double* doubleOrdinates, const int doubleOrdinatesLength,
		double* doubleValues, const int doubleValuesLength,
		const int numberOrdinates, const int numberCurves,
		const char* unitsIndependent, const char* typeIndependent,
		const char* unitsDependent, const char* typeDependent,
		const char* labels, const int labelsLength,
		const char* timeZoneName)

	# [gridded]
	int hec_dss_gridRetrieve(dss_file* dss, const char* pathname, int boolRetrieveData,
		int* type, int* dataType,
		int* lowerLeftCellX, int* lowerLeftCellY,
		int* numberOfCellsX, int* numberOfCellsY,
		int* numberOfRanges, int* srsDefinitionType,
		int* timeZoneRawOffset, int* isInterval,
		int* isTimeStamped,
		char* dataUnits, const int dataUnitsLength,
		char* dataSource, const int dataSourceLength,
		char* srsName, const int srsNameLength,
		char* srsDefinition, const int srsDefinitionLength,
		char* timeZoneID, const int timeZoneIDLength,
		float* cellSize, float* xCoordOfGridCellZero,
		float* yCoordOfGridCellZero, float* nullValue,
		float* maxDataValue, float* minDataValue,
		float* meanDataValue,
		float* rangeLimitTable, const int rangeTablesLength,
		int* numberEqualOrExceedingRangeLimit,
		float* data, const int dataLength)

	int hec_dss_gridStore(dss_file* dss, const char* pathname,
		const int gridType, const int dataType,
		const int lowerLeftCellX, const int lowerLeftCellY,
		const int numberOfCellsX, const int numberOfCellsY,
		const int numberOfRanges, const int srsDefinitionType,
		const int timeZoneRawOffset, int isInterval,
		const int isTimeStamped,
		const int compressionSize,
		const char* dataUnits, const char* dataSource,
		const char* srsName, const char* srsDefinition,
		const char* timeZoneID,
		const float cellSize, const float xCoordOfGridCellZero,
		const float yCoordOfGridCellZero, const float nullValue,
		const float maxDataValue, const float minDataValue,
		const float meanDataValue,
		float* rangeLimitTable,
		int* numberEqualOrExceedingRangeLimit,
		float* data)
