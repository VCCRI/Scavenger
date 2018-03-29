#!/bin/bash
#copies local file to specified remote destination

#colours; need to use -e option with echo
red=$( tput setaf 1 )
cyan=$( tput setaf 6 )
green=$( tput setaf 2 )
yellow=$( tput setaf 3 )
purple=$( tput setaf 5 )
nc=$( tput sgr0 )

#program usage
usage() {
   echo -e "${yellow}usage: ${purple}$0 ${cyan}<pem> <ip> <local> <remote>${nc}"
   exit
}


#checks latest return status 
#accepts one argument - name of program call
check_status() {
    if [ $? -ne 0 ] ; then
        echo -e "${red}program exited due to unsuccessful excecution: ${cyan}${1}${nc}"
        exit
    fi
}

#function to exit program with message
exit_msg() {
    echo -e "${red}exiting program: ${cyan}${1}${nc}"
    exit
}

if [[ $# -ne 4 ]] ; then
    usage
fi 

pem=$1
ip=$2
loc="$3"
rem="$4"

if [[ $loc == "" && $rem == "" ]] ; then
    exit_msg "no action specified"
fi

##local_files=~/taas-sw/install-pipeline.sh
#local_files=~/taas-sw/my-pipeline.sh
#other_files=~/taas-sw/run-*.sh
#more_files=prep-ssd.sh
#remote_dest=taas-sw
##note option to prevent user input to accept unknown host
#scp -o StrictHostKeyChecking=no -i $pem $local_files ec2-user@$ip:$remote_dest
#scp -o StrictHostKeyChecking=no -i $pem $other_files ec2-user@$ip:$remote_dest
#scp -o StrictHostKeyChecking=no -i $pem $more_files ec2-user@$ip:$remote_dest
scp -q -o StrictHostKeyChecking=no -i $pem $loc ec2-user@$ip:$rem
check_status "scp from:<$loc>; to:<$rem>"
#echo -e "${yellow}STATUS: ${green}scp successful${nc}"
