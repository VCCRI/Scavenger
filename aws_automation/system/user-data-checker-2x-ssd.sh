#!/bin/bash
#
# checks that the user-data script was successful 
#                                                

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
    echo -e "${yellow}usage:${purple} $0 ${cyan}<parm 1>${nc}"
    exit 1
}

#checks latest return status 
#accepts one argument - name of program call
check_status() {
    if [ $? -ne 0 ] ; then
        echo -e "${red}program exited due to unsuccessful excecution: ${cyan}${1}${nc}"
        exit 1
    fi
}

#function to exit program with message
exit_msg() {
    echo -e "${red}exiting program: ${cyan}${1}${nc}"
    exit 1
}

#echo -e "${yellow}STATUS: ${cyan}start user data checker...${nc}"

# add a delay to make sure instances ready
#TODO - some better way to do this? e.g. based on some sort of status??
sleep 60

ips_file=info/ipaddrs.txt
types_file=info/running-inst-types-file.txt
ssh_cmd=./ssh-cmd.sh

if ! [[ -f $ips_file ]] ; then
    exit_msg "user data check: unable to find ip address file: $ips_file"
fi
if ! [[ -f $types_file ]] ; then
    exit_msg "user data check: unable to find running instance types file: $types_file"
fi
# copy ips into an array
ips=( $( cat $ips_file ) )
# copy running types into an array
types=( $( cat $types_file ) )
num_inst=${#ips[*]}
i=0
while [[ $i -lt $num_inst ]] ; do
    if [[ ${types[$i]} == @(r3*) || ${types[$i]} == @(c3*) ]] ; then
        cmd="ls -las /mnt2/app/ && ls -las /mnt1/data"
    else
        cmd="ls -las /home/ec2-user/"
    fi
    # suppress the output - only concerned if it works
    $ssh_cmd ${ips[$i]} "$cmd" >/dev/null 2>&1
    check_status "user data check: $ip"
    i=$(($i + 1))
done
# now wait for "bootstrap" process to finish
echo -e "${yellow}STATUS: ${green}Instances accessible.  Waiting for configuration...${nc}"
while true ; do
    i=0
    all_done=true
    while [[ $i -lt $num_inst ]] ; do
        if [[ ${types[$i]} == @(r3*) || ${types[$i]} == @(c3*) ]] ; then
            cmd="ls -las /mnt2/app/BOOTSTRAP_SUCCESS"
        else
            cmd="ls -las /home/ec2-user/BOOTSTRAP_SUCCESS"
        fi
        # suppress the output - only concerned if it works
        $ssh_cmd ${ips[$i]} "$cmd" >/dev/null 2>&1
        if [ $? -ne 0 ] ; then
            all_done=false
            break
        fi
        i=$(($i + 1))
    done
    if $all_done ; then
        break
    fi
    sleep 10
done
# additional test
while [[ $i -lt $num_inst ]] ; do
    if [[ ${types[$i]} == @(r3*) || ${types[$i]} == @(c3*) ]] ; then
        cmd="python3 -c \"import pysam\""
        # suppress the output - only concerned if it works
        $ssh_cmd ${ips[$i]} "$cmd" >/dev/null 2>&1
        check_status "user data check: $ip"
    fi
    i=$(($i + 1))
done
echo -e "${yellow}STATUS: ${green}user data checker successful${nc}"
