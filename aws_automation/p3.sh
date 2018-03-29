#!/bin/bash
#
#This script is a wrapper to run a python3 program in the python 3 environement
#were supporting programs are installed (e.g. boto3)
#
if [[ $# -lt 2 ]] ; then
    cmd="-V"
else
    cmd="$1"
fi
source /home/py3venv/bin/activate
python "$cmd"
deactivate
