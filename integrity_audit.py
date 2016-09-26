#! /usr/bin/env python

from __future__ import print_function

"""Verify data integrity via checksums


"""

import argparse
from multiprocessing import Process, Queue
import os
import sys

__author__ = 'Alex Hyer'
__credits__ = 'Christopher Thornton'
__email__ = 'theonehyer@gmail.com'
__license__ = 'GPLv3'
__maintainer__ = 'Alex Hyer'
__status__ = 'Alpha'
__version__ = '0.0.1a4'


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
    """A simple class to store file locations, checksums, and sizes

    While the data stored in this class is accessible, and often initially
    obtained via the python os library, storing these variables in memory
    probably reduces access time as opposed to asking the OS every time.
    Additionally, this class-based approach definitely simplifies the code.

    Attributes:
        path (str): absolute path to file

        checksum (str): checksum of file

        size (int): size of file in bytes
    """

    def __init__(self, path):
        """Initialize attributes to store file data"""

        self.path = path
        self.checksum = None
        self.size = None


def sum_cmd_calculator(queue, sum_cmd):
    """

    Args:
         queue (Queue): multiprocessing Queue class containing Directory
                        classes to process

         sum_cmd (str): path to executable *nix checksum command
    """

    pass


def sum_py_calculator(queue):
    """

    Args:
         queue (Queue): multiprocessing Queue class containing File classes to
                        process
    """

    pass


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

    # In-house tests show that, predictably, Linux *sum commands are much
    # faster than Python's built-in hashlib. Use *sum commands when available.
    # The presence or absence of a sum command greatly influences program flow.
    sum_cmd = which(args.algo + 'sum')
    use_sum = True if sum_cmd is not None else False

    # Variables for use with multiprocessing module
    queue = Queue()
    processes = []

    # Initialize daemons to process checksums
    if use_sum:
        for i in range(args.threads):
            processes.append(Process(target=sum_cmd_calculator,
                                     args=(queue, sum_cmd,)))
            processes[i].daemonize = True
            processes[i].start()
    else:
        for i in range(args.threads):
            processes.append(Process(target=sum_py_calculator,
                                     args=(queue,)))
            processes[i].daemonize = True
            processes[i].start()

    # Obtain directory structure and data
    dirs = []
    args.recursive = True if args.max_depth > 0 else False  # -m implies -r
    for root, dir_names, file_names in os.walk(args.directory):

        # If directory beyond max depth, skip rest of loop
        if root.count(os.path.sep) > args.max_depth > -1:
            continue

        norm_root = os.path.normpath(root)

        # Skip hidden directories unless specified
        if args.hidden is False:
            parts = root.split(os.path.sep)
            for part in parts:
                if part[0] == '.':
                    continue

        # Analyze each file in the given directory
        file_classes = []
        for file_name in file_names:

            # Skip hidden files unless specified
            if args.hidden is False and file_name[0] == '.':
                continue

            # Initiate File class and store attributes
            file_path = os.path.join(norm_root, file_name)
            file_class = File(file_path)
            file_class.size = os.path.getsize(file_path)
            file_classes.append(File(file_path))

            # Send file to queue for processing
            if not use_sum:
                queue.put(file_classes)

        # Initialize directory and pass File handles
        directory = Directory(norm_root, file_classes)
        dirs.append(directory)

        # Send directory to queue for processing
        if use_sum:
            queue.put(directory)

        # Break loop on first iteration if not recursive
        if args.recursive is False:
            break

    # TODO: Add writing checksum files to directory


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.
                                     RawDescriptionHelpFormatter)
    parser.add_argument('directory', metavar='dir',
                        type=str,
                        help='directory containing files to check')
    parser.add_argument('-l', '--log',
                        type=argparse.FileType('a'),
                        help='log file to write output [Default: syslog]')
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
    parser.add_argument('-r', '--recursive',
                        action='store_true',
                        help='check files in all subdirectories')
    parser.add_argument('-m', '--max_depth',
                        type=int,
                        default=-1,
                        help='max number of subdirectory levels to check, '
                             'implies "-r"')
    parser.add_argument('-t', '--threads',
                        type=int,
                        default=1,
                        help='number of threads to run check with')
    args = parser.parse_args()

    main(args)

sys.exit(0)
