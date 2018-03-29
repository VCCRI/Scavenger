# a module that wraps some of the S3 commands
import boto3
from botocore.exceptions import ClientError
from boto3.s3.transfer import S3Transfer
import re
import os

# check for existance of bucket
def list_bucket(bucket_name, region):
    s3 = boto3.resource('s3', region)
    bucket = s3.Bucket(bucket_name)
    object_list = []
    try:
        for key in bucket.objects.all():
            print(key.key)
            object_list.append(key.key)
    except ClientError as e:
        #print('code: {}, msg: {}, op name: {}'.format([
        #    e.error_code, e.error_message, e.operation_name]))
        #print(e.msg)
        print(str(e))
        print(e.response)
    except Exception as e:
        # other response Error keys: Code, Message, BucketName
        print(e.response['Error']['Code'])
        print(str(e))
        print(e.response)
        print(e.response['ResponseMetadata']['HTTPStatusCode'])
    return object_list

# get list of bucket contents
def get_bucket_list(bucket_name, region):
    s3 = boto3.resource('s3', region)
    bucket = s3.Bucket(bucket_name)
    object_list = []
    for key in bucket.objects.all():
        object_list.append(key.key)
    return object_list

# check bucket exists (efficient version)
# NOTE: s3 bucket name space is for all AWS users
# therefore need to also check that have rights to read & write (+list)
def bucket_exists(bucket, region):
    s3 = boto3.resource('s3', region)
    exists = True
    try:
        s3.meta.client.head_bucket(Bucket=bucket)
    except ClientError as e:
        # If a client error is thrown, then check that it was a 404 error.
        # If it was a 404 error, then the bucket does not exist.
        error_code = int(e.response['Error']['Code'])
        if error_code == 404:
            exists = False
    return exists

#upload a file
def upload_file(bucket, region, source_file, dest_file):
    client = boto3.client('s3', region)
    transfer = S3Transfer(client)
    transfer.upload_file(source_file, bucket, dest_file)

# determine next unique number
def get_next_id(bucket_name, region, prefix):
    """
    determines the next sequential numbering for a given folder prefix

    e.g. prefix is "01092015Tue-"; if a file exists in the folder, then
    it will be of the form "01092015Tue-xxx/somefilename.ext" - where 
    xxx is some number"; if there is such a file, then next folder will
    be 01092015Tue-yyy - where yyy = xxx + 1; otherwise, next folder is
    01092015Tue-1

    Args:
        prefix: a string that represents the absolute folder name

        Returns: a string that represents the next folder name in the
        sequence
    """
    # added () to get group
    pattern = re.compile(prefix + '([0-9]+)/')
    ids = get_bucket_list(bucket_name, region)
    next_num = 1
    for name in ids:
        match = pattern.match(name)
        if match:
            # there is only one bracketed group - the number
            next_num = max(int(match.groups()[0]) + 1, next_num)
    result = prefix + str(next_num)
    # want to strip out any "directories" in path & just return id
    return result.split('/')[-1]
            
# return a list of bucket objects that match a given prefix
#TODO remove default bucket name
def list_by_prefix(bucket_name, region, prefix=''):
    """ returns a list of names of bucket objects that start with a 
    given prefix

    Args:
        bucket_name: string - the name of the s3 bucket
        prefix: string - the prefix of the name (key) of the bucket 
            objects

    Returns:
        a list of objects whose name (key) starts with the given prefix
    """
    s3 = boto3.resource('s3', region)
    bucket = s3.Bucket(bucket_name)
    names = []
    # osi - object summary iterator
    for osi in bucket.objects.filter(
            Prefix=prefix):
        name = osi.key
        names.append(name)
    return names

# determine if a given object key exists in the bucket
def key_exists(bucket_name, region, key):
    """ indicates if a key (object name) is in the bucket

    Args:
        bucket_name: string - the name of the s3 bucket
        key: string - the name of the object key (file-name)

    Returns:
        True if key in bucket; False otherwise
    """
    if key in list_by_prefix(bucket_name, region, key):
        return True
    return False

def get_timing_info(bucket_name, region, prefix):
    """ gets the timing information for jobs - labelled start & finish
    Returns:
        a 3-tuple of (finish time, elapsed time string, task name string)
    """
    s3 = boto3.resource('s3', region)
    bucket = s3.Bucket(bucket_name)
    start_dict = {}
    finish_dict = {}
    # osi - object summary iterator
    for osi in bucket.objects.filter(
            Prefix=prefix):
        name = osi.key
        last_mod = osi.last_modified
        if 'start' in name:
            start_dict[name] = last_mod
        if 'finish' in name:
            finish_dict[name] = last_mod
    results = []
    for name, finish_time in finish_dict.items():
        start_name = name.replace('finish', 'start') 
        if start_name in start_dict:
            elapsed = str(finish_time - start_dict[start_name])
            results.append((finish_time, elapsed, name.replace('finish', 'task').split('/')[-1].
                    split('.')[0]))

    return sorted(results)   

# download files matching regex
def download_files(bucket_name, region, prefix='', suffix='', dest_dir=''):
    """ downloads files who's path & name match given prefix & suffix
    to specified dir
    
    Args:
        bucket_name: the name of the s3 bucket to download from
        prefix: string - start of full path the s3 file
        suffix: string - the end characters of the file (e.g. '.vcf')
        dest_dir: string - the (local) directory to which the files are
            downloaded
    """
    # TODO better to raise ValueError??
    assert (prefix or suffix), 'must have a value for either prefix or suffix'
    # get rid of '/' at end of dir if exists
    if dest_dir.endswith('/'):
        dest_dir = dest_dir[:-1]
    # create directory in case not exist
    if dest_dir:
        os.makedirs(dest_dir, exist_ok=True)
    else:
        # no dir provided - default to current dir
        dest_dir = '.'
    names = []
    client = boto3.client('s3', region)
    transfer = S3Transfer(client)
    for name in list_by_prefix(bucket_name, region, prefix):
        if name.endswith(suffix):
            # remove any path from the file name
            fname = name.split('/').pop()
            # download the file
            transfer.download_file(bucket_name, name, dest_dir + '/' + fname)
