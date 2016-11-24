#! /usr/bin/env python

"""Verify data integrity via checksums

Copyright:

    derive_pathway+steps.py Obtain gene list from pathway databases
    Copyright (C) 2016  William Brazelton, Alex Hyer, Christopher Thornton

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""

from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import argparse
from glob import iglob
import hashlib
import logging
from multiprocessing import cpu_count, Process, Queue
from multiprocessing.managers import BaseManager
import os
import re
from subprocess import check_output
import sys
from time import localtime, strftime, time

__author__ = 'Alex Hyer'
__credits__ = 'Christopher Thornton'
__email__ = 'theonehyer@gmail.com'
__license__ = 'GPLv3'
__maintainer__ = 'Alex Hyer'
__status__ = 'Production'
__version__ = '0.2.0a5'


class Directory(object):
    """A simple class to wrap and perform functions on files in a directory

    The methods of this class just access the attributes so as to work
    with multiprocessing. Their function should be painfully obvious and
    warrant no individual documentation (except size()).

    Attributes:
        _path (str): absolute path to directory

        _files (list): list of File classes for files in directory
    """

    def __init__(self, path, files):
        """Initialize attributes to store directory data"""

        self._files = files
        self._path = path

    def files(self):
        return self._files

    def path(self):
        return self._path

    def size(self):
        """Calculate and return size of directory in bytes

        Returns:
            int: size of all files in directory
        """

        size = 0
        for path in self._files:
            size += path.size()
        return size


class File(object):
    """A simple class to store file locations, checksums, mtimes, and sizes

    While the data stored in this class is accessible, and often initially
    obtained via the python os library, storing these variables in memory
    probably reduces access time as opposed to asking the OS every time.
    Additionally, this class-based approach definitely simplifies the code.

    The methods of this class just access the attributes so as to work
    with multiprocessing. Their function should be painfully obvious and
    warrant no individual documentation.

    Attributes:
        _path (str): absolute path to file

        _checksum (str): checksum of file

        _mtime (int): time of last file modification in seconds since epoch

        _size (int): size fo file in bytes
    """

    def __init__(self, path, mtime, size):
        """Initialize attributes to store file data"""

        self._path = path
        self._mtime = mtime
        self._size = size
        self._checksum = None

    def checksum(self):
        return self._checksum

    def mtime(self):
        return self._mtime

    def path(self):
        return self._path

    def set_checksum(self, checksum):
        self._checksum = checksum

    def size(self):
        return self._size


class RsyncExclude(object):
    """Class to generate, store, and match rsync-style system path exclusions

    Attributes:
        exclusions (list): list of unicodes of regexs and paths to exclude

        base (unicode): base directory to stem exclusions from
    """

    def __init__(self, exclusions, base=os.path.sep):
        """Initialize instance and generate exclusions"""

        self.exclusions = self.generate_exclusions(base, exclusions)
        self.base = re.sub(os.path.sep + '$', '', base)

    @staticmethod
    def generate_exclusions(base, exclusions):
        """Generate regexes to match exclusion patterns based on rsync

        Args:
            base (unicode): starting path

            exclusions (list): list of unicodes containing paths to ignore

        Return:
            list: list of compiled regex matching paths to exclude
        """

        regexes = []

        # Generate exclusions
        for exclusion in exclusions:

            exclusion = exclusion.encode('unicode-escape')

            # Anchor exclusion to base if stars with path.sep
            # This regex only adds the exclusion to the beginning of the
            # path as the base is removed in exclude().
            # rsync: leading path.sep anchors to start of path
            # rsync: trailing path.sep not anchored to end
            # rsync: all else anchored to end of path
            if exclusion[0] == os.path.sep:
                exclusion = '^' + exclusion
            elif exclusion[-1] != os.path.sep:
                exclusion += '$'

            # Anchor exclusion to end of path if nothing captures path.sep.
            # rsync: if no path.sep (less last char) or '**', match end of path
            temp = re.sub(os.path.sep + '$', '', exclusion)
            if '**' not in temp and os.path.sep not in temp:
                exclusion += '$'

            # Replace unescaped wildcards with non-greedy capture
            # uw matches '*' not flanked by other '*' or preceded by '/'
            # rsync: unescaped '*' matches everything but stopped by path.sep
            uw = re.compile(r'(?<!\\)(?<!\*)\*(?!\*)')
            exclusion = re.sub(uw, r'[^{0}]*'.format(os.path.sep), exclusion)

            # Replace '**' with greedy capture
            # rsync: '**' behaves as '*' but not stopped by path.sep
            exclusion = re.sub(r'\*\*', r'.*', exclusion)

            # Replace unescaped '?' with any single character except slash
            # uc matches '?' not preceded by '\' or '.*'
            # rsync: '?' matches any non-path.sep character
            uc = re.compile(r'(?<!\\)(?<!\.\*)\?')
            exclusion = re.sub(uc, r'[^{0}]?'.format(os.path.sep), exclusion)

            """Notes on other rsync standards:

            rsync: brackets match character class
            Status: Python matches character classes already when re
            compiles them. As such, no need to explicitly address this
            standard.

            rsync: trailing path.sep only matches directory
            # TODO: Add explanation
            """

            regexes.append(re.compile(exclusion))

        return regexes

    def exclude(self, path):
        """Test if path is excluded

        Args:
            path (unicode): path to test

        Return:
            bool: True if path matches an exclusion, else False
        """

        # Remove base to ensure exclusions don't match paths before the base
        path = re.sub('^' + self.base, '', path)

        for exclusion in self.exclusions:

            match = exclusion.search(path)

            if match is not None:
                return True

        return False


class ThreadCheck(argparse.Action):
    """Argparse Action that ensures number of threads requested is valid

    Attributes:
        option_strings (list): list of str giving command line flags that
                               call this action

        dest (str): Namespace reference to value

        nargs (bool): True if multiple arguments specified

        **kwargs (various): optional arguments to pass to super call
    """

    def __init__(self, option_strings, dest, nargs=None, **kwargs):
        """Initialize class and spawn self as Base Class w/o nargs"""

        # Only accept a single value to analyze
        if nargs is not None:
            raise ValueError('nargs not allowed for ThreadCheck')

        # Call self again but without nargs
        super(ThreadCheck, self).__init__(option_strings, dest, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        """Called by Argparse when user specifies multiple threads

        Simply asserts that the number of threads requested is greater than 0
        but not greater than the maximum number of threads the computer
        can support.

        Args:
            parser (ArgumentParser): parser used to generate values

            namespace (Namespace): parse_args() generated namespace

            values (int): actual value specified by user

            option_string (str): argument flag used to call this function

        Raises:
            TypeError: if threads is not an integer

            ValueError: if threads is less than one or greater than number of
                        threads available on computer
        """

        threads = values  # Renamed for readability

        # This try/except should already be taken care of by Argparse
        try:
            assert type(threads) is int
        except AssertionError:
            raise TypeError('{0} is not an integer'.format(str(threads)))

        try:
            assert threads >= 1
        except AssertionError:
            raise ValueError('Must use at least one thread')

        try:
            assert threads <= cpu_count()
        except AssertionError:
            raise ValueError('Cannot use more threads than available: {0}'
                             .format(str(cpu_count())))

        setattr(namespace, self.dest, threads)


def analyze_checksums(queue, hasher, logger):
    """Probes directory for checksum file and compares computed file checksums

    Args:
         queue (Queue): multiprocessing Queue class containing Directory
                        classes to process

         hasher (str): hashing algorithm used to analyze files

         logger (Logger): logging class to log messages
    """

    # Loop until queue contains kill message
    while True:

        d = queue.get()

        # Break on kill message
        if d == 'DONE':
            logger.debug('Daemon received kill signal: exiting')
            break

        logger.debug('Daemon received directory: {0}'.format(d.path()))

        logger.debug('Comparing checksums for files in directory: {0}'
                     .format(d.path()))

        # Ensure directory still exists
        try:
            assert os.path.isdir(d.path()) is True
        except AssertionError:
            logger.warning('Directory no longer exists: {0}'
                           .format(d.path()))
            logger.warning('Skipping directory: {0}'.format(d.path()))
            logger.warning('Files checksums in directory cannot be '
                           'analyzed: {0}'.format(d.path()))
            return None
        else:
            logger.debug('Directory exists: {0}'.format(d.path()))

        logger.debug('Looking for checksum file in directory: {0}'
                     .format(d.path()))

        checksum_file_path = os.path.join(d.path(), hasher + 'sums')
        checksums = {}

        if os.path.isfile(checksum_file_path) is True:

            logger.debug('Found checksum file: {0}'
                         .format(checksum_file_path))

            # Read checksums file into memory
            with open(checksum_file_path, 'r') as file_handle:
                for line in file_handle:
                    line = line.strip().split()
                    checksums[line[-1]] = line[0]

            # Ensure all files listed in checksum file exist
            files = [os.path.basename(path) for path in iglob(d.path() + '/*')]
            for key, value in checksums.items():
                if key not in files:
                    logger.warning('Checksum file {0} contains checksum '
                                   'for non-existent file: {1}'
                                   .format(checksum_file_path, key))

            # Analyze checksums
            for f in d.files():

                file_name = os.path.basename(f.path())

                # Skip non-existent files
                try:
                    assert os.path.isfile(f.path()) is True
                except AssertionError:
                    logger.warning('File no longer exists: {0}'
                                   .format(f.path()))
                    logger.warning('Skipping file checksum comparision: '
                                   '{0}'.format(f.path()))
                    del checksums[file_name]
                    logger.warning('Removed file checksum from memory: {0}'
                                   .format(f.path()))
                    continue

                if file_name in checksums.keys():
                    logger.debug('File checksum stored in checksums file: '
                                 '{0}'.format(f.path()))
                    if f.checksum() == checksums[file_name]:
                        logger.debug('File checksum matches stored '
                                     'checksum: {0}'.format(f.path()))
                        pass
                    else:
                        logger.warning('File checksum differs from stored '
                                       'checksum: {0}'.format(f.path()))
                        local_time = strftime('%Y-%m-%d %H:%M:%S',
                                              localtime(f.mtime()))
                        logger.warning('File {0} last modified: {1}'
                                       .format(f.path(), local_time))
                        checksums[file_name] = f.checksum()
                        logger.warning('Formatted new checksum for '
                                       'checksum file: {0}'.format(f.path()))
                else:
                    logger.info('File checksum not stored in checksum '
                                'file: {0}'.format(f.path()))
                    checksums[file_name] = f.checksum()
                    logger.info('File checksum formatted for checksum '
                                'file: {0}'.format(f.path()))
        else:

            logger.debug('Could not find checksum file in directory: {0}'
                         .format(d.path()))

            logger.info('Formatting file checksums for directory: {0}'
                        .format(d.path()))

            for f in d.files():

                file_name = os.path.basename(f.path())

                # Skip non-existent files
                try:
                    assert os.path.isfile(f.path()) is True
                except AssertionError:
                    logger.warning('File no longer exists: {0}'
                                   .format(f.path()))
                    logger.warning('Skipping file checksum formatting: {0}'
                                   .format(f.path()))
                    continue

                checksums[file_name] = f.checksum()

                logger.info('File checksum formatted: {0}'.format(f.path()))

        # Write checksum file
        try:
            with open(checksum_file_path, 'w') as checksum_handle:
                for key, value in checksums.items():
                    output = value + '  ' + key + os.linesep
                    checksum_handle.write(output)
        except IOError:
            logger.error('Cannot write checksum file: {0}'
                         .format(checksum_file_path))
            pass


def checksum_calculator(queue, hasher, hash_from, logger):
    """Calculate hexadecimal checksum of file from queue using given hasher

    Args:
         queue (Queue): multiprocessing Queue class containing File classes to
                        process

         hasher (function): function from hashlib to compute file checksums

         hash_from (str): 'python' if hasher is a hashlib function and 'linux'
                          if hasher is a *nix hash command

         logger (Logger): logging class to log messages
    """

    # Loop until queue contains kill message
    while True:


        f = queue.get()

        # Break on kill message
        if f == 'DONE':
            logger.debug('Daemon received kill signal: exiting')
            break

        logger.debug('Daemon received file: {0}'.format(f.path()))

        try:
            assert os.path.isfile(f.path()) is True
        except AssertionError:
            logger.warning('File no longer exists: {0}'.format(f.path()))
            logger.warning('Skipping checksum calculation: {0}'
                           .format(f.path()))
            continue

        try:
            assert os.access(f.path(), os.R_OK) is True
        except AssertionError:
            logger.warning('Cannot read file: {0}'.format(f.path()))
            logger.warning('Skipping checksum calculation: {0}'.
                           format(f.path()))
            continue

        logger.debug('Calculating checksum: {0}'.format(f.path()))

        try:
            if hash_from == 'linux':
                f.set_checksum(check_output([hasher, f.path()]).split(' ')[0])
            elif hash_from == 'python':
                # Process file contents in memory efficient manner
                with open(f.path(), 'rb') as file_handle:
                    hexsum = hasher()
                    while True:
                        data = file_handle.read(hasher.block_size)
                        if not data:
                            break
                        hexsum.update(data)
                f.set_checksum(hexsum.hexdigest())
        except (KeyboardInterrupt, SystemExit):  # Exit if asked
            raise
        except Exception as error:  # Skip calculation on all other errors
            logger.error('Suppressed error: {0}'.format(error))
            f.set_checksum(None)
            logger.error('Reset checksum to None: {0}'.format(f.path()))
            logger.error('Skipping checksum calculation: {0}'.
                         format(f.path()))
        else:
            logger.debug('Calculated checksum: {0}'.format(f.path()))


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
    logger.info('Top Directory: {0}'.format(os.path.abspath(args.directory)))
    logger.info('Log Location: {0}'.format(os.path.abspath(args.log)))
    logger.info('Threads: {0}'.format(str(args.threads)))

    # Relate hashing algorithm arg to function for downstream use
    hash_functions = {
        'md5': hashlib.md5,
        'sha1': hashlib.sha1,
        'sha224': hashlib.sha224,
        'sha256': hashlib.sha256,
        'sha384': hashlib.sha384,
        'sha512': hashlib.sha512
    }

    logger.info('Checking for GNU program: {0}'.format(args.algorithm +
                                                       'sum'))

    # In-house tests show that, predictably, Linux GNU commands are much
    # faster than Python's built-in hashlib. Use GNU commands when available.
    # The presence or absence of a sum command influences program flow.
    sum_cmd = which(args.algorithm + 'sum')
    use_sum = True if sum_cmd is not None else False  # Mostly for readability

    if use_sum is True:
        logger.info('Found GNU program: {0}'.format(sum_cmd))
        logger.info('Computing checksums w/ GNU program: {0}'.format(sum_cmd))
    else:
        logger.info('Could not find GNU program: {0}'
                    .format(args.algorithm + 'sum'))
        logger.info('Computing checksums with Python hashing function: {0}'
                    .format(args.algorithm))

    # Create multiprocess manager to handle classes
    BaseManager.register('Directory', Directory)
    BaseManager.register('File', File)
    manager = BaseManager()
    manager.start()
    queue = Queue(args.threads)  # Max queue prevents race condition

    # Variables for use with processing threads
    if use_sum is True:
        hasher = sum_cmd
        hash_from = 'linux'
    else:
        hasher = hash_functions[args.algorithm]
        hash_from = 'python'

    logger.debug('Initializing daemon subprocesses')

    # Initialize daemons to process files
    processes = []
    for i in range(args.threads):
        processes.append(Process(target=checksum_calculator,
                                 args=(queue, hasher, hash_from, logger,)))
        processes[i].daemonize = True
        processes[i].start()

    logger.debug('Initialized {0} daemons'.format(str(len(processes))))

    abs_dir = os.path.abspath(args.directory)

    logger.info('Analyzing file structure from {0} downward'
                .format(abs_dir))

    # Adjust max_depth to correct for starting directory
    max_depth = -1
    if args.max_depth > 0:
        args.recursive = True  # -m implies -r
        max_depth = args.max_depth + abs_dir.count(os.path.sep)
        logger.info('Max Absolute Directory Depth: {0}'.format(str(max_depth)))

    # Obtain directory structure and data, populate queue for above daemons
    dirs = []
    for root, dir_names, file_names in os.walk(abs_dir):

        norm_root = os.path.abspath(os.path.normpath(root))

        logger.debug('Found directory: {0}'.format(norm_root))

        # Skip non-existent directories
        try:
            assert os.path.isdir(norm_root) is True
        except AssertionError:
            logger.warning('Directory no longer exists: {0}'.format(norm_root))
            logger.warning('Skipping directory: {0}'.format(norm_root))
            continue
        else:
            logger.debug('Directory exists: {0}'.format(norm_root))

        # If directory beyond max depth, skip rest of loop
        if norm_root.count(os.path.sep) > max_depth > -1:
            logger.debug('Directory is {0} directories deep: {1}'
                         .format(str(norm_root.count(os.path.sep)),
                                 norm_root))
            logger.debug('Skipping directory: {0}'.format(norm_root))
            continue

        # Skip unreadable directories
        try:
            assert os.access(norm_root, os.R_OK) is True
        except AssertionError:
            logger.warning('Cannot read from directory: {0}'.format(norm_root))
            logger.warning('Skipping directory: {0}'.format(norm_root))
            continue
        else:
            logger.debug('Can read from directory: {0}'.format(norm_root))

        # Warn about un-writeable directories
        try:
            assert os.access(norm_root, os.W_OK) is True
        except AssertionError:
            logger.warning('Cannot write to directory: {0}'.format(norm_root))
            logger.warning('Will attempt to analyze checksums of file anyway')
        else:
            logger.debug('Can write to directory: {0}'.format(norm_root))

        # Skip hidden directories unless specified
        if args.hidden is False:
            parts = norm_root.split(os.path.sep)[1:]
            for part in parts:
                if part[0] == '.':
                    logger.debug('Directory is hidden: {0}'.format(norm_root))
                    logger.debug('Skipping directory: {0}'.format(norm_root))
                    continue

        # Analyze each file in the given directory
        file_classes = []
        for file_name in file_names:

            file_path = os.path.join(norm_root, file_name)

            logger.debug('Found file: {0}'.format(file_path))

            # Skip non-existent files
            try:
                assert os.path.isfile(file_path) is True
            except AssertionError:
                logger.warning('File no longer exists: {0}'.format(file_path))
                logger.warning('Skipping file: {0}'.format(file_path))
            else:
                logger.debug('File exists: {0}'.format(file_path))

            # Skip unreadable files
            try:
                assert os.access(file_path, os.R_OK) is True
            except AssertionError:
                logger.warning('Cannot read file: {0}'.format(file_path))
                logger.warning('Skipping file: {0}'.format(file_path))
                continue
            else:
                logger.debug('Can read file: {0}'.format(file_path))

            # Skip hidden files unless specified
            if args.hidden is False and file_name[0] == '.':
                logger.debug('{0} is hidden: skipping'.format(file_path))
                continue

            # Skip checksum files
            if file_name in ([key + 'sums' for key in hash_functions.keys()]):
                logger.debug('Checksum file found: {0}'.format(file_path))
                logger.debug('Skipping checksum file: {0}'.format(file_path))
                continue

            # Initiate File class and store attributes
            mtime = os.path.getmtime(file_path)
            size = os.path.getsize(file_path)
            file_class = manager.File(file_path, mtime, size)
            file_classes.append(file_class)

            logger.debug('Initialized class for file: {0}'.format(file_path))

            queue.put(file_class)

            logger.debug('File placed in processing queue: {0}'
                         .format(file_path))

        # Initialize Directory and pass File handles
        directory = manager.Directory(norm_root, file_classes)
        dirs.append(directory)

        logger.debug('Initialized class for directory: {0}'.format(norm_root))

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

    logger.info('Comparing file checksums to stored checksums')

    logger.debug('Initializing daemon subprocesses')

    # Initialize daemons to compare checksums
    queue2 = Queue(args.threads)  # Max queue prevents race condition
    processes2 = []
    for i in range(args.threads):
        processes2.append(Process(target=analyze_checksums,
                                  args=(queue2, args.algorithm, logger,)))
        processes2[i].daemonize = True
        processes2[i].start()

    logger.debug('Initialized {0} daemons'.format(str(len(processes2))))

    for d in dirs:
        queue2.put(d)
        logger.debug('Directory placed in processing queue: {0}'
                     .format(d.path()))

    logger.debug('Populating end of queue with kill messages')

    # Send a kill message to each thread via queue
    for i in processes2:
        queue2.put('DONE')

    logger.debug('Waiting for daemons to complete')

    # Wait for each process to complete before continuing
    for process in processes2:
        process.join()
        logger.debug('A daemon has exited')

    logger.debug('All daemons have exited')

    logger.info('Checksum comparisons complete')

    # Calculate and log end of program run
    end = time()
    total_size = float(sum([d.size() for d in dirs])) / 1073741824.0
    total_time = (end - start) / 60.0

    logger.info('Analyzed {0:.2e} GB of data in {1:.2e} minutes'
                .format(total_size, total_time))

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
    parser.add_argument('-d', '--hidden',
                        action='store_true',
                        help='check files in hidden directories and hidden '
                             'files')
    parser.add_argument('-l', '--log',
                        type=str,
                        default='syslog',
                        help='log file to write output')
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
                        action=ThreadCheck,
                        type=int,
                        default=1,
                        help='number of threads to run check with')
    args = parser.parse_args()

    main(args)

sys.exit(0)
