cdef extern from "zStructSpatialGrid.h":

	ctypedef struct zStructSpatialGrid:
		int structType;
		char *pathname;
		int _structVersion;
		int _type;  

		# Don't store but in the DSS 
		# int       _infoSize; 
		# int       _gridInfoSize; 

		int _version;

		# int       _verbose;
		# int       _startTime;
		# int       _endTime ;

		char* _dataUnits;
		int _dataType;
		char* _dataSource; # Needed for HRAP grids 
		int _lowerLeftCellX;
		int _lowerLeftCellY;
		int _numberOfCellsX;
		int _numberOfCellsY;
		float _cellSize;
		int _compressionMethod; #zlib for initial implementation
		int _sizeofCompressedElements;
		void* _compressionParameters;

		char* _srsName;
		# for now we're using WKT strings for the SRS definitions, but 
		# here's a placeholder for future options like proj4 or GML
		int _srsDefinitionType;
		char* _srsDefinition;
		float _xCoordOfGridCellZero;
		float _yCoordOfGridCellZero;
		float _nullValue;
		char* _timeZoneID;
		int _timeZoneRawOffset;
		int _isInterval; # Originally boolean 
		int _isTimeStamped; # Originally boolean
		int _numberOfRanges;


		# Actual Data
		int _storageDataType;
		void *_maxDataValue;
		void *_minDataValue;
		void *_meanDataValue;
		void *_rangeLimitTable;
		int *_numberEqualOrExceedingRangeLimit;
		void *_data;


	# spatial grid fuctions
	zStructSpatialGrid* zstructSpatialGridNew(const char* pathname)
	int zspatialGridRetrieve(long long *ifltab, zStructSpatialGrid *gdStruct, int boolRetrieveData)
	int zspatialGridStore(long long *ifltab, zStructSpatialGrid *gdStruct)



