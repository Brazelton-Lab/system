#! /usr/bin/env python
"""
Parses a JSON-formatted file containing information on the available 
programs on the server and displays it as human-readable text. The user can 
specify a program of interest as a command line argument and receive more 
detail about the program in return, including previous version information, 
dependencies, and a list of possible commands supplied by the program.
"""

from __future__ import print_function

__author__ = "Christopher Thornton"
__date__ = "2015-01-23"

import sys
import json
import textwrap
import argparse

def argument_parser():
    parser = argparse.ArgumentParser(description="Display information about "
                                     "the available bioinformatics programs "
                                     "on the server. If no arguments given, "
                                     "will list all of the programs (with a "
                                     "short description)")
    parser.add_argument('-n', '--name',
                        type=str,
                        metavar='PROGRAM',
                        nargs='+',
                        help="obtain detailed information about a program or "
                        "list of programs")
    parser.add_argument('-p', '--prev_vers',
                        action='store_const',
                        const='previous versions',
                        help="list all of versions of the specified "
                        "program(s) that were used on the server in the past "
                        "(must be used with the --name option)")
    parser.add_argument('-f', '--full_desc',
                        action='store_const',
                        const='description',
                        help="output a more detailed description of the "
                        "program(s) (must be used with the --name option)")
    parser.add_argument('-c', '--commands',
                        action='store_const',
                        const='commands',
                        help="list all of the available commands provided by "
                        "the specified program(s) (must be used with the "
                        "--name option)")
    parser.add_argument('-i', '--inst_method',
                        action='store_const',
                        const='installation method',
                        help="method used to install program(s) onto the "
                        "the server (must be used with the --name option)")
    parser.add_argument('-d', '--depends',
                        action='store_const',
                        const='dependencies',
                        help="list the dependencies of the program(s) (must "
                        "be used with the --name option)")
    return parser

def display_progs(data):
    for program in sorted(data):
        version = data[program]["version"]
        if version:
            col_one = "{}(v.{}):".format(program, version)
        else:
            col_one = program
        col_two = data[program]["synopsis"]
        col_two_begin = 30
        indent=' ' * col_two_begin
        if len(col_one) > col_two_begin:
            print_out(col_one)
            print_out(col_two, initial=indent, subsequent=indent)  
        else:
            print_out("{:<30}{}".format(col_one, col_two), subsequent=indent)

def prog_detail(prog, data, mods):
    if prog in data:
        version = data[prog]["version"]
        if version:
            print_out("{}(v.{}):".format(prog, version))
        else:
            print_out(prog)
        for modifier in sorted(mods):
            category = mods[modifier]
            if category:
                cat_indent = ' ' * 4
                print_out(category + ':', initial=cat_indent,
                          subsequent=cat_indent)
                detail_indent = ' ' * 8
                if type(data[prog][category]) == type(list()):
                    line = ', '.join(sorted(data[prog][category]))
                else:
                    line = data[prog][category]
                print_out(line, initial=detail_indent,
                          subsequent=detail_indent)
    else:
        output = ("{} is not installed on the server. Please verify that the "
                  "program you are searching for is installed on the server, "
                  "and/or not misspelled, by usings \"utils\" without "
                  "command-line arguments".format(prog))
        print_out(output)
        sys.exit(1)

def print_out(line, width=79, initial='', subsequent=''):
    output = textwrap.fill(line, width, initial_indent=initial, 
                          subsequent_indent=subsequent)
    print(output)

def main():
    args = argument_parser().parse_args()
    programs = args.name
    utils = "/usr/local/etc/utils.txt"
    with open(utils, 'rU') as infile:
        json_data = json.load(infile)
    if programs:
        modifiers = vars(args)
        del modifiers['name']
        for prog in programs:
            prog_detail(prog, json_data, modifiers)
    else: 
        display_progs(json_data)

if __name__ == "__main__":
    main()
