import configparser

import utility
import constants as CONST
class Config(object):
    """ reads from configuration file
    """
    def __init__(self, file_name):
        #TODO check for existance of file
        config = configparser.ConfigParser()
        config.read(file_name)
        # AWS
        self.aws_region = self.get_config_value(config, 
                CONST.CONFIG_SECTION_AWS, 
                CONST.CONFIG_VAL_REGION)
        # S3
        self.s3_bucket = self.get_config_value(config, 
            CONST.CONFIG_SECTION_AWS, 
            CONST.CONFIG_VAL_BUCKET)
        self.s3_results = self.get_config_value(config, 
            CONST.CONFIG_SECTION_AWS, 
            CONST.CONFIG_VAL_RESULTS)
        # EC2 Instance configuration
        # availability zone
        self.ec2_availability_zone =self.get_config_value(config,
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_AVAILABILITY_ZONE)
        # security key
        self.ec2_security_key = self.get_config_value(config, 
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_SECURITY_KEY)
        # instance types
        self.ec2_type =self.get_config_value(config, 
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_TYPE)
        # instance counts
        self.ec2_count =self.get_config_value(config, 
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_COUNT, True)
        # ebs only
        self.ec2_ebs_only_volume_size =self.get_config_value(config, 
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_EBS_ONLY_VOLUME_SIZE, True)
        self.ec2_ebs_only_volume_type =self.get_config_value(config, 
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_EBS_ONLY_VOLUME_TYPE)
        # user data
        self.ec2_user_data =self.get_config_value(config, 
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_USER_DATA)
        # user data checker
        self.ec2_user_data_check =self.get_config_value(config,
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_USER_DATA_CHECK)
        # dry run
        self.ec2_dry_run =self.get_config_value(config, 
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_DRY_RUN)
        # spot instance flag
        self.ec2_use_spot =self.get_config_value(config, 
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_USE_SPOT)
        # spot price
        self.ec2_spot_price =self.get_config_value(config, 
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_SPOT_PRICE)
        # image id
        self.ec2_image_id  =self.get_config_value(config,
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_IMAGE_ID)
        # security groups
        self.ec2_security_groups =self.get_config_value(config,
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_SECURITY_GROUPS)
        # security group id
        self.ec2_security_group_id =self.get_config_value(config,
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_SECURITY_GROUP_ID)
        # profile name
        self.ec2_profile_name =self.get_config_value(config,
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_PROFILE_NAME)
        # ARN id
        self.ec2_arn_id =self.get_config_value(config,
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_ARN_ID)
        # instance tag
        self.ec2_instance_tag =self.get_config_value(config,
            CONST.CONFIG_SECTION_AWS,
            CONST.CONFIG_VAL_INSTANCE_TAG)

        # program files
        self.local_program_files_dir =self.get_config_value(config,
            CONST.CONFIG_SECTION_RESCUE,
            CONST.CONFIG_VAL_LOCAL_DIR)
        # run
        self.pipe_run_output_dir = self.get_config_value(config,
            CONST.CONFIG_SECTION_RESCUE,
            CONST.CONFIG_VAL_RUN_OUTPUT_DIR)
        self.pipe_run_args = self.get_config_value(config,
            CONST.CONFIG_SECTION_RESCUE,
            CONST.CONFIG_VAL_RUN_ARGS)
        self.instance_working_dir = self.get_config_value(config,
            CONST.CONFIG_SECTION_RESCUE,
            CONST.CONFIG_VAL_INSTANCE_WORKING_DIR)
        #fastq
        self.fastq_manifest = self.get_config_value(config,
            CONST.CONFIG_SECTION_FASTQ,
            CONST.CONFIG_VAL_MANIFEST)
        self.fastq_s3_bucket = self.get_config_value(config,
            CONST.CONFIG_SECTION_FASTQ,
            CONST.CONFIG_VAL_COPY_S3_BUCKET)
        self.fastq_s3_region = self.get_config_value(config,
            CONST.CONFIG_SECTION_FASTQ,
            CONST.CONFIG_VAL_COPY_S3_REGION)
        self.fastq_s3_bucket_dir = self.get_config_value(config,
            CONST.CONFIG_SECTION_FASTQ,
            CONST.CONFIG_VAL_COPY_S3_BUCKET_DIR)
        self.fastq_s3_local_dir = self.get_config_value(config,
            CONST.CONFIG_SECTION_FASTQ,
            CONST.CONFIG_VAL_COPY_S3_LOCAL_DIR)

    # read a list of values for an item in the config file
    def get_config_list(self, config, sect_name, item_name, convert_int=False):
        """given a configparser object, and a section name & item name

        Args:
            config: configparser object to access configuration file
            sect_name: string - section name in configuration file
            item_name: string - item label in configuration file
            convert_int: boolean - convert value to int if True

        Returns:
            a list of values from the configuration file
        """
        value_str = config[sect_name][item_name]
        if convert_int:
            return_list = [int(x) for x in value_str.split()]
        else:
            return_list = value_str.split()
        
        return return_list

    # get value from config file and return as string
    def get_config_value(self, config, sect_name, item_name, convert_int=False):
        if convert_int:
            return int(config[sect_name][item_name])
        return config[sect_name][item_name]
