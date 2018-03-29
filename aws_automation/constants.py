import sys

# general
EMPTY = ''
RUN_INSTANCE_SCRIPT = 'system/run-instances.sh'
PAUSE = 10  # seconds to pause for job completion

# constants for pipeline testing program
CONFIG_FILE = 'rescue.cfg'
# this constants file
CONSTANTS_FILE = 'constants.py'

# cfg sections, parameters
CONFIG_SECTION_AWS = 'aws'
CONFIG_VAL_REGION = 'region'
CONFIG_VAL_BUCKET = 's3-bucket'
CONFIG_VAL_RESULTS = 's3-results-dir'
CONFIG_VAL_AVAILABILITY_ZONE = 'availability-zone'
CONFIG_VAL_USE_SPOT = 'use-spot'
CONFIG_VAL_SPOT_PRICE = 'spot-price'
CONFIG_VAL_TYPE = 'instance-type'
CONFIG_VAL_COUNT = 'count'
CONFIG_VAL_EBS_ONLY_VOLUME_SIZE = 'ebs-only-volume-size'
CONFIG_VAL_EBS_ONLY_VOLUME_TYPE = 'ebs-only-volume-type'
CONFIG_VAL_USER_DATA = 'user-data'
CONFIG_VAL_USER_DATA_CHECK = 'user-data-checker'
CONFIG_VAL_USER_DATA_OPTION = '--user-data'
CONFIG_VAL_DRY_RUN = 'dry-run'
CONFIG_VAL_DRY_RUN_OPTION = '--dry-run'
CONFIG_VAL_SECURITY_KEY = 'security-key'
CONFIG_VAL_IMAGE_ID = 'image-id'
CONFIG_VAL_SECURITY_GROUPS = 'security-groups'
CONFIG_VAL_SECURITY_GROUP_ID = 'security-group-id'
CONFIG_VAL_PROFILE_NAME = 'profile-name'
CONFIG_VAL_ARN_ID = 'arn-id'
CONFIG_VAL_INSTANCE_TAG = 'instance-tag'

CONFIG_SECTION_RESCUE = 'rescue'
CONFIG_VAL_LOCAL_DIR = 'local-program-dir'
CONFIG_VAL_RUN_OUTPUT_DIR = 'instance-output-dir'
CONFIG_VAL_RUN_ARGS = 'command-arguments'
CONFIG_VAL_INSTANCE_WORKING_DIR = 'instance-working-dir'


# copy-s3 allows for multiple sections of the form
# copy-s3* - e.g. copy-s3-1, copy-s3-2,etc
CONFIG_SECTION_COPY_S3 = 'copy-s3'
# note that some of these CONFIG_VAL_COPY_S3 values are also used by
# the fasq section
CONFIG_VAL_COPY_S3_BUCKET = 's3-bucket-addr'
CONFIG_VAL_COPY_S3_REGION = 'region'
CONFIG_VAL_COPY_S3_BUCKET_DIR = 's3-bucket-dir'
CONFIG_VAL_COPY_S3_LOCAL_DIR = 'destination-dir' 
CONFIG_VAL_COPY_S3_FILES = 'files' 

# fastq
CONFIG_SECTION_FASTQ = 'fastq'
CONFIG_VAL_MANIFEST = 'manifest'

# non config file constants (user does not maintain)
S3_COPY_SCRIPT = 'copy-s3.py'
RESCUE_INSTANCE_FILES_DIR = 'rescue-instance-files'
INSTANCE_SCRIPT_WRAPPER = 'wrapper.sh'
INSTANCE_VCF_PATH = 'latest-vcf-file-path.txt'
RESULTS_DIR = 'results'
USER_INSTANCE_FILES_DIR = 'user-instance-files'
FAILED_LABEL = 'FAILED'
TEMP_DIR = 'tmp'    # temporary directory to hold ephemeral files
PYTHON3_PATH = '/opt/python3.4.3/bin/python3'
# file extension for AWS security key
SECURITY_FILE_EXT = '.pem'
# targeting instances with > 30G mem
VALID_EC2_INSTANCE_TYPES_EBS_ONLY = 'm4.2xlarge|m4.4xlarge|m4.10xlarge|m4.16xlarge|c4.4xlarge|c4.8xlarge|r4.4xlarge|r4.2xlarge|r4.4xlarge|r4.8xlarge|r4.16xlarge'
VALID_EC2_INSTANCE_TYPES_HAS_INSTANCE_SSD = 'm3.2xlarge|c3.4xlarge|c3.8xlarge|r3.8xlarge|m3.large|r3.xlarge|r3.2xlarge|r3.4xlarge|c4.2xlarge'
VALID_EC2_INSTANCE_TYPES = VALID_EC2_INSTANCE_TYPES_EBS_ONLY + '|' + VALID_EC2_INSTANCE_TYPES_HAS_INSTANCE_SSD 

# info dir constants
RESCUE_INFO_DIR = 'info'
INSTANCE_IPS_FILE = RESCUE_INFO_DIR + '/ipaddrs.txt'
LATEST_RESULTS_PATH = RESCUE_INFO_DIR + '/latest-results-dir.txt'
RUNNNING_INSTANCE_TYPES_FILE = RESCUE_INFO_DIR + '/running-inst-types-file.txt'
SPOT_REQUEST_IDS = RESCUE_INFO_DIR + '/spot-request-ids.txt'
INSTANCE_PARMS = RESCUE_INFO_DIR + '/instance-parms.txt'
INSTANCE_IDS = RESCUE_INFO_DIR + '/instance-ids.txt'

RESCUE_INFO_STATIC_DIR = 'info-static'
INSTANCE_TYPES = RESCUE_INFO_STATIC_DIR + '/instance-types.txt'

#colours
YELLOW = '\033[33m'
NC = '\033[0m' 
BOLD = '\033[1m' 
RED = '\033[31m' 
PURPLE = '\033[35m' 
CYAN = '\033[36m' 
GREEN = '\033[92m'
BLUE = '\033[94m'
GREY = '\033[37m'

#log level
DEBUG = YELLOW + 'DEBUG: ' + NC
WARN = RED + 'WARN: ' + NC
ERROR = RED + 'ERROR: ' + NC
INFO = YELLOW + 'INFO: ' + NC

# the following code allows bash scripts to get constant values
# In bash call like: "python3 constants.py <constant name>"
# e.g. "python3 constants.py INSTANCE_IDS"
if __name__ == '__main__':
    # default to null string in case of any problems
    val = ''
    if len(sys.argv) > 1:
        try:
            # get the arg - which is the name of the constant (key)
            key = sys.argv[-1]
            # vars() is a dictionary of variable values
            val = vars()[key]
        except:
            pass
    print(val)
