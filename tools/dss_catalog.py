#!/usr/bin/env python3
import pyheclib as phl 
import os , sys
import argparse 


def main(filename):

    if not os.path.exists(filename):
        print("File doesnt exists.")
        return

    dss = phl.hecdss(filename)

    catalog = dss.catalog("")

    for i,cat in enumerate(catalog):
        print(f"{i:02d}:",cat)

    dss.close()
    



if __name__ == "__main__":

    
  
  
    main(sys.argv[1])

