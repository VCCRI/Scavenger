#!/bin/bash
# logs to s3 given an input string and file-name + other...
bucket=$1
results=$2
region=$3
log_file=$4
contents=$5
echo "$contents" > tmp_.txt
#\n passed in literally - convert to newline
# -i is to change file in-place
# -n is to suppress ouput
#TODO potential issue here if file contained a path with
# \n in it; potential solution is to change input to use {\n}
# as newline identifier - could even make this a parameter to pass to 
# target file (e.g NL={\n})
sed -in 's/\\n/\n/g' tmp_.txt
aws s3 cp tmp_.txt s3://$bucket/$results/$log_file --region $region
