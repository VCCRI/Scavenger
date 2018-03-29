# utility.py
"""library of utility functions

Available functions
- file_to_list: makes a list out of the lines of a file
- copy_local_to_remote: copies files from local to remote system
- remote_command: executes a command on a remote system
"""
import subprocess
import os

# local imports
import constants as CONST

# make a list out of the lines of a file
def file_to_list(file_name):
    """ makes a list out of the lines of a file

    Args:
        file_name: string - the name of the file

    Returns:
        a list - the lines of the file
    """
    lines = []
    with open(file_name) as f:
        lines = f.read().splitlines()
    return lines

# make a file from a list
def list_to_file(file_name, lines):
    """ creates a file from a list of line values

    Args:
        file_name: string - name of file
        lines: list - each item is a line in the file
    """
    with open(file_name, 'w') as f:
        for line in lines:
            f.write(line + '\n')

# make a directory listing of files in the given directory
# - files in subdirectories are excluded
#TODO doco
def list_dir(dir_name):
    names = os.listdir(dir_name) 
    fnames = []
    for name in names:
        path = dir_name + '/' + name
        if os.path.isfile(path):
            fnames.append(path)
    return fnames

# copy local files to remote system
def copy_local_to_remote(key, ip, files, dest_dir):
    """ copies files from a local source to a remote system

    Args:
        key:        string  - full path of security key
        ip:         string  - ip address of remote system
        files:      list    - list of full paths of files to copy
        dest_dir:   string  - dir path for remote destination
    """
    # files is a list - scp expects a string of filenames sep by spaces
    result = subprocess.call(['./scp.sh', key, ip, " ".join(files), dest_dir])
    return result

# execute remote command
def remote_command(ip, cmd):
    """ executes a command on a remote system

    Args:
        ip:      string      ip address of remote system
        cmd:     string      command to execute on remote system
    """
    result = subprocess.call(['./ssh-cmd.sh', ip, cmd])
    return result

