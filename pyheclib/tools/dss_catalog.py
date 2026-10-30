#!/usr/bin/env python3
import os
import argparse

import pyheclib as phl


def main(filename, search_path, condensed):

    if not os.path.exists(filename):
        print("File doesnt exists.")
        return

    with phl.open(filename) as dss_file:
        for i, (path, code) in enumerate(dss_file.catalog(search_path, condensed=condensed, with_types=True)):
            print(f"{i:02d}: [{code}]", path)


def cli():
    parser = argparse.ArgumentParser(description="list records of a dss file")
    parser.add_argument("filename")
    parser.add_argument("search_path", nargs="?", default="",
                        help="pathname filter with * wild characters")
    parser.add_argument("-c", "--condensed", action="store_true",
                        help="combine dated blocks of time series")
    args = parser.parse_args()

    main(args.filename, args.search_path, args.condensed)


if __name__ == "__main__":
    cli()
