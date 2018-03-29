#!/bin/bash
#create ssh session to an instance
#parameter is number of instance (starting at 0)
#assumes using aws linux image - hence username is ec2-user

if [[ $# -lt 1 ]] ; then
    echo "usage: $0 <instance number - starting from 0>"
    exit 1
fi
instance=$1
# check that it is a number
if ! [[ $instance =~ ^[0-9]+$ ]] ; then
    echo "usage: $0 <instance number - starting from 0>"
    exit 1
fi

# get security key name
security_key=$( system/get-security-key.sh )
# if there was an error, then exit
if [[ $? -ne 0 ]] ; then
    echo "$0: Exiting program.  Unable to get security key"
    exit 1
fi
# the instance ip addresses are stored in a file - read into array
ips_file=info/ipaddrs.txt
if ! [ -f "$ips_file" ] ; then
    echo "TERMINATING.  Could not open ips file: $ips_file"
    exit 1
fi
ips=( $(<$ips_file) )
if [ $instance -ge ${#ips[@]} ] ; then
    echo "TERMINATING.  Instance number out of range."
    exit 1
fi
ssh -o StrictHostKeyChecking=no -i ~/$security_key ec2-user@${ips[$instance]}
