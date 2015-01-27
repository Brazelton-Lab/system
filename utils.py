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
import re

def argument_parser():
    parser = argparse.ArgumentParser(description="Displays information about "
                                     "the available bioinformatics programs "
                                     "on the server. If no arguments given "
                                     "with the list subcommand, will list all "
                                     ". Various flags can be used to modify "
                                     "the information output/input")
    # arguments available to certain subcommands
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('program', metavar='PROGRAM', help="program name")
    flag_group = parent_parser.add_argument_group('flags')
    flag_group.add_argument('-p', '--prev',
                        action='store_const',
                        const='previous versions',
                        help="list of former versions of the program used on the "
                        "server")
    flag_group.add_argument('-c', '--commands',
                        action='store_const',
                        const='commands',
                        help="list of available commands provided by program")
    flag_group.add_argument('-i', '--installation',
                        action='store_const',
                        const='installation method',
                        help="method used to install program")
    flag_group.add_argument('-d', '--depends',
                        action='store_const',
                        const='dependencies',
                        help="list of program dependencies")
    subparsers = parser.add_subparsers(title="subcommands", description="available subcommands", help="extra help")
    # list-specific arguments
    list_parser = subparsers.add_parser('list', 
                                        help="list all available programs")
    list_parser.set_defaults(func=prog_list)
    # edit-specific arguments
    edit_parser = subparsers.add_parser('edit', parents=[parent_parser], 
                                        help="edit or append an entry into the "
                                        "database of bioinformatics programs")
    edit_parser.add_argument('version', metavar='VERSION', help="current version of the program (can be \"null\" if no version info available)")
    edit_parser.add_argument('synopsis', metavar='DESCRITPTION', help="program description")
    group_mode = edit_parser.add_argument_group('action')
    exclusive_group = group_mode.add_mutually_exclusive_group(required=True)
    exclusive_group.add_argument('-a', '--append', 
                       action='store_true', 
                       help="add new entry to database")
    exclusive_group.add_argument('-e', '--edit', 
                       action='store_true', 
                       help="edit existing entry in database")
    exclusive_group.add_argument('-r', '--remove',
                       action='store_true',
                       help="remove existing entry from database")
    edit_parser.set_defaults(func=prog_edit)
    # display-specific arguments
    display_parser = subparsers.add_parser('display', parents=[parent_parser], 
                                          help="obtain detailed information "
                                          "about a specific program")
    display_parser.set_defaults(func=prog_display)
    return parser

def test_matched(ci_prog, data):
    ignore_case = re.compile(ci_prog, re.IGNORECASE)
    match = None
    for cs_prog in data: # case sensitive
        if ignore_case.match(cs_prog):
            match = ignore_case.match(cs_prog).group()
            break
    return match


def obtain_flags(given_args):
    flags = {}
    for argument in given_args:
        if argument in ["commands", "installation", "prev", "depends"]:
            flags[argument] = given_args[argument]
    return flags

def display_info(first, second):
        col_two_begin = 20
        indent=' ' * col_two_begin
        if len(first) > col_two_begin:
            print_out(first)
            print_out(second, initial=indent, subsequent=indent)  
        else:
            print_out("{:<20}{}".format(first, second), subsequent=indent)

def prog_list(args, data):
    for program in sorted(data):
        version = data[program]["version"]
        if version:
            col_one = "{}(v.{}): ".format(program, version)
        else:
            col_one = program
        col_two = data[program]["description"]
        display_info(col_one, col_two)

def prog_display(args, data):
    flags = obtain_flags(vars(args))
    program = test_matched(args.program, data)
    if program:
        version = data[program]["version"]
        if version:
            col_one = "{}(v.{}): ".format(program, version)
        else:
            col_one = program
        col_two = data[program]["description"]
        display_info(col_one, col_two)
        for modifier in sorted(flags):
            category = flags[modifier]
            if category: #the constant from store_constant
                category_out = category + ': '
                if type(data[program][category]) == type(list()):
                    line = ', '.join(sorted(data[program][category]))
                else:
                    line = data[program][category]
                display_info(category_out, line)
    else:
        output = ("{} is not installed on the server. Please verify that the "
                  "program you are searching for is installed on the server, "
                  "and/or not misspelled, by usings \"utils list\""
                  .format(args.program))
        print_out(output)
        sys.exit(1)

def prog_edit(args, data):
    if args.remove:
        program = test_matched(args.program) # verify that it actually exists
        if program:
            answer = userinput("would you really like to delete {}?".format(program))
            if answer:
                del data[program]
                out_write(json.dumps(data))
            else:
                sys.exit(0)
        else:
            print_out("{} does not exists in database. Nothing done.".format(args.program))
            sys.exit(1)
    elif args.edit:
        pass 
    elif args.append:
        if not test_matched(args.program):
            data[args.program] = {"description": "", "version": "", 
                                  "previous versions": [], "commands": [], 
                                  "installation method": "", "dependencies": []
                                 }
        else:
            print_out("{} already exists in database. Use \"utils edit -e <program>\" to modify an entry".format(args.program))
            sys.exit(1)
    
def print_out(line, width=79, initial='', subsequent=''):
    output = textwrap.fill(line, width, initial_indent=initial, 
                          subsequent_indent=subsequent)
    print(output)

def main():
    utils = "/usr/local/etc/utils.txt"
    with open(utils, 'rU') as infile:
        json_data = json.load(infile)
    args = argument_parser().parse_args()
    args.func(args, json_data)

if __name__ == "__main__":
    main()
