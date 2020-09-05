#!/usr/bin/env bash
root="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"



if [ -f $root/pyheclib.*.so ]; then
    rm $root/pyheclib.*.so
fi

python3 setup.py build_ext --inplace

# remove dss

if [ -f $root/*.dss ]; then
    rm $root/pyheclib.*.so
fi


cp pyheclib.cpython-*linux-gnu.so tests/
cp pyheclib.cpython-*linux-gnu.so tools/