#!/usr/bin/env python3
import os, sys
import argparse

# run from a clone without installing: use the repo's in-place build
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.isfile(os.path.join(REPO, "pyheclib", "__init__.py")):
    sys.path.insert(0, REPO)
import numpy as np
import pyheclib as phl


def main(filename, pathname, out_csv):

    if not os.path.exists(filename):
        print("File doesnt exists.")
        return

    with phl.open(filename) as dss_file:
        record = dss_file.read(pathname)

    if isinstance(record, phl.GriddedData):
        np.savetxt(out_csv, record.data, delimiter=",")
    elif isinstance(record, phl.PairedData):
        record.to_dataframe().to_csv(out_csv)
    else:
        record.to_series().to_csv(out_csv)


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="write a dss record to csv")
    parser.add_argument("filename")
    parser.add_argument("pathname", help="record pathname, empty D part reads whole time series")
    parser.add_argument("out_csv")
    args = parser.parse_args()

    main(args.filename, args.pathname, args.out_csv)
