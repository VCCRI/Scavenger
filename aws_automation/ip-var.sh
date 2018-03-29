#!/bin/bash
#assign ip addresses to variables
# useful for working at command line to have
# aliases to all the ip addresses & security key
j=0
# temporary file name - will be removed
f=tmp-ip-var.txt
# this loop reads in lines from the file that keeps the ip addresses
# each line is a single ip address - read into variable addr
# Each address is assigned to a variable ip0, ip1, etc
while read addr
do
    if [[ $j -eq 0 ]] ; then
        echo "ip$j=$addr" > $f
    else
        echo "ip$j=$addr" >> $f
    fi

    if [[ $? -ne 0 ]] ; then
        echo "error"
        exit
    fi
    j=$(($j+1))
    #TODO get ipaddrs text file name from configuration
done < info/ipaddrs.txt
# source the temporary file to set up the variable assignments
source $f
# remove temporary file
rm $f
# variable for security key
pem=$( system/get-security-key.sh )
if [[ $? -ne 0 ]] ; then
    echo "Error getting security key"
fi
