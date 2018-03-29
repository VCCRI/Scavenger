#!/bin/bash
###############################################################################
#                                                                             #
# creates aws IAM role & profile so that instances are created with           # 
# temporary rights to do basic work with ec2 / s3 services                    #
# originaly designed so that instances can write to s3 for job control        #
# and reporting                                                               #
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
role_policy_doc=gpt-trust-policy-ec2.json
permit_name=gpt-permit-policy-ec2
permit_doc=gpt-permit-policy-ec2.json
profile_name=gpt-ec2-s3-bucket

print_status "starting to create instance profile..."
# create role - specifies what services the role is trusted to use
aws iam create-role --role-name $role_name --assume-role-policy-document file://$role_policy_doc
check_status "create role"
# add policy to role - specifies the permissions (what actions are allowed)
aws iam put-role-policy --role-name $role_name --policy-name $permit_name --policy-document file://$permit_doc
check_status "create role-policy"
# create instance profile
aws iam create-instance-profile --instance-profile-name $profile_name
check_status "create instance profile"
# attach role to profile
aws iam add-role-to-instance-profile --instance-profile-name $profile_name --role-name $role_name
check_status "attach role to profile"
print_status "${green}Successfully created instance profile"
