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
import glob
import locale
import re
import sys
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
        filetype = old_name[-1].strip()
        if filetype in ["gz", "bz2", "zip"]:
            compress = ".{}".format(filetype)
            filetype = old_name[-2]

        try:
            extension = extensions[filetype]
        except KeyError:
             print(textwrap.fill("Error: unknown file type {}. Please make "
                "sure the filenames end in one of the supported extensions "
                "(fa, fna, fasta, fq, fnq, fastq)".format(filetype), 79), 
                file=sys.stderr)
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
            new_dir = new_dir.strip()
            new_id = new_id.strip()
            old_dir = old_dir.strip()
            old_name = old_name.strip()

            if old_name.strip()[-1] == '*':
                strand_name = {'R1': 'forward', 'R2': 'reverse'}

                forwards = glob.glob('{}/{}*R1_*'.format(old_dir, old_name[:-1]))
                reverses = glob.glob('{}/{}*R2_*'.format(old_dir, old_name[:-1]))
                if len(forwards) != len(reverses):
                    print(textwrap.fill("Warning: missing pair in {}. The use "
                        "of '*' should only be used for paired-end reads in "
                        "separate files".format(old_name), 79), file=sys.stderr)
                    continue
                if len(forwards) > 1:
                    add_det = True
                else:
                    add_det = False

                for strand in (forwards, reverses):
                    for filename in strand:
                        if add_det:
                            seq_detail = re.search(r'L\d{3}_R[12]_\d{3}', 
                                filename).group()
                            lane, pair, number = seq_detail.split('_')
                            new_name = format_io(filename, "{}.{}.{}_{}"
                                .format(new_id, strand_name[pair], lane, 
                                number), args.ext)
                        else:
                            new_name = format_io(filename, "{}.{}"
                                .format(new_id, strand_name[pair]), args.ext)

                        ln_out, ln_err = (Popen(['ln', "-s", filename, "{}/{}"
                            .format(new_dir, new_name)], stdout=PIPE, 
                            stderr=PIPE).communicate())
                        if ln_err:
                            print(ln_err.decode(locale.getdefaultlocale()[1]), 
                                file=sys.stderr)

            else:
                new_name = format_io(old_name, new_id, args.ext)
                new_path = new_dir + "/" + new_name
                old_path = old_dir + "/" + old_name

                ln_out, ln_err = (Popen(['ln', "-s", old_path, new_path], 
                    stdout=PIPE, stderr=PIPE).communicate())
                if ln_err:
                    print(ln_err.decode(locale.getdefaultlocale()[1]), 
                        file=sys.stderr)

if __name__ == '__main__':
    main()
    sys.exit(0)
