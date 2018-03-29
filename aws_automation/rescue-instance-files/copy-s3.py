"""
    copy-s3.py

    copy data from AWS S3 buckets to specific local directories as specified
    by the rescue configuration file
    assumes:
      (1) bucket path without trailing file separator
      (2) destination path without trailing file separator
      (3) this file is called by wrapper.sh - which changes to the 
          expected working directory before calling this file
      (4) the configuration file and constants file are available
          on the local instance

    errors in accessing the configuration file or transferring a file
    should cause this program to terminate, returning a non-zero status
 
"""

import configparser
import boto3
from botocore.exceptions import ClientError
from boto3.s3.transfer import S3Transfer
import os
import sys

# local import
import constants as CONST

def print_transfer_details(bucket, key, local_path):
    """ prints details about a file transfer
    
    Args:
        bucket:     string      name of s3 bucket
        key:        string      key of file in bucket (path)
        local_path  string      path of local destination

    Returns:
        (no return value)
    """
    print('file transfer:')
    # the formatting here indents & right justifies the sub-
    # headings
    print("{:>14s}".format('bucket:'),bucket)
    print("{:>14s}".format('key:'),key)
    print("{:>14s}".format('local dir:'),local_path)
    print('')

def terminate_with_error():
    print('Exiting program')
    sys.exit(1)
    
print('Starting', sys.argv[0], 
        'to copy files from AWS S3 buckets to local instance')
# create a configparser object
config = configparser.ConfigParser()
# read in the configuration file - exit if error
cfg = []
try:
    cfg = config.read(CONST.CONFIG_FILE)
except:
    print('Error reading configuration file:', CONST.CONFIG_FILE)
    terminate_with_error()
# note that config.read will not throw an error for a non-existant file
if not cfg:
    print('Non-existant configuration file?:', CONST.CONFIG_FILE)
    terminate_with_error()

# count the number of files transferred
count = 0
for key in config.keys():
    # there is a separate section in the configuration file for files
    # located in each unique s3 bucket "directory" / local directory
    # combination
    if key.startswith(CONST.CONFIG_SECTION_COPY_S3):
        # the configuration file allows for different buckets/regions
        region = config[key][CONST.CONFIG_VAL_COPY_S3_REGION]
        client = boto3.client('s3', region_name=region)
        transfer = S3Transfer(client)
        # the source s3 bucket - assumes this user has rights to download
        bucket = config[key][CONST.CONFIG_VAL_COPY_S3_BUCKET]
        # get bucket dir
        bucket_dir = config[key][CONST.CONFIG_VAL_COPY_S3_BUCKET_DIR]
        # local dir to which s3 bucket files are downloaded
        dest_dir = config[key][CONST.CONFIG_VAL_COPY_S3_LOCAL_DIR]
        # get the list of s3 bucket files to copy
        files = config[key][CONST.CONFIG_VAL_COPY_S3_FILES].split('\n')
        # create local destinatin dir if not exist
        os.makedirs(dest_dir, exist_ok=True)
        # copy the files from s3 to local directory
        for file in files:
            file_key = bucket_dir + '/' + file
            local_path = dest_dir + '/' + file
            # attempt the file transfer & handle error case
            try:
                transfer.download_file(bucket, file_key, local_path)
            except:
                print('The following file transfer failed:')
                print_transfer_details(bucket, file_key, local_path)
                terminate_with_error()
            # update count of successful file downloads
            count +=1
            # print out the files transferred - makes is easier
            # to troubleshoot in the case of failed transfers
            print_transfer_details(bucket, file_key, local_path)

# print status message to finish
print('Finished copying', count , 
    'files downloaded from AWS S3 to local instance')

