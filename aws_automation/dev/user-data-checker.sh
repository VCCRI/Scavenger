#!/bin/bash
while true ; do
    ls /home/ec2-user/USER-DATA.TXT
    if [ $? -ne 0 ] ; then
        sleep 10
    else
        break
    fi
done
