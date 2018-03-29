#!/bin/bash
###############################################################################
#                                                                             #
# creates aws instances based on supplied ami configuration                   #
#                                                                             #
# Also waits until the instances are ready, then prints out the instance id's,#
# the ip addresses, and the time taken to create the instances                #
#                                                                             #
# if --dry-run option is used, the program with exit with an error            #
# describing if command would have been successful                            #
#                                                                             #
###############################################################################

# output format for aws commands - can be either text, json, or tabular
aws_output_format=text

# assumes python3 is normal mapping (not a special path value)
# location of python3 executable
python3=$( system/get-python-path.sh )

# get a constant vaue from the python constants file used for this app
get_constant_value() {
    echo "$( $python3 constants.py $1 )"
}

#colours; need to use -e option with echo
red=$( tput setaf 1 )
cyan=$( tput setaf 6 )
green=$( tput setaf 2 )
yellow=$( tput setaf 3 )
purple=$( tput setaf 5 )
nc=$( tput sgr0 )

#program usage
usage() {
    echo -e "${red}program exited due to invalid usage${nc}"
    echo -e "${yellow}usage:${purple} $0 ${cyan}--instance-type <type> \
        <count> [[--instance-type <type> <count>]...] \
        [--user-data <value>] [--dry-run]${nc}"
    echo -e "${yellow}Example:${nc}"
    echo -e "$0 --instance-type r3.large 1 --user-data some-file.sh --dry-run"
    echo -e "${yellow}Valid instance types:${cyan}"
    cat `get_constant_value INSTANCE_TYPES`
    echo -e "${nc}"
    exit 1
}

#checks latest return status 
#accepts one argument - name of program call
check_status() {
    if [ $? -ne 0 ] ; then
        echo -e "${red}ERROR: ${yellow}program exited due to unsuccessful excecution: \
            ${cyan}${1}${nc}"
        exit 1
    fi
}

#checks program usage: assumes 1 parameter: modify as necessary
if [ $# -lt 3 ] ; then
    usage
fi

#function to exit program with message
exit_msg() {
    echo -e "${red}Exiting program: ${cyan}${1}${nc}"
    exit 1
}

#TODO should strip any leading or trailing spaces from parameters
add_instance_type() {
    instance_type=$1
    count=$2
    #check for valid instance type
    result=`grep -E "\|$instance_type\|" $instance_types_file`
    if [[ $? != 0 ]] ; then
        exit_msg "Invalid instance type: $instance_type"
    fi
    #check for valid number format & range for # of instances
    if ! [[ $count =~ ^[1-9][0-9]?$ ]] ; then
        exit_msg "Invalid count for number of instances in parameter: $count"
    fi
    #have valid parameters - add to file
    echo "$instance_type $count" >> $instance_parms
}

#remove any previous parameters file
instance_parms=`get_constant_value INSTANCE_PARMS`
if [[ -f $instance_parms ]] ; then
    rm $instance_parms
fi

#remove any previous running_inst_types_file
running_inst_types_file=`get_constant_value RUNNNING_INSTANCE_TYPES_FILE`
if [[ -f $running_inst_types_file ]] ; then
    rm $running_inst_types_file
fi

#check that file exists that lists valid instance types
instance_types_file=`get_constant_value INSTANCE_TYPES`
if ! [[ -f $instance_types_file ]] ; then
    exit_msg "Can't find file: $instance_types_file  (Required)"
fi

#get options - minimum one set of --instance-type
user_data=""
dry_run=""
use_spot=""
spot_price=""
availability_zone=""
image_id=""
security_key=""
security_groups=""
security_group_id=""
profile_name=""
arn_id=""
instance_name=""
while [[ $# > 0 ]]
do
    arg="$1"

    case $arg in
        --availability-zone)
            availability_zone="$2"
            shift
            shift
            ;;
        --instance-type)
            add_instance_type $2 $3
            shift # past argument
            shift
            shift
            ;;
        --user-data)
            user_data="$2"
            shift
            shift
            ;;
        --dry-run)
            dry_run="--dry-run"
            shift
            ;;
        --use-spot-instances)
            use_spot=$2
            shift
            shift
            ;;
        --spot-price)
            spot_price=$2
            shift
            shift
            ;;
        --image-id)
            image_id=$2
            shift
            shift
            ;;
        --security-key)
            security_key=$2
            shift
            shift
            ;;
        --security-groups)
            security_groups=$2
            shift
            shift
            ;;
        --security-group-id)
            security_group_id=$2
            shift
            shift
            ;;
        --profile-name)
            profile_name=$2
            shift
            shift
            ;;
        --arn-id)
            arn_id=$2
            shift
            shift
            ;;
        --instance-name)
            instance_name=$2
            shift
            shift
            ;;
        *)
            # unknown option - exit program
            usage
            ;;
    esac
done
if [[ $user_data != "" ]] ; then
    # need original user_data file string for spot instances
    user_data_file=$user_data
    #assumes user-data is like: <path to file>
    user_data="--user-data file://$user_data"
fi
# if using spot - only allow one instance type
if [[ $use_spot == "1" &&  \
    `wc -l $instance_parms|awk '{print $1}'` -ne 1 ]] ; then
    exit_msg "Only one instance type allowed for spot instances"
fi

# remove old instance id file
ids_file=`get_constant_value INSTANCE_IDS`
if [[ -f $ids_file ]] ; then
    rm $ids_file
fi

# file to hold instance public ip addresses
ips_file=`get_constant_value INSTANCE_IPS_FILE`
if [[ -f $ips_file ]] ; then
    rm $ips_file
fi

# file to hold spot instance request ids
spot_request_ids_file=`get_constant_value SPOT_REQUEST_IDS`
if [[ -f $spot_request_ids_file ]] ; then
    rm $spot_request_ids_file
fi

#create the instances that were requested
start=`date +%s` #seconds since epoc
#loop through the instance_parms file to create the requested # of instances
#for each type
while read instance_type count ; do
    # at this stage, assuming that $user_data only applies to ssd settings
    # ; to start with, assume that only r3 types allow ssd
    tmp=$user_data
    # determine if we can configure ssd on instance
    #TODO - is this correct "== !(...)"??
    if [[ $instance_type == !(r3*) && $instance_type == !(c3*) ]] ; then
        # aws instance type is not r3... & not c3... - no ssd
        user_data=""
    else
        # spot instances use a different way to process user_data
        if [[ $use_spot == "1" ]] ; then
            # create base64 code for user data
            # NOTE difference in base64 between mac platform & other linux
            # mac base64 uses -b option iso -w option
            op="-w"
            v=$( man base64 | grep '\-w' )
            [ $? -ne 0 ] && op="-b"
            user_data_base64=$( base64 $op 0 $user_data_file )
        fi
    fi
    if [[ $use_spot == "1" ]] ; then
        #TODO - set up for c3.8xlarge type (has 2x ssd)
        # note that r3 instance types don't auto mount their ssd's
        # whereas other types, such as c3, automount first ssd

        # spot instances - assumes all the one instance type
        aws ec2 request-spot-instances \
            --spot-price $spot_price \
            --output $aws_output_format \
            --instance-count $count \
            --type "one-time" \
            --launch-specification \
            "{ \
                \"ImageId\": \"$image_id\", \
                \"KeyName\": \"$security_key\", \
                \"SecurityGroupIds\": [ \"$security_group_id\" ], \
                \"InstanceType\": \"$instance_type\", \
                \"UserData\": \"$user_data_base64\", \
                \"Placement\": { \
                    \"AvailabilityZone\": \"$availability_zone\" \
                }, \
                \"BlockDeviceMappings\": [ \
                    { \
                        \"DeviceName\": \"/dev/sdb\", \
                        \"VirtualName\": \"ephemeral0\" \
                    }, \
                    { \
                        \"DeviceName\": \"/dev/sdc\", \
                        \"VirtualName\": \"ephemeral1\" \
                    } \
                ], \
                \"IamInstanceProfile\": { \
                    \"Arn\": \"$arn_id\" \
                } \
            }" \
            --query 'SpotInstanceRequests[*].SpotInstanceRequestId' > \
            $spot_request_ids_file
        if [[ $? -ne 0 ]] ; then
            exit_msg "spot request command failed"
        fi
        echo -e "${yellow}STATUS: ${green}Waiting for spot requests to be fulfilled${nc}"
        while (true) ; do
            sleep 10
            fulfilled=0
            for request_id in `cat $spot_request_ids_file` ; do
                # the effect of this look is to count the # of fulfilled 
                # spot requests
                fulfilled=$((`aws ec2 describe-spot-instance-requests \
                            --output $aws_output_format \
                            --spot-instance-request-ids $request_id \
                            --query "SpotInstanceRequests[*].Status.Code" \
                            |grep "fulfilled"|wc -l|awk '{print $1}'` + \
                            $fulfilled))
            done
            if [[ $fulfilled -eq $count ]] ; then
                # record instance_ids
                for request_id in `cat $spot_request_ids_file` ; do
                    aws ec2 describe-spot-instance-requests \
                        --spot-instance-request-ids $request_id \
                        --output $aws_output_format \
                        --query "SpotInstanceRequests[*].InstanceId" >> \
                        $ids_file
                done
                break
            fi
        done
        echo -e "${yellow}STATUS: ${green}All spot requests have been fulfilled${nc}"
    else
        # on demand instances
        aws ec2 run-instances \
            --image-id $image_id \
            --count $count \
            --output $aws_output_format \
            --instance-type $instance_type \
            --key-name $security_key \
            --security-groups $security_groups \
            --iam-instance-profile Name=$profile_name $dry_run $user_data \
            --query 'Instances[*].InstanceId' >> $ids_file
        check_status "run-instances"
    fi
    user_data=$tmp
done < $instance_parms
all_done=true
#wait a minute for the instances to start running
sleep 60
#start an infinite loop to check when instances are running
while true; do
    all_done=true
    #check the run state of each instance id that was created
    if [[ -f $ips_file ]] ; then
        rm -f $ips_file
    fi
    for id in `cat $ids_file`; do
        #check the instance reachability status - when "passed" 
        #should be ok to use
        instance_details_name=`aws ec2 describe-instance-status \
            --instance-ids $id \
            --output $aws_output_format \
            --query \ 'InstanceStatuses[0].InstanceStatus.Details[0].Name'`
        instance_details_status=`aws ec2 describe-instance-status \
            --instance-ids $id \
            --output $aws_output_format \
            --query \ 'InstanceStatuses[0].InstanceStatus.Details[0].Status'`
        if ! [[ ("$instance_details_name" == "reachability") &&
           ("$instance_details_status" == "passed") ]] ; then
            all_done=false
            #this instance is not ready
            break
        fi
        ipaddr=`aws ec2 describe-instances --instance-ids $id \
            --output $aws_output_format \
            --query 'Reservations[0].Instances[0].PublicDnsName'`
        inst_type=`aws ec2 describe-instances --instance-ids $id \
            --output $aws_output_format \
            --query 'Reservations[0].Instances[0].InstanceType'`
        echo $ipaddr >> $ips_file
        echo $inst_type >> $running_inst_types_file
    done
    if ! $all_done ; then
        sleep 10
    else
        break
    fi
done
# name the instances - updates the tag "Name" for each instance
# instance_name is passed in as an argument
i=0
while read id ; do
    aws ec2 create-tags --resources $id --tags Key=Name,Value="${instance_name}-$i"
    ((++i))
done < $ids_file

# want to check if instance has been fully configured
