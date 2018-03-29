#!/bin/bash
#creates vols.txt file for use with del-vols.sh
#separate file to make sure operator is confident they want to delete all these volumes
#-could have put in del-vols.txt, but risk is delete wanted volumes
#
./desc-vols.sh |awk '{print $1}' > vols.txt
