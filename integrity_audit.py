#! /usr/bin/env python

from __future__ import division
from __future__ import print_function

"""Verify data integrity via checksums


"""

import argparse
import hashlib
import logging
from multiprocessing import Process, Queue
import os
from subprocess import check_output
import sys
from time import time

__author__ = 'Alex Hyer'
__credits__ = 'Christopher Thornton'
__email__ = 'theonehyer@gmail.com'
__license__ = 'GPLv3'
__maintainer__ = 'Alex Hyer'
__status__ = 'Alpha'
__version__ = '0.0.1a8'


class Directory:
    """A simple class to wrap and perform functions on files in a directory

    Attributes:
        path (str): absolute path to directory

        files (list): list of File classes for files in directory
    """

    def __init__(self, path, files):
        """Initialize attributes to store directory data"""

        self.path = path
        self.files = files

    def size(self):
        """Calculate and return size of directory in bytes

        Returns:
            int: size of all files in directory
        """

        size = 0
        for path in self.files:
            size += path.size
        return size


class File:
    """A simple class to store file locations, checksums, mtimes, and sizes

    While the data stored in this class is accessible, and often initially
    obtained via the python os library, storing these variables in memory
    probably reduces access time as opposed to asking the OS every time.
    Additionally, this class-based approach definitely simplifies the code.

    Attributes:
        path (str): absolute path to file

        checksum (str): checksum of file

        mtime (int): time of last file modification in seconds since epoch

        size (int): size fo file in bytes
    """

    def __init__(self, path):
        """Initialize attributes to store file data"""

        self.path = path
        self.checksum = None
        self.mtime = None
        self.size = None


def sum_calculator(queue, hasher, hash_from, logger):
    """Calculate hexadecimal checksum of file from queue using given hasher

    Args:
         queue (Queue): multiprocessing Queue class containing File classes to
                        process

         hasher (function): function from hashlib to compute file checksums

         hash_from (str): 'python' if hasher is a hashlib function and 'linux'
                          if hasher is a *nix hash command

        logger (Logger): logging class to log progress
    """

    # Loop until queue contains kill message
    while True:
        f = queue.get()

        logger.debug('Daemon got file: {0}'.format(f.path))

        # Break on kill message
        if f == 'DONE':
            logger.debug('Daemon got kill signal: exiting')
            break

        logger.debug('Calculating checksum for {0}'.format(f.path))

        if hash_from == 'linux':
            f.checksum = check_output(hasher, f.path).split(' ')[0]
        elif hash_from == 'python':
            # Process file contents in memory efficient manner
            with open(f.path, 'rb') as file_handle:
                hexsum = hasher()
                while True:
                    data = file_handle.read(hasher.block_size)
                    if not data:
                        break
                    hexsum.update(data)
            f.checksum = hexsum.hexdigest()

        logger.debug('Calculated checksum for {0}'.format(f.path))


# This method is literally just the Python 3.5.1 which function from the
# shutil library in order to permit this functionality in Python 2.
# Minor changes to style were made to account for indentation.
def which(cmd, mode=os.F_OK | os.X_OK, path=None):
    """Given a command, mode, and a PATH string, return the path which
    conforms to the given mode on the PATH, or None if there is no such
    file.
    `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
    of os.environ.get("PATH"), or can be overridden with a custom search
    path.
    """

    # Check that a given file can be accessed with the correct mode.
    # Additionally check that `file` is not a directory, as on Windows
    # directories pass the os.access check.
    def _access_check(fn, mode):
        return (os.path.exists(fn) and os.access(fn, mode)
                and not os.path.isdir(fn))

    # If we're given a path with a directory part, look it up directly
    # rather than referring to PATH directories. This includes checking
    # relative to the current directory, e.g. ./script
    if os.path.dirname(cmd):
        if _access_check(cmd, mode):
            return cmd
        return None

    if path is None:
        path = os.environ.get("PATH", os.defpath)
    if not path:
        return None
    path = path.split(os.pathsep)

    if sys.platform == "win32":
        # The current directory takes precedence on Windows.
        if not os.curdir in path:
            path.insert(0, os.curdir)
        # PATHEXT is necessary to check on Windows.
        pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
        # See if the given file matches any of the expected path
        # extensions. This will allow us to short circuit when given
        # "python.exe". If it does match, only test that one, otherwise
        # we have to try others.
        if any(cmd.lower().endswith(ext.lower()) for ext in
               pathext):
            files = [cmd]
        else:
            files = [cmd + ext for ext in pathext]
    else:
        # On other platforms you don't have things like PATHEXT to tell you
        # what file suffixes are executable, so just pass on cmd as-is.
        files = [cmd]

    seen = set()
    for dir in path:
        normdir = os.path.normcase(dir)
        if not normdir in seen:
            seen.add(normdir)
            for thefile in files:
                name = os.path.join(dir, thefile)
                if _access_check(name, mode):
                    return name
    return None


def main(args):
    """Control program flow

    Arguments:
        args (ArgumentParser): args to control program options
    """

    # Setup logging
    log_level = {
        'debug': logging.DEBUG,
        'info': logging.INFO,
        'warning': logging.WARNING,
        'error': logging.ERROR,
        'critical': logging.CRITICAL
    }

    logger = logging.getLogger('integrity_audit')
    logger.setLevel(log_level[args.log_level])
    if args.log == 'syslog':
        handler = logging.handlers.SysLogHandler(address='/dev/log')
        formatter = logging.Formatter(
            '%(name)s - %(levelname)s: %(message)s')
    else:
        handler = logging.FileHandler(filename=args.log)
        formatter = logging.Formatter(
            '%(asctime)s %(name)s - %(levelname)s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    start = time()

    # Log startup information
    logger.info('Starting integrity_audit')
    logger.info('Command: {0}'.format(' '.join(sys.argv)))
    logger.info('Logging to {0}'.format(args.log))
    logger.info('Will use {0} threads'.format(str(args.threads)))

    # Relate hashing algorithm arg to function for downstream use
    hash_functions = {
        'md5': hashlib.md5,
        'sha1': hashlib.sha1,
        'sha224': hashlib.sha224,
        'sha256': hashlib.sha256,
        'sha384': hashlib.sha384,
        'sha512': hashlib.sha512
    }

    logger.info('Checking for *nix prgram: {0}'.format(args.algorithm + 'sum'))

    # In-house tests show that, predictably, Linux *sum commands are much
    # faster than Python's built-in hashlib. Use *sum commands when available.
    # The presence or absence of a sum command greatly influences program flow.
    sum_cmd = which(args.algorithm + 'sum')
    use_sum = True if sum_cmd is not None else False

    if use_sum is True:
        logger.info('Found *nix program: {0}'.format(args.algorithm + 'sum'))
        logger.info('Computing checksums with {0}'.format(sum_cmd))
    else:
        logger.info('Could not find *nix program: {0}'
                    .format(args.algorithm + 'sum'))
        logger.info('Computing checksums with Python {0} function'
                    .format(args.algorithm))

    # Variables for use with processing threads
    queue = Queue()
    processes = []
    if use_sum is True:
        hasher = hash_functions[args.algorithm]
        hash_from = 'linux'
    else:
        hasher = sum_cmd
        hash_from = 'python'

    logger.debug('Initializing daemon subprocesses')

    # Initialize daemons to process
    for i in range(args.threads):
        processes.append(Process(target=sum_calculator,
                                 args=(queue, hasher, hash_from, logger,)))
        processes[i].daemonize = True
        processes[i].start()

    logger.debug('Intialized {0} daemons'.format(str(len(processes))))

    logger.info('Analyzing file structure from {0} downward'
                .format(args.directory))

    # Obtain directory structure and data, populate queue for above daemons
    dirs = []
    args.recursive = True if args.max_depth > 0 else False  # -m implies -r
    for root, dir_names, file_names in os.walk(args.directory):

        norm_root = os.path.normpath(root)

        logger.debug('Found directory: {0}'.format(norm_root))

        # If directory beyond max depth, skip rest of loop
        if norm_root.count(os.path.sep) > args.max_depth > -1:
            logger.debug('{0} is {1} directories deep: skipping'
                         .format(norm_root, str(norm_root.count(os.path.sep))))
            continue

        # Skip hidden directories unless specified
        if args.hidden is False:
            parts = root.split(os.path.sep)
            for part in parts:
                if part[0] == '.':
                    logger.debug('{0} is hidden: skipping'.format(norm_root))
                    continue

        # Analyze each file in the given directory
        file_classes = []
        for file_name in file_names:

            file_path = os.path.join(norm_root, file_name)

            logger.debug('Found file: {0}'.format(file_path))

            # Skip hidden files unless specified
            if args.hidden is False and file_name[0] == '.':
                logger.debug('{0} is hidden: skipping'.format(file_path))
                continue

            # Skip checksum files
            for key in hash_functions.keys():
                if file_name.endswith(key + 'sum'):
                    logger.debug('{0} is a checksum file: skipping'
                                 .format(file_path))
                    continue

            logger.debug('Initializing class for {0}'.format(file_path))

            # Initiate File class and store attributes
            file_class = File(file_path)
            file_class.mtime = os.path.getmtime(file_path)
            file_class.size = os.path.getsize(file_path)
            file_classes.append(File(file_path))

            logger.debug('Initialized class for {0}'.format(file_path))

            queue.put(file_classes)

            logger.debug('Class placed in processing queue')

        logger.debug('Initializing class for {0}'.format(norm_root))

        # Initialize directory and pass File handles
        directory = Directory(norm_root, file_classes)
        dirs.append(directory)

        logger.debug('Initialized class for {0}'.format(norm_root))

        # Break loop on first iteration if not recursive
        if args.recursive is False:
            logger.debug('Recursion deactivated: stopping analysis')
            break

    logger.info('File structure analysis complete')

    logger.debug('Populating end of queue with kill messages')

    # Send a kill message to each thread via queue
    for i in processes:
        queue.put('DONE')

    logger.debug('Waiting for daemons to complete')

    # Wait for each process to complete before continuing
    for process in processes:
        process.join()
        logger.debug('A daemon has exited')

    logger.debug('All daemons have exited')

    logger.info('All file checksums calculated')

    # TODO: Add checking checksums in a directory
    # TODO: Add writing checksum files to directory

    # Calculate and log end of program run
    end = time.time()
    total_size = float(sum([dir.size() for dir in dirs])) / 1073741824.0
    total_time = (end - start) / 60.0

    logger.info('Analyzed {0} GB of data in {1} minutes'
                .format(str(total_size), total_time))

    logger.info('Exiting integrity_audit')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.
                                     RawDescriptionHelpFormatter)
    parser.add_argument('directory', metavar='dir',
                        type=str,
                        help='directory containing files to check')
    parser.add_argument('-a', '--algorithm',
                        type=str,
                        default='sha512',
                        choices=['md5',
                                 'sha1',
                                 'sha224',
                                 'sha256',
                                 'sha384',
                                 'sha512'],
                        help='algorithm used to perform checksums')
    parser.add_argument('-l', '--log',
                        type=str,
                        default='syslog',
                        help='log file to write output')
    parser.add_argument('-d', '--hidden',
                        action='store_true',
                        help='check files in hidden directories and hidden '
                             'files')
    parser.add_argument('-r', '--recursive',
                        action='store_true',
                        help='check files in all subdirectories')
    parser.add_argument('-m', '--max_depth',
                        type=int,
                        default=-1,
                        help='max number of subdirectory levels to check, '
                             'implies "-r"')
    parser.add_argument('-o', '--log_level',
                        type=str,
                        default='info',
                        choices=[
                            'debug',
                            'info',
                            'warning',
                            'error',
                            'critical'
                        ],
                        help='minimum level to log messages')
    parser.add_argument('-t', '--threads',
                        type=int,
                        default=1,
                        help='number of threads to run check with')
    args = parser.parse_args()

    main(args)

sys.exit(0)
