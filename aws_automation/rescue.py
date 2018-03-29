# rescue.py 
""" AWS automation to execute scavenger.py on one or
more EC2 instances

Controlled by a configuration file: rescue.cfg

This framework creates instances in the AWS EC2 environment
using the user's own credentials.  

"""

import sys

#only designed for python 3
#some imported modules depend on python 3, so better to exit gracefully
assert sys.version_info[0] == 3, ( 
    "This program must be run with Python version 3.x")

import os
import argparse
import configparser
import subprocess
import datetime
import logging
import time
import enum
from collections import namedtuple
import botocore.session
from dateutil.tz import tzutc
import base64
import boto3
import constants as CONST
import utility
import config
import s3

#this should only be run directly (not from import)
#if __name__ == "main":

class Rescue(object):
    """Read Rescuer class

    main class for the framework
    """

    def __init__(self):
        self.rescue_id = ''
        cfg = config.Config(CONST.CONFIG_FILE)
        self.aws_region = cfg.aws_region
        self.ec2_availability_zone = cfg.ec2_availability_zone
        self.ec2_security_key = cfg.ec2_security_key
        self.ec2_type = cfg.ec2_type
        self.ec2_count = cfg.ec2_count
        self.ec2_ebs_only_volume_size = cfg.ec2_ebs_only_volume_size
        self.ec2_ebs_only_volume_type = cfg.ec2_ebs_only_volume_type
        self.ec2_user_data = cfg.ec2_user_data
        self.ec2_user_data_check = cfg.ec2_user_data_check
        self.ec2_dry_run = cfg.ec2_dry_run
        self.ec2_use_spot = cfg.ec2_use_spot
        self.ec2_spot_price = cfg.ec2_spot_price
        self.ec2_image_id = cfg.ec2_image_id
        self.ec2_security_groups = cfg.ec2_security_groups 
        self.ec2_security_group_id = cfg.ec2_security_group_id 
        self.ec2_profile_name = cfg.ec2_profile_name
        self.ec2_arn_id = cfg.ec2_arn_id
        self.ec2_instance_tag = cfg.ec2_instance_tag
        self.s3_bucket = cfg.s3_bucket
        self.s3_results = cfg.s3_results
        self.pipe_run_output_dir = cfg.pipe_run_output_dir
        self.pipe_run_args = cfg.pipe_run_args
        self.local_program_files_dir = cfg.local_program_files_dir
        self.instance_working_dir = cfg.instance_working_dir
        # fastq values
        self.fastq_manifest = cfg.fastq_manifest
        self.fastq_s3_bucket = cfg.fastq_s3_bucket
        self.fastq_s3_region = cfg.fastq_s3_region
        self.fastq_s3_bucket_dir = cfg.fastq_s3_bucket_dir
        self.fastq_s3_local_dir = cfg.fastq_s3_local_dir
        

    def debug_print(self, msg):
        #if __debug__:
        # don't print atm
        if False:
            print('<## debug ##>' + msg)

    def initialise_test_run(self):
        """initialises the pipeline test run

        Creates a unique id for this run & creates a folder in S3 bucket
        Also checks if s3 bucket exists & creates if not there

        program should exit if user doesn't have right to create bucket in s3

        Args:
            config: configparser object to access configuration file

        Returns:
            id: string representing the unique id for this run in format
            ddmmYYYYDay-<seconds today padded with 0's>
        """
        # only allow spot instances at this stage
        if self.ec2_use_spot != "1":
            lgr.error(CONST.ERROR + colour_msg(Colour.CYAN, 
                'This framework only allows AWS EC2 spot instances.  See configuration file.'))
            sys.exit(1)
        if self.ec2_type not in (CONST.VALID_EC2_INSTANCE_TYPES).split('|'):
            lgr.error(CONST.ERROR + 
                    colour_msg(Colour.CYAN, 'Invalid EC2 instance type: ') +
                    colour_msg(Colour.PURPLE, self.ec2_type) + 
                    colour_msg(Colour.CYAN, '.  Valid instance types include: ') + 
                    colour_msg(Colour.PURPLE, CONST.VALID_EC2_INSTANCE_TYPES))
            sys.exit(1)
        
        # create unique id for this run 
        now = datetime.datetime.now()
        tmp_prefix = self.s3_results + '/'
        self.rescue_id = s3.get_next_id(self.s3_bucket, self.aws_region,
                tmp_prefix + now.strftime("%d%m%Y%a-"))
        # create an entry in the s3 log for start of pipeline testing
        self.log_to_s3('rescue-start.log', 'start')

    def log_to_s3(self, file_name, time_label):
        """send a small timing log to s3 - used in timing stats"""
        lines = []
        line = '[time]'
        lines.append(line)
        line = time_label + '=' + str(datetime.datetime.now())
        lines.append(line)
        utility.list_to_file(file_name, lines)
        s3.upload_file(self.s3_bucket, self.aws_region, file_name,
                self.s3_results + '/' + self.rescue_id + '/' + file_name)
        # now delete the file because we don't need it
        os.remove(file_name)

    # run instances
    def run_instances(self):
        """ starts aws ec2 instances

        Instance settings are obtained from the configuration file
        
        Args:
            config: configparser object to enable reading from .cfg file
        Returns:
            a list of ip addresses of the instances - when they are
            ready to use
        """
        # create an entry in the s3 log for the start of this task 
        self.log_to_s3('run-instances-start.log', 'start')

        session = botocore.session.get_session()
        client = session.create_client('ec2', region_name=self.aws_region)

        # convert user-data to base64
        user_data = ''
        # NOTE conversion of file to string, then string to bytes, the bytes encoded 
        # base64 - then decode the base64 bytes into base64 string
        with open(self.ec2_user_data, 'r') as f:
            user_data = base64.b64encode(bytes(f.read(), "utf-8")).decode("utf-8")

        if self.ec2_type in (CONST.VALID_EC2_INSTANCE_TYPES_EBS_ONLY).split('|'):
            # block device mapping for ebs backed instances
            # creates an ephemeral EBS volume (delete on terminate)
            # Note that gp2 instance type is EBS SSD
            custom_block_device_mapping = [{
                        'DeviceName': '/dev/sdb',
                        'VirtualName': 'ephemeral0',
                        'Ebs':{
                            'VolumeSize': self.ec2_ebs_only_volume_size,
                            'VolumeType': self.ec2_ebs_only_volume_type,
                        },
                    }]
        else:
            # block device mapping allows for 2 extra drives
            # - works for either single ssd or 2 ssd's
            custom_block_device_mapping = [ 
                {
                    'DeviceName': '/dev/sdb',
                    'VirtualName': 'ephemeral0'
                },
                {
                    'DeviceName': '/dev/sdc',
                    'VirtualName': 'ephemeral1'
                }
            ]

        r = client.request_spot_instances(
            InstanceCount=self.ec2_count,
            SpotPrice=self.ec2_spot_price,
            LaunchSpecification= {
                'SecurityGroupIds': [
                    self.ec2_security_group_id,
                ],
                'SecurityGroups': [
                    self.ec2_security_groups,
                ],
                'Placement': {
                    'AvailabilityZone': self.ec2_availability_zone,
                },
                'BlockDeviceMappings': custom_block_device_mapping,
                'IamInstanceProfile': {
                    'Arn': self.ec2_arn_id,
                },
                'UserData': user_data,
                'ImageId': self.ec2_image_id,
                'InstanceType': self.ec2_type,
                'KeyName': self.ec2_security_key,
            },
        )

        # get the spot instance request ids
        spot_ids = []
        lgr.debug(CONST.DEBUG + colour_msg(Colour.CYAN, 'Spot request ids:'))
        for i, spot_inst in enumerate(r['SpotInstanceRequests']):
            inst_str = '[' + str(i) + ']'
            lgr.debug(CONST.DEBUG + colour_msg(Colour.PURPLE, 
                inst_str + '\t' + spot_inst['SpotInstanceRequestId']))
            spot_ids.append(spot_inst['SpotInstanceRequestId'])
        utility.list_to_file(CONST.SPOT_REQUEST_IDS, spot_ids)

        # create a list of spot instance statuses - so we can print out
        # some updates to the user
        spot_status = ['']*len(spot_ids)
        # Expecting status codes of "pending-evaluation", "pending-fulfillment", or 
        # fulfilled.  Any other status-code should be printed out & the program 
        # terminated.
        expected_status = ['fulfilled', 'pending-evaluation', 'pending-fulfillment']
        instance_ids = [None]*len(spot_ids)

        # check the status of the spot requests
        while True:
            fulfilled = 0
            for i, id in enumerate(spot_ids):
                inst_str = '[' + str(i) + ']'
                r = client.describe_spot_instance_requests(SpotInstanceRequestIds=[id])
                status_code = r['SpotInstanceRequests'][0]['Status']['Code']
                if status_code not in expected_status:
                    lgr.error(CONST.ERROR + 
                            colour_msg(Colour.CYAN, 'Unexpected status for spot request ') +
                            colour_msg(Colour.PURPLE, id) +
                            colour_msg(Colour.CYAN, ': ') +
                            colour_msg(Colour.PURPLE, status_code))
                    sys.exit(1)
                if status_code != spot_status[i]:
                    lgr.debug(CONST.DEBUG + 
                            colour_msg(Colour.CYAN, 'Spot instance request: ') +
                            colour_msg(Colour.PURPLE, inst_str) +
                            colour_msg(Colour.CYAN, '\tStatus: ') +
                            colour_msg(Colour.PURPLE, status_code))
                    spot_status[i] = status_code
                if status_code == 'fulfilled':
                    fulfilled += 1
                    # record the instance id
                    instance_ids[i] = r['SpotInstanceRequests'][0]['InstanceId']
            if fulfilled == len(spot_ids):
                break
            time.sleep(1)

        utility.list_to_file(CONST.INSTANCE_IDS, instance_ids)
        lgr.debug(CONST.DEBUG + colour_msg(Colour.CYAN, 'Instance Ids:'))
        for i, id in enumerate(instance_ids):
            inst_str = '[' + str(i) + ']'
            lgr.debug(CONST.DEBUG + colour_msg(Colour.PURPLE, inst_str + '\t' + id))
            tag_val = self.ec2_instance_tag + str(i)
            client.create_tags(Resources=[id], Tags=[{'Key':'Name', 'Value':tag_val}])

        # monitor the instances until all running
        instance_states = ['']*len(instance_ids)
        expected_states = ['running', 'pending']
        instance_ips = [None]*len(instance_ids)
        running = 0
        while True:
            running = 0
            for i, id in enumerate(instance_ids):
                inst_str = '[' + str(i) + ']'
                r = client.describe_instances(InstanceIds=[id])
                state = r['Reservations'][0]['Instances'][0]['State']['Name']
                if state not in expected_states:
                    lgr.error(CONST.ERROR + 
                            colour_msg(Colour.CYAN, 
                                'Unexpected instance state for instance-id ') +
                            colour_msg(Colour.PURPLE, id) +
                            colour_msg(Colour.CYAN, ': \t') +
                            colour_msg(Colour.PURPLE, state))
                    sys.exit(1)
                if state != instance_states[i]:
                    lgr.debug(CONST.DEBUG + 
                            colour_msg(Colour.CYAN, 'Instance id: ') +
                            colour_msg(Colour.PURPLE, inst_str) +
                            colour_msg(Colour.CYAN, '\tState: ') +
                            colour_msg(Colour.PURPLE, state))
                    instance_states[i] = state
                if state == 'running':
                    running += 1
                    # record the instance id
                    instance_ips[i] = r['Reservations'][0]['Instances'][0]['PublicDnsName']
            if running == len(instance_ids):
                break
            time.sleep(10)

        lgr.debug(CONST.DEBUG + colour_msg(Colour.CYAN, 'Instance Ips:'))
        for i, id in enumerate(instance_ips):
            inst_str = '[' + str(i) + ']'
            lgr.debug(CONST.DEBUG + colour_msg(Colour.PURPLE, inst_str + '\t' + id))
         
        utility.list_to_file(CONST.INSTANCE_IPS_FILE, instance_ips)
        # need to at least wait until all the instances are reachable
        # possible statuses: (passed | failed | initializing | insufficient-data )
        reachability = ['']*len(instance_ids)
        while True:
            passed = 0
            for i, id in enumerate(instance_ids):
                inst_str = '[' + str(i) + ']'
                r = client.describe_instance_status(InstanceIds=[id])
                state = r['InstanceStatuses'][0]['InstanceStatus']['Details'][0]['Status']
                if state != reachability[i]:
                    lgr.debug(CONST.DEBUG + 
                            colour_msg(Colour.CYAN, 'Instance id: ') +
                            colour_msg(Colour.PURPLE, inst_str) +
                            colour_msg(Colour.CYAN, '\tReachability: ') +
                            colour_msg(Colour.PURPLE, state))
                    reachability[i] = state
                if state == 'passed':
                    passed += 1
            if passed == len(instance_ids):
                break
            time.sleep(10)
                    
        lgr.info(CONST.INFO + colour_msg(Colour.GREEN, 'Instances are reachable'))
        
        # if user-data configuration file supplied - check that it has worked
        # Note that this checker is run once on each instance
        if self.ec2_user_data:
            lgr.info(CONST.INFO + colour_msg(Colour.CYAN, 
                'Starting job to monitor user-data configuration...'))
            # at the moment is calling a local script that does the checking
            result = subprocess.call('./' + self.ec2_user_data_check)  
            if result:
                lgr.error(CONST.ERROR + colour_msg(Colour.CYAN, 
                    'user data checker FAILED'))
                sys.exit(1)

        # create an entry in the s3 log for finish this task 
        self.log_to_s3('run-instances-finish.log', 'finish')

        # return the list of ip's for the newly created instances
        return utility.file_to_list(CONST.INSTANCE_IPS_FILE)

    # install user pipeline on instances
    def install_pipeline(self, ip, label, extra):
        """ installs the users's pipeline software on a specified instance
        
        Args:
            ip: string - ip address of instance

        Returns:
            (no return value)
        """
        # copy files to instance - user specifies in .cfg
        # also copy essential rescue files as well
        # assumes user includes install script in list
        # NOTE - nothing to install as "pipeline" is run via 
        # wrapper script
        result = utility.copy_local_to_remote(
                self.ec2_security_key + CONST.SECURITY_FILE_EXT, ip, 
                utility.list_dir(CONST.RESCUE_INSTANCE_FILES_DIR) +
                utility.list_dir(self.local_program_files_dir) +
                [CONST.CONFIG_FILE, CONST.CONSTANTS_FILE],
                self.instance_working_dir)
        # there is no script to run - so we need to log the finish
        # or failure  to s3
        if result==0:
            self.log_to_s3(label + '-finish.log', 'finish')
        else:
            self.log_to_s3(label + '-failed.log', 'failed')

    # copy data from S3 to instance
    def copy_s3_data(self, ip, label, extra):
        self.run_instance_script_asynch(ip, CONST.S3_COPY_SCRIPT, label)

    def run_pipeline(self, ip, label, extra):
        # first copy fastq file(s) to instance
        # - extra parm is name of fastq file or files (in case of pe)
        fq_list = extra.split('\t')
        extra_args = '--fastq1 ' + fq_list[0]
        if len(fq_list) > 1:
            extra_args += ' --fastq2 ' + fq_list[1]
        # output directory consists of a base output directory (e.g.
        # /mnt2/output) and a subdirectory for this aws run (e.g. 
        # 03102017Tue-1) and a subdirectory for the fastq identifier
        # (e.g. fastq-1) ; so the final target directory structure would 
        # be like: /mnt2/output/03102017Tue-1/fastq-1
        # Input argument "label" already includes <fastq-i>


        # send through other details necessary to copy fastq file(s) from 
        # s3 to instance
        extra_args += ' --fastq_s3_bucket ' + self.fastq_s3_bucket
        extra_args += ' --fastq_s3_region ' + self.fastq_s3_region
        extra_args += ' --fastq_s3_bucket_dir ' + self.fastq_s3_bucket_dir
        extra_args += ' --fastq_s3_local_dir ' + self.fastq_s3_local_dir
        extra_args += ' --output_dir ' + self.pipe_run_output_dir
        extra_args += ' --run_args ' + self.pipe_run_args
        self.debug_print('extra_args: ' + extra_args)
        # Note that the wrapper script will call the rescue code - NOT
        # called by a separate script on the instance
        self.run_instance_script_asynch(ip, 'NO_SCRIPT', label,
                extra_args)

    # helper functon to run instance command
    def run_instance_script_asynch(self, ip, script, label, extra=''):
        """
        runs a script that exists on the instance by using the wrapper 
        script (also on instance)

        Args:
            ip: string - ip address of instance
            script: name of script to run on instance
            label: string - label used to create s3 logging info
        """
        utility.remote_command(ip, 'nohup ' + self.instance_working_dir + '/' + 
                CONST.INSTANCE_SCRIPT_WRAPPER + ' ' +
                script + ' ' + self.s3_bucket + ' ' +
                self.s3_results + ' ' +
                self.aws_region + ' ' + self.rescue_id + '/' + label + ' ' + 
                extra + '> ' + label + '.out 2>&1 < /dev/null &')

        
# end of class Rescue

# helper class to enumerate colours for use with logging
class Colour(enum.Enum):
    YELLOW = CONST.YELLOW
    NC = CONST.NC 
    BOLD = CONST.BOLD
    RED = CONST.RED
    PURPLE = CONST.PURPLE
    CYAN = CONST.CYAN
    GREEN = CONST.GREEN
    BLUE = CONST.BLUE 


# helper for logging in colour
def colour_msg(colour, msg):
    return colour.value + msg + Colour.NC.value

# helper function to strip off instance index
def get_instance_index(label):
    """ gets the instance index from a label

    the label is assumed to be of the form:
        some-text-<num> e.g. 'copy-s3-data-0'
    """
    return_val = None
    try:
        return_val = label.split('-').pop()
        return_val = int(return_val)
    except:
        pass
    return return_val

# main part of program
# create instance of class Rescue
rescue = Rescue()

# set up logging
# Note that we use two copies of the log file -
# one in the current dir (that will be overwritten next run)
# & one in the results dir - that wont be overwritten
# Also note that 'rescue.log' contains only the loggging info
# whereas the report file will contain logging + other information
logging.basicConfig(filename='rescue.log', filemode = 'w', 
        level=logging.DEBUG, datefmt='%d-%m %H:%M:%S')
# suppress low-level boto logging messages
logging.getLogger('botocore').setLevel(50)
logging.getLogger('boto3').setLevel(50)
# also log to the report file
logfile = 'latest_rescue_run.log'
# create error file handler and set level to error
file_handler = logging.FileHandler(logfile,"w", 
        encoding=None, delay="true")
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s %(message)s', '%H:%M:%S')
file_handler.setFormatter(formatter)
# define a Handler which writes INFO messages or higher to the sys.stderr
console = logging.StreamHandler()
console.setLevel(logging.DEBUG)
# tell the handler to use the format created earlier
console.setFormatter(formatter)
# add the handler to the rescue logger
lgr = logging.getLogger('RESCUE')
lgr.addHandler(file_handler)
lgr.addHandler(console)

# initialise
rescue.initialise_test_run()

#Parse arguments
parser = argparse.ArgumentParser()
#allow single
#TODO - how to throw errors if certain combinations of options
# e.g. don't want --all & --jobs
parser.add_argument('--all', nargs='?', default=argparse.SUPPRESS, 
        help="full run - create & configure instances + do testing run")
parser.add_argument('--x-instances', nargs='?', default=argparse.SUPPRESS, 
        help="don't create instances")
parser.add_argument('--x-install', nargs='?', default=argparse.SUPPRESS, 
        help="don't install/configure instances")
parser.add_argument('--x-jobs', nargs='?', default=argparse.SUPPRESS, 
        help="don't run jobs yet")
parser.add_argument('--jobs', nargs='?', default=argparse.SUPPRESS, 
        help="run jobs only")
args = parser.parse_args()  #access like args.<argname>
d_args = vars(args)         #a dictionary of the args
if not d_args:
    print(colour_msg(Colour.RED, "You must specify at least one option"))
    parser.print_help()
    sys.exit(1)

lgr.info(CONST.INFO + colour_msg(Colour.CYAN, 
    'STARTED RESCUE PROCESSING FOR ID: ')
        + colour_msg(Colour.PURPLE, rescue.rescue_id))

#set variables based on parameter values
do_run_instances = True
do_run_jobs = True
do_configure_instances = True
if 'x_instances' in d_args:
    do_run_instances = False
if 'x_install' in d_args:
    do_configure_instances = False
    do_run_instances = False
if 'jobs' in d_args:
    do_run_instances = False
    do_configure_instances = False
if 'x_jobs' in d_args:
    do_run_jobs = False

rescue.debug_print("do_run_instances = " + str(do_run_instances))

# start instances unless option set to prevent starting instances
instance_ips = []
if do_run_instances:
    # log start of instance creation
    lgr.info(CONST.INFO + colour_msg(Colour.CYAN, 
        'starting job to create instances...'))
    # create the instances
    instance_ips = rescue.run_instances()
    # log finish instance creation
    lgr.info(CONST.INFO + colour_msg(Colour.GREEN, 
        'finished creating instances...'))
    # log the ip addresses of the created instances
    for i, ip in enumerate(instance_ips):
        lgr.info(CONST.INFO + colour_msg(Colour.CYAN, 
            'ip ' + str(i) + ' - ') + 
            colour_msg(Colour.PURPLE, ip))
else:
    print("not creating instances")

# get a list of all the instance ips
instance_ips = utility.file_to_list(CONST.INSTANCE_IPS_FILE)

# create a job q for each instance
# NOTE the 'label action' is a list of "properties" for Job - label & action
Job = namedtuple('Job', 'label action extra')
job_q_list = []
# note in reverse order, as we will be popping jobs from end of list
# start with essential setup jobs
jobs_list = []
if do_configure_instances:
    extra = ''
    jobs_list = [('copy-s3-data', rescue.copy_s3_data, extra), 
            ('install-pipeline', rescue.install_pipeline, extra)]
# code for running the rescue pipeline
# Each fastq file (or pair) requires one pipeline run
jobs = []
if do_run_jobs:
    # for each line of fastq manifest, create a job entry
    try:
        i = 1
        with open(rescue.fastq_manifest, 'r') as f:
            for fastq in f:
                jobs.append(('fastq-' + str(i) + '-i', rescue.run_pipeline, fastq.strip()))
                rescue.debug_print('fastq: ' + fastq.strip())
                i += 1
            # revese the list jobs - so that the first record (fastq)
            # is at the end of the list (first to be used)
            jobs = jobs[::-1]
    except IOError:
        lgr.error(CONST.ERROR + colour_msg(Colour.CYAN, 
            'Unable to open manifest file: ' + rescue.fastq_manifest))
        sys.exit(1)

# assign jobs to instances - set up every instance first
num_instances = len(instance_ips)
for i in range(num_instances):
    job_q_list.append(jobs_list[:])
# assign MR jobs to instances one at a time until all MR's allocated
# allows for less instances than there are MR's
while jobs:
    for i in range(num_instances):
        if not jobs:
            break
        job_q_list[i].insert(0, jobs.pop())

active_jobs = []

# starts the first job for each instance
for i, ip  in enumerate(instance_ips):
    # job is a tuple where the first element is the job label minus
    # the instance index (e.g. 'install_pipeline'); the second element
    # is the action to run for this job (the function name)
    # Job is a namedtuple of (label, action, extra)
    # use * to expand job_q_list tuple
    if job_q_list[i]:
        job = Job(*(job_q_list[i].pop()))
        # run the job
        label = job.label + '-' + str(i)
        job.action(ip, label, job.extra)
        # add to active jobs list & log start of job
        active_jobs.append(label)
        lgr.info(CONST.INFO + colour_msg(Colour.CYAN, 'starting job: ') + 
                colour_msg(Colour.PURPLE, label))

# wait for pipeline run to finish:
while active_jobs:
    # looping through a copy of the active jobs list
    for label in active_jobs[:]:
        prefix = rescue.s3_results + '/' + rescue.rescue_id + '/' + label
        # if anything has failed, stop
        for name in s3.list_by_prefix(rescue.s3_bucket, rescue.aws_region,prefix):
            if CONST.FAILED_LABEL in name.upper():
                lgr.error(CONST.ERROR + colour_msg(Colour.CYAN, 
                    'A job has failed: ' + name))
                sys.exit(1)
        if s3.key_exists(rescue.s3_bucket, rescue.aws_region, 
                prefix + '-finish.log'):
            lgr.info(CONST.INFO + colour_msg(Colour.GREEN, 'finished job: ')
                    + colour_msg(Colour.PURPLE, label))
            # job has finished - remove from active list
            active_jobs.remove(label)
            # get instance index (some-label-string-0)
            i = get_instance_index(label)
            assert (i is not None), 'label without instance index: ' \
                    + label
            # check for more jobs for this instance
            if job_q_list[i]:
                # get the next job in the q for instance i
                job = Job(*(job_q_list[i].pop()))
                # get label for job
                lbl = job.label + '-' + str(i)
                # run job
                job.action(instance_ips[i], lbl, job.extra)
                # add to active jobs list & log start of job
                active_jobs.append(lbl)
                lgr.info(CONST.INFO + colour_msg(Colour.CYAN, 'starting job: ') + 
                        colour_msg(Colour.PURPLE, lbl))
        
    # pause - give time for job to finish
    time.sleep(CONST.PAUSE)


lgr.info(CONST.INFO + colour_msg(Colour.GREEN, 
    'FINISHED RESCUE PROCESSING FOR ID: ')
        + colour_msg(Colour.PURPLE, rescue.rescue_id))

# close file handler in the logger, so that no issue appending to report
for h in lgr.handlers:
    if type(h) == logging.FileHandler:
        h.close()
