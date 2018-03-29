#!/bin/bash
#delete volumes - by supplied file
vols_file=vols.txt
if ! [[ -f $vols_file ]] ; then
    echo "unable to find vols_file: $vols_file"
    exit
fi
for v in `cat $vols_file` ; do aws ec2 delete-volume --volume-id $v; done
