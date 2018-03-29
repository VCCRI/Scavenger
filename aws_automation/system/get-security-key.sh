#!/bin/bash
# gets a security key name from a python .cfg file & python constants file

# location of python3 executable
python3=$( system/get-python-path.sh )
# get a constant value from the python constants file used for this app
get_constant_value() {
    echo `$python3 constants.py $1`
}

# get security key name
# file extension for security key
file_ext=`get_constant_value SECURITY_FILE_EXT` 
# need strings for .cfg file section & item
section=`get_constant_value CONFIG_SECTION_AWS`
item=`get_constant_value CONFIG_VAL_SECURITY_KEY`
security_key=`$python3 get-config-value.py $section $item`$file_ext
echo "$security_key"
