#!/bin/bash
# get value from python constants file ; removes any comment at eol
# assumes; no spaces, ', ", #, = in path
# The name of the constant is PYTHON3_PATH
# Once we have the python executable location, we can use python
# to get the contant value from the python constants file

# first check if python3 mapping works
# don't want any errors printing to stdout
tmp=`python3 --version 2>/dev/null`
if [[ $? -eq 0 ]] ; then
    # normal python3 mapping
    python3=python3
else
    # some sort of non-standard python3 mapping (e.g. on exome01)
    const_file=constants.py
    python3=`awk -F "=" '/^PYTHON3_PATH[ \t]*=/ {print $2; exit}' $const_file|\
                tr -d " "\'\" | sed -r 's/#.*$//'`
    # default to python3
    if [[ $? != 0 ]] ; then
        python3=python3
    fi
fi
echo $python3
