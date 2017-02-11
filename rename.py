#! /usr/bin/env python
"""
This program is for renaming files (through symbolic links) using a file
conversion table. The columns should be ordered as so: new directory, new id,
old directory, old file name. Columns can be separated using any standard
ASCII character.

If files are paired-end and follow the standard conventions for discriminating
forward from reverse reads (R1 and R2), then an asterics (*) can be used after
the file name (e.g samplename1_R*) instead of specifying each paired file
individually. The linked pairs will be differentiated using "forward" and
"reverse" in place of "R1" and "R2".
"""

from __future__ import print_function

import argparse
import sys
import glob
import textwrap
from itertools import izip
from subprocess import Popen, PIPE

def format_io(old_name, new_name, ext=''):
    extensions = {'fa': 'fasta', 'fasta': 'fasta', 'fna': 'fasta', 
        'fq': 'fastq', 'fastq': 'fastq', 'fnq': 'fastq'}
    compress = ''

    if ext:
        file_end = ext
    else:
        old_name = old_name.split('.')
        filetype = old_name[-1]
        if filetype in ["gz", "bz2", "zip"]:
            compress = ".{}".format(filetype)
            filetype = old_name[-2]

        try:
            extension = extensions[filetype]
        except KeyError:
             print(textwrap.fill("Error: unknown file type. Please make sure "
                "the filenames end in one of the supported file extensions "
                "(fa, fna, fasta, fq, fnq, fastq)", 79), file=sys.stderr)
             sys.exit(1)        
        file_end = extensions[filetype] + compress

    return "{}.{}".format(new_name, file_end)

def main():
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('infile',
        help="input conversion table file")
    parser.add_argument('-e', '--ext',
        help="extension of renamed file (optional)")
    parser.add_argument('-s', '--sep',
        default=',',
        help="field separator character [default: ,]")
    args = parser.parse_args()

    with open(args.infile, 'rU') as in_h:
        for line in in_h:
            try:
                new_dir, new_id, old_dir, old_name = line.split(args.sep)
            except ValueError:
                print(textwrap.fill("Error: failed to properly parse {}. The "
                    "conversion table should contain four columns. See usage "
                    "for details".format(infile), 79), file=sys.stderr)
                sys.exit(1)
            if old_name[-1] == '*':
                forwards = sorted(glob.glob('{}/{}*R1_*'.format(old_dir, old_name[:-1])))
                reverses = sorted(glob.glob('{}/{}*R2_*'.format(old_dir, old_name[:-1])))
                if len(forwards) != len(reverse):
                    print(textwrap.fill("Error: missing pair. The use of '*' "
                        "should only be used for paired-end reads in separate "
                        "files", 79), file=sys.stderr)
                    sys.exit(1)
                if len(forwards) > 1:
                    add_int = True
                else:
                    add_int = False

                i = 1
                for forward, reverse in izip(forwards, reverses):
                    if add_int:
                        new_f = format_io(forward, "{}.forward.{!s}".format(new_id, i.zfill(3)), args.ext)
                        new_r = format_io(reverse, "{}.reverse.{!s}".format(new_id, i.zfill(3)), args.ext)
                    else:
                        new_f = format_io(forward, "{}.forward".format(new_id), args.ext)
                        new_r = format_io(reverse, "{}.reverse".format(new_id), args.ext)

                    ln_out, ln_err = (Popen(['ln', "-s", forward, "{}/{}".format(new_dir, new_f)], 
                        stdout=PIPE, stderr=PIPE).communicate())
                    if ln_err:
                        print(ln_err.decode(locale.getdefaultlocale()[1]), 
                            file=sys.stderr)
                    ln_out, ln_err = (Popen(['ln', "-s", reverse, "{}/{}".format(new_dir, new_r)], 
                        stdout=PIPE, stderr=PIPE).communicate())
                    if ln_err:
                        print(ln_err.decode(locale.getdefaultlocale()[1]), 
                            file=sys.stderr)
                    i += 1
            else:
                new_name = format_io(old_name, new_id, args.ext)
                new_path = new_dir + "/" + new_name
                old_path = old_dir + "/" + old_name

                ln_out, ln_err = (Popen(['ln', "-s", old_path, new_path], stdout=PIPE, stderr=PIPE)
                .communicate())
                if ln_err:
                    print(ln_err.decode(locale.getdefaultlocale()[1]), file=sys.stderr)

if __name__ == '__main__':
    main()
    sys.exit(0)
