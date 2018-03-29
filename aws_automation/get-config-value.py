"""gets a configurgation value from the rescue.cfg file
    - intended to be called from within a bash script

    The expected input arguments are two strings:
    representing the section and the item name
    for which the value is to be obtained from 
    the .cfg file
"""

import sys
import configparser

import constants as CONST

# program only intended to be called from within a bash script
# If there is some problem - exit with non-zero value & let the 
# bash script deal with the error
if __name__ == '__main__':
    section = item = ''
    if len(sys.argv) < 3:
        sys.exit(1)
    else:
        # only look at first two arguments
        section, item = sys.argv[1:3]
    if not section or not item:
        sys.exit(1)
    # read in the configuration file
    config = configparser.ConfigParser()
    config.read(CONST.CONFIG_FILE)
    try:
        # "return" the configuration value
        print(config[section][item])
    except:
        sys.exit(1)
