#! /usr/bin/env python
'''
Verify data integrity through the comparison of checksum values. If a file does 
not have a checksum value to compare, compute one; attach it to the file as 
an extended attribute, [namespace].checksum.[checksum_algorithm]; and log the 
name of the file. Supports multiple threads.
'''

from __future__ import print_function

__author__ = 'Christopher Thornton, Alex Hyer'
__date__ = '2015-03-30'
__version__ = '2.1.3'

import argparse
import sys
import os
import locale
import platform
import multiprocessing
from datetime import datetime
from subprocess import Popen,PIPE

def output_stream(message, log_file=None):
    if log_file:
        prog = os.path.basename(__file__)
        date = datetime.now().strftime("%b %d %H:%M:%S")
        hostname = platform.node().split('.')[0]
        output = "{} {} {}: {}".format(date, hostname, prog, message)
        with open(log_file, 'a')  as out_handle:
	    out_handle.write('{}\n'.format(output))
    else:
        print(message)

def file_check(in_file):
    """check privelages and existence"""
    file_pass = True
    try:
        fh = open(in_file)
        fh.close()
    except IOError as e:
	output_stream(e, log_file)
        file_pass = False
    return file_pass

def core_number_check(core_number):
    #Ensure that the number of cores specified is legitimate
    coreNumber = int(core_number)
    if coreNumber < 1:
	output_stream('Minimum of one core required.')
	sys.exit(1)
    maxCoreNumber = multiprocessing.cpu_count()
    if coreNumber > maxCoreNumber:
	output_stream('Cannot exceed maximum number of cores: {}'
                      .format(maxCoreNumber))
	sys.exit(1)
    return coreNumber

def worker(file_list, commands):
    for file in file_list:
	sum_check(file, commands)

def sum_check(in_file, commands):
    """
    Check file for checksums. If values for the md5 and sha256 algorithms do 
    not already exist, compute them and store them with the file
    """
    algorithms = ['md5sum', 'sha256sum']
    for algorithm in algorithms:
        xattr_name = 'user.checksum.{}'.format(algorithm.replace('sum', ''))
        value_computed, compute_err = Popen([commands[algorithm], in_file], \
            stdout=PIPE, stderr=PIPE).communicate()
        value_computed = value_computed.decode(locale.getdefaultlocale()[1]).\
            split(' ')[0]
        value_stored, get_err = Popen([commands['getfattr'], '-n', \
            xattr_name, '--only-values', '--absolute-names', in_file], \
            stdout=PIPE, stderr=PIPE).communicate()
        value_stored = value_stored.decode(locale.getdefaultlocale()[1])
        if not value_stored: #log and store if checksum doesn't already exist
            store_err = Popen([commands['setfattr'], '-n', xattr_name, '-v', \
                value_computed, in_file], stderr=PIPE).communicate()[1]
            if store_err:
                output = store_err.decode(locale.getdefaultlocale()[1])
		output_stream(output, log_file)
        elif value_computed != value_stored: #compare the values
	    output = "{}: {}: checksums do not match".format(os.path.basename(in_file), xattr_name)
	    output_stream(output, log_file)

def main():
    output_stream("Data check started", log_file)
    commands = {'md5sum': '', 'sha256sum': '', 'setfattr': '', 'getfattr': ''}
    #verify that the system has the proper tools installed
    for command in commands.keys():
        proc, proc_err = Popen(['which', command], stdout=PIPE, stderr=PIPE).\
            communicate()
        if proc_err:
            output = "Cannot find {} in system path".format(command)
	    output_stream(output, log_file)
            sys.exit(1)
        commands[command] = proc.decode(locale.getdefaultlocale()[1]).strip()

    #obtain all of the shared data files and calculate their cumulative size
    all_files = []
    total_file_size = 0
    for root, dirs, file_names in os.walk(args.directory):
        for file_name in file_names:
	    hidden = False
	    file_path = root + '/' + file_name
	    split_path = file_path.split('/')
	    for segment in split_path:
		if segment != '..':
		    if segment.startswith('.'):
			hidden = True
	    if not hidden:
		file_status = file_check(file_path)
		if file_status:
		    all_files.append(file_path)
		    total_file_size += os.path.getsize(file_path)
    output_stream('Checking {} bytes of data with {} core(s)'
                  .format(str(total_file_size), str(args.cores)), log_file)

    #divide files into lists of roughly equal size for individual cores to process
    average_file_size = float(total_file_size/args.cores)
    files_per_processor = [[0] for i in range(args.cores)]
    all_files.sort(key = os.path.getsize, reverse = True)
    count = 0
    for file in all_files:
	processorList = files_per_processor[count:] + files_per_processor[:count]
	for processor in processorList:
	    if processor[0] <= average_file_size:
		processor.append(file)
		file_size = os.path.getsize(file)
		processor[0] += file_size
		count = files_per_processor.index(processor) 
		break
	count += 1
	if count == args.cores:
	    count = 0

    #send a list to each core and initiates the process
    jobs = []
    for processor in files_per_processor:
	if len(processor) > 1: #don't intialize jobs with no data to work on
	    partial = processor[1:]
	    p = multiprocessing.Process(target = worker, args = (partial,commands,))
	    jobs.append(p)
	    p.start()
    for p in jobs: #wait for each process to finish before exiting the program
	p.join()
    output_stream('Data check completed', log_file)
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description = "Calcualtes checksum of "
                                     "each file in a given directory and "
                                     "compares it to the existing value")
    parser.add_argument('directory', metavar='DIR',
			type = str,
			help = "directory containing files to check")
    parser.add_argument('-l', '--log', metavar='LOG',
			type = str,
			help = "output to log file")
    parser.add_argument('-c', '--cores',
			type = core_number_check,
			default = 1,
			nargs = '?',
			help = "number of cores to utilize")
    args = parser.parse_args()
    log_file = args.log
    main()

sys.exit(0)
