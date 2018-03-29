#!/bin/bash
#terminates instances in instance-ids.txt file
ids_file=info/instance-ids.txt
if ! [[ -f $ids_file ]] ; then
    echo "couldn't find ids_file: $ids_file"
    exit
fi
for i in $( cat $ids_file ) ; do
    aws ec2 terminate-instances --instance-ids $i
done
