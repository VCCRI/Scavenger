#!/bin/bash
#describe instances - filtered for my security group
#only prints out instance id
if [[ ($# -gt 0) && ($1 == '-v') ]] ; then
    aws ec2 describe-instances --query 'Reservations[*].Instances[*].[State.Name, InstanceId, SecurityGroups[0].GroupName, PublicDnsName]'|grep "mictro"
else
    aws ec2 describe-instances --query 'Reservations[*].Instances[*].[InstanceId, SecurityGroups[0].GroupName]'|grep "mictro"|awk '{print $1}'
fi
