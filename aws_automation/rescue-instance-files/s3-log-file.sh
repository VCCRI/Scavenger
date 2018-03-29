#!/bin/bash
# logs to s3 given an input string and file-name + other...
bucket=$1
results=$2
region=$3
log_file=$4
# separate the file name from any path
from_file=`awk 'BEGIN {FS="/"} {print $NF}' <<< $log_file`
aws s3 cp $from_file s3://$bucket/$results/$log_file --region $region
