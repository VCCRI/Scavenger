#!/bin/bash
#create ssh session to an instance
#parameter is dns name or ip address of instance
#assumes using aws linux image - hence username is ec2-user

if [[ $# -lt 1 ]] ; then
    echo "usage: $0 <public dns name or ip address>"
    exit 1
fi
# get security key name
security_key=$( system/get-security-key.sh )
# if there was an error, then exit
if [[ $? -ne 0 ]] ; then
    echo "$0: Exiting program.  Unable to get security key"
    exit 1
fi

ssh -q -o StrictHostKeyChecking=no -i ~/$security_key ec2-user@$1 $2
