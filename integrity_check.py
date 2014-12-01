#! /usr/bin/env python
"""
Verify data integrity through the comparison of checksum values. If a file does 
not have a checksum value to compare, compute one; attach it to the file as 
an extended attribute, [namespace].checksum.[checksum_algorithm]; and log the 
name of the file.
"""

from __future__ import print_function

__author__ = "Christopher Thornton"
__date__ = "2014-10-27"

import sys
import os
import locale
import syslog
from subprocess import Popen,PIPE

def file_check(in_file):
    file_pass = True
    try:
        fh = open(in_file, 'rU')
        fh.close()
    except IOError as e:
        syslog.syslog(syslog.LOG_INFO, str(e))
        file_pass = False
    return file_pass

def sum_check(in_file, commands):
    """
    Check file for checksums. If values for the md5 and sha256 algorithms do 
    not already exist, compute them and store them with the file
    """
    algorithms = ["md5sum", "sha256sum"]
    for algorithm in algorithms:
        xattr_name = "user.checksum." + algorithm.replace("sum", "")
        compute_sum, compute_err= Popen([commands[algorithm], in_file], \
            stdout=PIPE, stderr=PIPE).communicate()
        value_computed = compute_sum.decode(locale.getdefaultlocale()[1]).\
            split(' ')[0]
        get_value, get_err = Popen([commands["getfattr"], "-n", \
            xattr_name, "--only-values", "--absolute-names", in_file], \
            stdout=PIPE, stderr=PIPE).communicate()
        value_stored = get_value.decode(locale.getdefaultlocale()[1])
        if not value_stored: #log and store if checksum doesn't already exist
            syslog.syslog(syslog.LOG_INFO, get_err.decode(locale.\
                getdefaultlocale()[1].strip()))
            syslog.syslog(syslog.LOG_INFO, in_file + ": " + xattr_name + ": " \
                + "setting value " + value_computed)
            store_err = Popen([commands["setfattr"], "-n", xattr_name, "-v", \
                value_computed, in_file], stderr=PIPE).communicate()[1]
            if store_err:
                syslog.syslog(syslog.LOG_WARNING, store_err.decode(locale.\
                    getdefaultlocale()[1]))
        else: #compare the values
            if value_computed != value_stored:
                log_message = in_file + ": " + xatrr_name + ": " + "checksum \
                    values do not match. File may be corrupt."
                syslog.syslog(syslog.LOG_ERR, log_message)

def main():
    data_path = sys.argv[1]
    commands = {"md5sum": "", "sha256sum": "", "setfattr": "", "getfattr": ""}
    #verify that the system has the proper tools installed
    for command in commands.keys():
        proc, proc_err = Popen(["which", command], stdout=PIPE, stderr=PIPE).\
            communicate()
        if proc_err:
            syslog.syslog(syslog.LOG_ERR, "Cannot find " + command + " in \
                system path.")
            sys.exit(1)
        commands[command] = proc.decode(locale.getdefaultlocale()[1]).strip()

    #obtain all of the shared data files
    all_files = []
    for root, dirs, file_names in os.walk(data_path):
        for file_name in file_names:
            file_path = root + "/" + file_name
            all_files.append(file_path)
    
    #iterate through list of files to compare or compute checksums
    for in_file in all_files:
        passes = file_check(in_file)
        if not passes:
            continue
        sum_check(in_file, commands)
    syslog.syslog(syslog.LOG_INFO, "Data check completed")
    
if __name__ == "__main__":
    main()

sys.exit(0)
