
''' ** heclib header defination imports ** '''

cdef extern from "heclib.h":
	cdef:
		int MESS_METHOD_OPEN
		int zSTRUCT_length
		int DATA_TYPE_RTS
		int DATA_TYPE_ITS
		int DATA_TYPE_PD
		int DATA_TYPE_SG

		int STATUS_OKAY
		int STATUS_NOT_OKAY
		int STATUS_NO_OP
		int STATUS_RECORD_FOUND
		int STATUS_RECORD_NOT_FOUND
		int STATUS_TRUE
		int STATUS_FALSE


		
	int  zopen  (long long *ifltab, const char *dssFilename)
	int  zopen6 (long long *ifltab, const char *dssFilename)
	int  zopen7 (long long *ifltab, const char *dssFilename)
	
	int zclose(long long *ifltab)

	# [struct]
	ctypedef struct zStructCatalog:

		int structType;
		int statusWanted;
		int typeWantedStart;
		int typeWantedEnd;
		long long lastWriteTimeSearch;
		int lastWriteTimeSearchFlag;
		char **pathnameList;
		int numberPathnames;
		int boolSorted;
		int boolIsCollection;
		int boolHasAttribues;
		char **attributes;
		int boolIncludeDates;
		int *startDates;
		int *endDates;
		int *recordType;
		long long *pathnameHash;
		long long *lastWriteTimeRecord;
		long long lastWriteTimeFile;
		unsigned int *crcValues;
		int boolGetCRCvalues;   
		int listSize; 
		long long *sortAddresses; 
		char *pathWithWildChars;  
		char allocated[25];
	#zstructcatalog
 
	
	int zgetVersion(long long *ifltab)
	# logging
	void zsetMessageLevel(int methodID, int levelID)


	# catelog
	zStructCatalog* zstructCatalogNew()
	int zcatalog(long long *ifltab, const char *pathWithWild, zStructCatalog *catStruct, int boolSorted)

	int zopenLog(const char *logFileName)


	# time to date conversion
	int getDateAndTime(int timeMinOrSec, int timeGranularitySeconds, int julianBaseDate,
				   char *dateString, int sizeOfDateString, char* hoursMins, int sizeofHoursMins)

	
	# dss version
	int zgetFullVersion(long long *ifltab)
	int zgetVersion(long long *ifltab)


	# logging
	int zset(const char* parameter, const char* charVal, int integerValue)

	# delete record


	# zcheck

	int zcheck(long long *ifltab, const char* pathname)

	# record type
	int zdataType (long long *ifltab, const char* pathname)


	# check data type
	int zdataType (long long *ifltab, const char* pathname)


	int zaliasGetPrimary(long long *ifltab, const char* aliasPathname, char* primayPathname, size_t maxLenPrimayPathname)


	int zreadInfo(long long *ifltab, const char *pathname, int statusWanted)

	int zcollectionCat(long long *ifltab, const char *seedPathname, zStructCatalog *catStruct)


	














