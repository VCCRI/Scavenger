#!/bin/bash
#
# wrapper script for running jobs on the AWS EC2 instances 
# - adds some logging to S3 for start & finish of job
#

#colours; need to use -e option with echo
red='\e[0;31m'
cyan='\e[0;36m'
green='\e[0;32m'
yellow='\e[1;33m'
purple='\e[0;35m'
nc='\e[0m' #no colour

# add some default values for s3 - temp code
log_file="UNKNOWN" 

# print status message
print_status() {
    echo -e "${yellow}STATUS<$0>: ${cyan}${1}${nc}"
}

# function to write error file to s3
script_fail() {
    print_status "${red}${0}Script execution failed ${cyan}${1}${nc}"
    timestamp=`date`
    contents="[time]\nstart=$timestamp\ninfo=$1\n"
    ./s3-log.sh $bucket $s3_results $region ${log_file}-failed.log "$contents"
    exit 1
}

# helper script to check status of script after execution
check_status_script() {
    if [[ $? -ne 0 ]] ; then
        script_fail "$1"
    fi
}

# usage is not currently used
#program usage
usage() {
    echo -e "${red}$0 program exited due to invalid usage${nc}"
    exit 1
}

#checks latest return status 
#accepts one argument - name of program call
check_status() {
    if [ $? -ne 0 ] ; then
        echo -e "${red}$0 program exited due to unsuccessful excecution: ${cyan}${1}${nc}"
        script_fail
    fi
}

#function to exit program with message
exit_msg() {
    echo -e "${red}<$0> exiting program: ${cyan}${1}${nc}"
    #TODO - should log failure message to s3
    exit 1
}

# function to get argument value given argument key
# e.g. args could be "val1 val2 --opt1 val3" & option = "--opt1"
# in this case, the return value should be "val3"
get_arg() {
    args=$1
    option=$2
    get_val=false
    for val in $args ; do
        if $get_val ; then
            echo $val
            return
        else
            if [[ $val == $option ]] ; then
                get_val=true
            fi
        fi
    done
    # if we get to here then - unable to find option or its value
}

# gets the value of an argument - that may contain spaces
# Assumes args start with --
get_arg_with_spaces() {
    args="$1"
    option="$2"
    str="${args##*${option} }"
    echo "${str%% --*}"
}

# separate the file name from any path
get_file_name() {
    awk 'BEGIN {FS="/"} {print $NF}' <<< $1
}

# get path without file name
get_path_only() {
    # deletes last field (i.e. the file name)
    # will leave any trailing "/"
    awk 'BEGIN {FS="/";OFS="/"}; {$NF=""; print $0}' <<< $1
}

# should take script to wrap as $1
# s3 bucket as $2
# s3 results as $3
# region as $4
# log file name as $5
# extra as $6
# NOTE that these arguments are passes as purely positional -
# i.e. NOT like: --script <script>
i=1
extra=""
script=""
bucket=""
s3_results=""
region=""
log_file=""
while [[ $# > 0 ]] ; do
    case $i in
        1)
            script=$1
            i=$(($i + 1))
            shift
            ;;
        2)
            bucket=$1
            i=$(($i + 1))
            shift
            ;;
        3)
            s3_results=$1
            i=$(($i + 1))
            shift
            ;;
        4)
            region=$1
            i=$(($i + 1))
            shift
            ;;
        5)
            log_file=$1
            i=$(($i + 1))
            shift
            ;;
        *)
            #concatinates all the rest of the arguments into one variable
            extra="${@}"
            i=0
            break
            ;;
    esac  

done

echo "************* <wrapper.sh ********************"
echo "script bucket results region log_file: $script, $bucket, $s3_results, $region, $log_file"
echo "extra: $extra"
echo "************* >wrapper.sh ********************"

LATEST_VCF_FILE_PATH=latest-vcf-file-path.txt
sam_location_file=latest-sam-align-only.txt

# determine if this is a rescue run - log_file label will start with "fastq"
# example of log_file label: 04102017Wed-4/fastq-2-i-0
IS_PIPE_RUN=false
label=${log_file##*/}
if [ ${label:0:5} == "fastq" ] ; then
    IS_PIPE_RUN=true
    # want to extract just the fastq label - e.g. fastq-1
    tmp=${label#*-} # remove the "fastq-" from the beginning
    num=${tmp%%-*}  # remove everything from the first "-"
    fastq_label=fastq-$num
    # get just the run id (e.g. 04102017Wed-4)
    run_id=${log_file%%/*}
fi

# change to the directory in which this file resides
# $0 is name of program file including path used to execute
# will be of form /some/path/wrapper.sh
# the sed command extracts the path  from the file name
base_dir=`sed -r 's/(.*\/).*/\1/' <<< $0`
cd $base_dir

# separate the file name from any path
#log_file_name=`awk 'BEGIN {FS="/"} {print $NF}' <<< $log_file`-output.log
base_log_file_name=`get_file_name $log_file`-output
log_file_name=${base_log_file_name}.log

if $IS_PIPE_RUN ; then
    # copy fastq file(s) from s3 to this instance
    fastq1=$( get_arg "$extra" "--fastq1" ) 
    fastq2=$( get_arg "$extra" "--fastq2" ) 
    fastq_s3_bucket=$( get_arg "$extra" "--fastq_s3_bucket" ) 
    fastq_s3_region=$( get_arg "$extra" "--fastq_s3_region" ) 
    fastq_s3_bucket_dir=$( get_arg "$extra" "--fastq_s3_bucket_dir" ) 
    fastq_s3_local_dir=$( get_arg "$extra" "--fastq_s3_local_dir" ) 
    output_dir=$( get_arg "$extra" "--output_dir" )
    output_dir=$output_dir/$run_id/$fastq_label
    run_args=$( get_arg_with_spaces "$extra" "--run_args" )
    if [ "$fastq1" != "" ] ; then
        # copy fastq file 
        aws s3 cp s3://$fastq_s3_bucket/$fastq_s3_bucket_dir/$fastq1 $fastq_s3_local_dir --region $fastq_s3_region
        if [[ $? -ne 0 ]] ; then
            script_fail "Exiting program - unable to copy fastq1 file from s3 to local instance."
        fi
        # if fastq has .gz extension, then unzip it 
        if [ "${fastq1: -3}" == ".gz" ] ; then
            # check that not previous version of file already unzipped
            unzipped=${fastq1:0:${#fastq1}-3}
            unzip_fp=$fastq_s3_local_dir/$unzipped 
            if [ -f $unzip_fp ] ; then
                rm $unzip_fp
            fi
            gunzip $fastq_s3_local_dir/$fastq1
            if [[ $? -ne 0 ]] ; then
                script_fail "Exiting program - unable unzip fastq1 file: $fastq1"
            fi
            # remove the .gz from the end of the filename
            fastq1=${fastq1:0:${#fastq1}-3}
        fi
    else
        script_fail "Exiting program - no fastq1 file specified"
    fi    
    if [ "$fastq2" != "" ] ; then
        aws s3 cp s3://$fastq_s3_bucket/$fastq_s3_bucket_dir/$fastq2 $fastq_s3_local_dir --region $fastq_s3_region
        if [[ $? -ne 0 ]] ; then
            script_fail "Exiting program - unable to copy fastq2 file from s3 to local instance."
        fi
        # if fastq has .gz extension, then unzip it 
        if [ "${fastq2: -3}" == ".gz" ] ; then
            # check that not previous version of file already unzipped
            unzipped=${fastq2:0:${#fastq2}-3}
            unzip_fp=$fastq_s3_local_dir/$unzipped 
            if [ -f $unzip_fp ] ; then
                rm $unzip_fp
            fi
            gunzip $fastq_s3_local_dir/$fastq2
            if [[ $? -ne 0 ]] ; then
                script_fail "Exiting program - unable unzip fastq2 file: $fastq2"
            fi
            # remove the .gz from the end of the filename
            fastq2=$unzipped
        fi
    fi
    # create subdirectory for output
    # e.g. output_dir=/mnt1/output & run_id=04102017Wed-4
    mkdir -p $output_dir/$run_id
    # run the pipeline

    # if PE, then need to separate the two fastq files with a space
    fastq="$fastq_s3_local_dir/$fastq1"
    if [ "fastq2" != "" ] ; then
        fastq="${fastq} $fastq_s3_local_dir/$fastq2"
    fi
    echo "python3 rescue_reads.py -i $fastq $run_args"
    python3 rescue_reads.py -i $fastq_s3_local_dir/$fastq1 -o $output_dir $run_args
    if [[ $? -ne 0 ]] ; then
        script_fail "Exiting program - pipeline execution failed."
    fi

else
    # not a pipeline run - e.g. could be unrelated script - 
    # like copy-s3.py
    # log start time
    timestamp=$( date )
    contents="[time]\nstart=$timestamp\n"
    # log start time to s3
    ./s3-log.sh $bucket $s3_results $region ${log_file}-start.log "$contents"
    if [[ $? -ne 0 ]] ; then
        echo "Exiting program - unable to log to s3"
        exit
    fi
fi

result=$?
./s3-log-file.sh $bucket $s3_results $region ${log_file}-output.log

# if pipeline run, copy results to s3
##TODO - comment & what to do in case of error
if $IS_PIPE_RUN ; then
    for f in $output_dir/*.log $output_dir/*rescued.sam ; do
        aws s3 cp $f s3://$bucket/$s3_results/$run_id/output/ --region $region
    done
fi

# log finish to s3
timestamp=$( date )
contents="[time]\nfinish=$timestamp\n[script]\nreturn=$result\n"
./s3-log.sh $bucket $s3_results $region ${log_file}-finish.log "$contents"

