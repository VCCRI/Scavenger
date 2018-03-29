#!/bin/bash
# create dir & give rights 
#intended for use on aws - with ssd drive
#usage: ./create... <dirname>
if [[ $# -ne 1 ]] ; then
    echo "usage: $0 <dirname>"
    exit
fi
dir=$1

sudo mkdir $dir
sudo chmod g+rwx $dir
sudo chgrp ec2-user $dir
sudo chown ec2-user $dir
