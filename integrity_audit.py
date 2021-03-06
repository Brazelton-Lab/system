#! /usr/bin/env python

"""Verify data integrity via checksums

Copyright:

    integrity_audit.py Validate checksums of files
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
__version__ = '0.3.0'


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


class RsyncRegexes(object):
    """Class to generate, store, and match rsync-style system path regexes

    This class converts rsync-esque patterns available at:

    https://linux.die.net/man/1/rsync

    into Python regexes and stores them. The instance can then be queried to
    see if a specific path is to be included or excluded given the stored
    regexes. A given instance can be in either 'include' mode where a path
    matching a given regex is to be included, or 'exclude' mode where a path
    matching a given regex is to be excluded. The exclude() and include()
    methods evaluate a given path and return whether a given path is to be
    included or excluded based on the instance's regexes and mode. Perhaps
    the most useful method in this class if walk(). walk() wraps os.walk
    and removes excluded files and directories before yielding results.
    In essence, this class provides a simple interface for converting
    rsync patterns into python regexes allowing programs to provide users
    access to the familiarity of rsync patterns in Python programs.

    Attributes:
        mode (str): ['include', 'exclude'] determines if a path
                    matching a pattern should be included or excluded

        patterns (list): list of str of rsync-style patterns to match
                         paths against
    """

    def __init__(self, mode, patterns=None):
        """Verify input, initialize instance, and generate regexes"""

        mode = mode.lower()
        try:
            assert mode in ['include', 'exclude']
        except AssertionError:
            raise AssertionError('Mode must be "include" or "exclude"')

        if patterns is None:
            patterns = []

        self.mode = mode
        self.regexes = self.generate_rsync_regexes(patterns)

    @staticmethod
    def generate_rsync_regexes(patterns):
        """Generate regexes to match rsync patterns

        Args:
            patterns (list): list of str containing rsync patterns to
                             convert to Python regexes

        Returns:
            list: list of compiled regexes matching paths to match

        Examples:
            >>> [i.pattern for i in
            ...  RsyncRegexes.generate_rsync_regexes(['.git**', 'test/',
            ...                                       'hello*world.txt'])]
            ['.git.*', 'test/$', 'hello[^/]*world.txt$']

            >>> [i.pattern for i in
            ...  RsyncRegexes.generate_rsync_regexes(['?1.csv', '**.py'])]
            ['[^/]?1.csv$', '.*.py']
        """

        regexes = []

        # Change single entry to list format for ease of use
        if type(patterns) is unicode or type(patterns) is str:
            patterns = [patterns]

        # Generate patterns
        for pattern in patterns:

            pattern = pattern.encode('unicode-escape')

            # Anchor pattern to base if stars with path.sep
            # This regex only anchors the pattern to the beginning of the
            # path instead of adding the base to the beginning of the path
            # as the base is removed in walk().
            # rsync: leading path.sep anchors to start of path
            if pattern[0] == os.path.sep:
                pattern = '^' + pattern

            # Anchor pattern to end of path if nothing captures path.sep.
            # Anchoring trailing path.sep to end of string will work in an
            # rsync-esque manner because the walk function will not descend
            # into excluded directories.
            # rsync: if no path.sep (less last char) or '**', match end of path
            temp = re.sub(os.path.sep + '\$?$', '', pattern)
            if '**' not in temp and os.path.sep not in temp:
                pattern += '$'

            # Replace unescaped wildcards with non-greedy capture.
            # uw matches '*' not flanked by other '*' or preceded by '\'.
            # rsync: unescaped '*' matches everything but stopped by path.sep
            uw = re.compile(r'(?<!\\)(?<!\*)\*(?!\*)')
            pattern = re.sub(uw, r'[^{0}]*'.format(os.path.sep), pattern)

            # Replace '**' with greedy capture.
            # rsync: '**' behaves as '*' but not stopped by path.sep.
            pattern = re.sub(r'\*\*', r'.*', pattern)

            # Replace unescaped '?' with any single character except slash.
            # uc matches '?' not preceded by '\'.
            # rsync: '?' matches any non-path.sep character
            uc = re.compile(r'(?<!\\)\?')
            pattern = re.sub(uc, r'[^{0}]?'.format(os.path.sep), pattern)

            """Notes on implicitly-implemented rsync standard:

            rsync: brackets match character class
            Status: Python matches character classes already when re
            compiles them. As such, no need to explicitly address this
            standard.
            """

            regexes.append(re.compile(pattern))

        return regexes

    def add_patterns(self, patterns):
        """Add patterns to match to self

        This function is not strictly necessary, but is highly convenient.

        Args:
             patterns (list): list of str rsync patterns to convert to
                              Python regexes and add to instance's list of
                              regexes

        Example:
            >>> r = RsyncRegexes('exclude', 'hello?world.py')
            >>> [i.pattern for i in r.regexes]
            ['hello[^/]?world.py$']
            >>> r.add_patterns(['goodbye**', 'python?'])
            >>> [i.pattern for i in r.regexes]
            ['hello[^/]?world.py$', 'goodbye.*', 'python[^/]?$']
        """

        # Change single entry to list format for ease of use
        if type(patterns) is str:
            patterns = [patterns]

        self.regexes += self.generate_rsync_regexes(patterns)

    def exclude(self, path, base=None):
        """Test if path is excluded as per instance regexes

        Args:
            path (str): path to match against self.regexes

            base (str): if provided, removes base from beginning of path
                        so regexes can't match base

        Returns:
            bool: True if path is to be excluded, else False
                  This function will return the boolean appropriate for the
                  instance's mode (self.mode).

        Examples:
            >>> r = RsyncRegexes('exclude', 'hello?world.py')
            >>> r.exclude('hello_world.py')
            True
            >>> r.exclude('bye_world.py')
            False
            >>> r = RsyncRegexes('include', 'hello?world.py')
            >>> r.exclude('hello_world.py')
            False
            >>> r.exclude('bye_world.py')
            True
        """

        # Determine whether or not a path is an absolute directory
        is_abs_dir = False
        if os.path.isdir(path) is True and os.path.islink(path) is False:
            is_abs_dir = True

        # Remove base from path
        if base is not None:
            path = path[len(base):]

        for regex in self.regexes:

            # If pattern ends in path.sep, only match directories
            # rsync: patterns ending in path.sep only match non-link dirs
            temp = re.sub('\$?$', '', regex.pattern)
            if temp[-1] == os.path.sep and is_abs_dir is False:
                continue

            match = regex.search(path)

            if match is not None:
                if self.mode == 'exclude':
                    return True  # Exclude path
                elif self.mode == 'include':
                    return False  # Include path

        if self.mode == 'exclude':
            return False  # Include path
        elif self.mode == 'include':
            return True  # Exclude path

    def include(self, path, base=None):
        """Test if path is included as per instance regexes

        Args:
            path (str): path to match against self.regexes

            base (str): if provided, removes base from beginning of path
                        so regexes can't match base

        Returns:
            bool: True if path is to be included, else False
                  This function will return the boolean appropriate for the
                  instance's mode (self.mode).

        Examples:
            >>> r = RsyncRegexes('exclude', 'hello?world.py')
            >>> r.include('hello_world.py')
            False
            >>> r.include('bye_world.py')
            True
            >>> r = RsyncRegexes('include', 'hello?world.py')
            >>> r.include('hello_world.py')
            True
            >>> r.include('bye_world.py')
            False
        """

        return not self.exclude(path, base=base)

    def walk(self, path, hidden=False, **kwargs):
        """Mimic os.walk but excludes dirs and files as per instance regexes

        Args:
            path (str): top directory to walk down from

            hidden (bool): skip hidden files and directories if False, include
                           them if True

            **kwargs: arbitrary keyword arguments to pass to os.walk

        Yields:
            tuple: os.walk tuple mimic. Namely, first item is a str of
                   root directory for current iteration, second item is a list
                   of directories in root, and third item is a list of files
                   is root. Only directory and file names not to be excluded
                   are yielded. Un-yielded directories will not be further
                   transversed.

        Example:
            >>> r = RsyncRegexes('include', 'hello?world.py')
            >>> for root,  dirs, files in r.walk('/path/to/test/dir/'):
            ...     print(root, dirs, files)
            ('/', ['dir1', 'dir2'], ['file1', 'file2'])
        """

        # Ensure path ends with path.sep so base can be passed to exclude
        if path[-1] != os.path.sep:
            path += os.path.sep

        for root, dir_names, file_names in os.walk(path, topdown=True,
                                                   **kwargs):

            # Remove excluded directories
            remove_dir = []
            for _dir in dir_names:
                m_dir = os.path.join(root, _dir) + os.path.sep
                if self.exclude(m_dir, base=path) is True:
                    remove_dir.append(_dir)
                elif hidden is False and _dir[0] == '.':
                    remove_dir.append(_dir)
            dir_names[:] = list(set(dir_names) - set(remove_dir))

            # Remove excluded files
            remove_files = []
            for _file in file_names:
                m_file = os.path.join(root, _file)
                if self.exclude(m_file, base=path) is True:
                    remove_files.append(_file)
                elif hidden is False and _file[0] == '.':
                    remove_files.append(_file)
            file_names[:] = list(set(file_names) - set(remove_files))

            yield root, dir_names, file_names


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


def analyze_checksums(queue, hasher, logger, read_only):
    """Probes directory for checksum file and compares computed file checksums

    Args:
         queue (Queue): multiprocessing Queue class containing Directory
                        classes to process

         hasher (str): hashing algorithm used to analyze files

         logger (Logger): logging class to log messages

         read_only (bool): if True, does not write checksum file
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

            if read_only is True:
                logger.warning('Read-Only Mode active')
                logger.warning('Skipping directory: {0}'.format(d.path()))
                continue

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
        if read_only is False:
            try:
                with open(checksum_file_path, 'w') as checksum_handle:
                    for key, value in checksums.items():
                        output = value + '  ' + key + os.linesep
                        checksum_handle.write(output)
            except IOError:
                logger.error('Cannot write checksum file: {0}'
                             .format(checksum_file_path))
                pass
        else:
            logger.debug('Read-Only Mode active')
            logger.debug('Skipping writing checksum file: {0}'
                         .format(d.path()))


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
    logger.info('Read-Only Mode: {0}'.format(str(args.read_only)))

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
    algo = args.algorithm + 'sums'

    if use_sum is True:
        logger.info('Found GNU program: {0}'.format(sum_cmd))
        logger.info('Computing checksums w/ GNU program: {0}'.format(sum_cmd))
    else:
        logger.info('Could not find GNU program: {0}'
                    .format(args.algorithm + 'sum'))
        logger.info('Computing checksums with Python hashing function: {0}'
                    .format(args.algorithm))

    # Generate regexes of files/folder to include or exclude
    if args.exclude is not None:
        path_filter = RsyncRegexes('exclude', args.exclude)
        logger.info('Excluding files and folders matching --exclude patterns')
        for exclude in args.exclude:
            logger.debug('Exclude Pattern: {0}'.format(exclude))
    elif args.include is not None:
        path_filter = RsyncRegexes('include', args.include)
        logger.info('Including only files and folders matching --include '
                    'patterns')
        for include in args.include:
            logger.debug('Include Pattern: {0}'.format(include))
    else:
        path_filter = RsyncRegexes('exclude', [])

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
    for root, dir_names, file_names in path_filter.walk(abs_dir,
                                                        hidden=args.hidden):

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

        # Skip directories w/o checksum files in read-only mode
        if args.read_only is True and algo not in file_names:
            logger.warning('Directory does not contain file {0}: {1}'
                           .format(algo, norm_root))
            logger.warning('Skipping directory: {0}'.format(norm_root))
            continue

        # Warn about un-writeable directories
        try:
            assert os.access(norm_root, os.W_OK) is True
        except AssertionError:
            logger.warning('Cannot write to directory: {0}'.format(norm_root))
            logger.warning('Will attempt to analyze checksums of file anyway')
        else:
            logger.debug('Can write to directory: {0}'.format(norm_root))

        # Analyze each file in the given directory
        file_classes = []
        for file_name in file_names:

            file_path = os.path.join(norm_root, file_name)

            logger.debug('Found file: {0}'.format(file_path))

            # Skip non-existent files
            try:
                assert os.path.exists(file_path) is True
            except AssertionError:
                logger.warning('File no longer exists: {0}'.format(file_path))
                logger.warning('Skipping file: {0}'.format(file_path))
                continue
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

            # Skip special files
            try:
                assert (os.path.isfile(file_path) \
                    and not os.path.islink(file_path)) is True
            except AssertionError:
                logger.debug('{0} is a special file: skipping'.format(file_path))
                continue
            else:
                logger.debug('File exists and is a regular file: {0}'
                             .format(file_path))

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
                                  args=(queue2, args.algorithm, logger,
                                        args.read_only)))
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
    patterns = parser.add_mutually_exclusive_group()
    patterns.add_argument('-e', '--exclude',
                          default=None,
                          nargs='+',
                          help='rsync patterns of files and folder to exclude '
                               'from audit')
    patterns.add_argument('-i', '--include',
                          default=None,
                          nargs='+',
                          help='rsync patterns of files and folder to include '
                               'from audit, anything not matching an include '
                               'pattern is excluded')
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
    parser.add_argument('-n', '--read_only',
                        action='store_true',
                        help='skips writing checksum files and doesn\'t '
                             'analyze directories w/o checksum files')
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
