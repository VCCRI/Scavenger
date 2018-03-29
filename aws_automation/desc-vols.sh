#!/bin/bash
#describe volumes
aws ec2 describe-volumes --query 'Volumes[*].[VolumeId, Attachments[0].InstanceId, Size, CreateTime]'
