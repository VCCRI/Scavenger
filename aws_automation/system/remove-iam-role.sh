#!/bin/bash
###############################################################################
#                                                                             #
# removes role, policy, etc 
#                                                                             #
# Author: mictro Aug 2015                                                     #
#                                                                             #
###############################################################################


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
    echo -e "${yellow}usage:${purple} $0${nc}"
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

# print status message
print_status() {
    echo -e "${yellow}STATUS: ${1}${nc}"
}

role_name=gpt-role-ec2
permit_name=gpt-permit-policy-ec2
permit_doc=gpt-permit-policy-ec2.json
profile_name=gpt-ec2-s3-bucket

print_status "starting to remove role, profile,..."
aws iam remove-role-from-instance-profile --instance-profile-name $profile_name --role-name $role_name
check_status "remove role from instance profile"
aws iam delete-role-policy --role-name $role_name --policy-name $permit_name
check_status "delete role policy"
aws iam delete-role --role-name $role_name
check_status "delete role"
aws iam delete-instance-profile --instance-profile-name $profile_name
check_status "delete instance profile"
print_status "${green}Successfully removed role & associated objects"
