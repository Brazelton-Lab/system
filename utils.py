#! /usr/bin/env python

"""
Parses a JSON-formatted file containing information on the available 
programs on the server and displays it as human-readable text. The user can 
specify a program of interest as a command line argument and receive more 
detail about the program in return, including previous version information, 
dependencies, and a list of possible commands supplied by the program. Also
includes functionality for editing the database.
"""

from __future__ import print_function

__author__ = "Christopher Thornton, Alex Hyer"
__date__ = "2015-11-03"

import sys
import json
import textwrap
import argparse
import re

def argument_parser():
    parser = argparse.ArgumentParser(description="Displays information about "
        "the available bioinformatics programs on the server. If no arguments "
        "given with the list subcommand, will list all. Various flags can be "
        "used to modify the information output with the display subcommand")
    parent_parser = argparse.ArgumentParser(add_help=False)
    parent_parser.add_argument('program',
        metavar='PROGRAM', 
        help="program name")
    db_parser = argparse.ArgumentParser(add_help=False)
    db_parser.add_argument('-b', '--database', metavar="DB",
        default="/usr/local/etc/utils.json",
        type=io_check,
        help="provide a custom JSON-formatted database file")
    subparsers = parser.add_subparsers(title="subcommands", 
        help="exactly one of these commands is required")
    # list-specific arguments
    list_parser = subparsers.add_parser('list',
        parents=[db_parser],
        help="list all available programs")
    category_mode = list_parser.add_argument_group('category viewers')
    exclusive_list = category_mode.add_mutually_exclusive_group()
    exclusive_list.add_argument('-l', '--list_categories',
        action='store_true',
        help='list all program categories')
    exclusive_list.add_argument('-c', '--category',
        type=parse_multiple_args,
        help='list all prgrams in given category')
    list_parser.set_defaults(func=prog_list)
    # edit-specific arguments
    edit_parser = subparsers.add_parser('edit',
        parents=[parent_parser, db_parser],
        help="edit, append, or remove an entry to the database")
    edit_parser.add_argument('-v','--version',
        metavar='VERSION',
        help="current version of the program (can be \"null\" if no version "
            "info available)")
    edit_parser.add_argument('-s', '--synopsis', 
        dest="description",
        metavar='DESCRITPTION', 
        help="program description")
    edit_parser.add_argument('-p', '--prev',
        metavar='VERSION [,VERSION,...]',
        dest="previous versions",
        type=parse_multiple_args,
        help="comma-separated list of previous versions with last date used "
            "(ex: <version>(to <date>)")
    edit_parser.add_argument('-c', '--commands',
        metavar='COMMAND [,COMMAND,...]',
        type=parse_multiple_args,
        help="comma-separated list of commands provided by the program")
    edit_parser.add_argument('-t, --categories',
        dest='categories',
        metavar='CATEGORY [,CATEGORY,...]',
        type=parse_multiple_args,
        help="comma-separated list of categories program is in")
    edit_parser.add_argument('-i', '--installation', metavar='METHOD',
        dest="installation method",
        help="method used to install the program")
    edit_parser.add_argument('-d', '--depends',
        metavar='DEP [,DEP,...]',
        dest="dependencies",
        type=parse_multiple_args,
        help="comma-separated list of program dependencies")
    group_mode = edit_parser.add_argument_group('actions')
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
    display_parser = subparsers.add_parser('show',
        parents=[parent_parser, db_parser],
        help="obtain detailed information about a program")
    flag_group = display_parser.add_argument_group('flags')
    flag_group.add_argument('-p', '--prev',
        action='store_const',
        const='previous versions',
        help="list former versions of the program used on the server")
    flag_group.add_argument('-c', '--commands',
        action='store_const',
        const='commands',
        help="list available commands provided by program")
    flag_group.add_argument('-t', '--categories',
        action='store_const',
        const='categories',
        help="list of categories the program fits in")
    flag_group.add_argument('-i', '--installation',
        action='store_const',
        const='installation method',
        help="display method used to install program")
    flag_group.add_argument('-d', '--depends',
        action='store_const',
        const='dependencies',
        help="list program dependencies")
    display_parser.set_defaults(func=prog_display)
    return parser

def parse_multiple_args(arguments):
    arguments = arguments.split(',')
    return arguments

def io_check(infile, mode='rU'):
    try:
        fh = open(infile, mode)
    except IOError as e:
        print(e)
        sys.exit(1)
    else:
        fh.close()
    return infile

def autocomplete(user_prog, data):
    match = False
    matches = []
    for program in data:
        user_prog_lower = user_prog.lower()
        data_prog_lower = program.lower()
        if user_prog_lower == data_prog_lower:
            match = program
            break
        elif data_prog_lower.startswith(user_prog_lower):
            matches.append(program)
    if not match and len(matches) == 1:
        print_out('Assuming "{0}" meant "{1}"'.format(user_prog, matches[0]))
        print()
        match = matches[0]
    elif not match and len(matches) > 1:
        print('Could not unambiguously determine what "{0}" means.'
              .format(user_prog))
        print('Did you mean one of the following:\n{0}'
              .format('\n'.join(matches)))
        sys.exit(0)
    elif not match and len(matches) == 0:
        print('"{0}" did not match anything in the database.'
              .format(user_prog))
        sys.exit(0)
    return match

def display_info(first, second):
        col_two_begin = 20
        indent=' ' * col_two_begin
        if len(first) > col_two_begin:
            print_out(first)
            print_out(second, initial=indent, subsequent=indent)  
        else:
            print_out("{:<20}{}".format(first, second), subsequent=indent)

def relevant_values(all_args, name, data):
    given_args = []
    approved_values = [
        'previous versions',
        'description',
        'version',
        'commands',
        'installation method',
        'dependencies',
        'categories'
        ]
    for arg in all_args:
        if arg in approved_values and all_args[arg]:
            given_args.append(arg)
    return given_args

def prog_list(args, data):
    if args.list_categories:
        categories = []
        for program in sorted(data):
            try:
                prog_cat = data[program]["categories"]
                for cat in prog_cat:
                    if not cat in categories:
                        categories.append(cat)
            except KeyError:
                pass
        print('\n'.join(categories))
    elif args.category:
        for category in args.category:
            print()
            print( '-' * len(category))
            print('{0}'.format(category))
            print('-' * len(category), '\n')
            exists = False
            for program in sorted(data):
                try:
                    prog_cat = data[program]["categories"]
                    if category in prog_cat:
                        print(program)
                        exists = True
                except KeyError:
                    pass
            if not exists:
                print('No such category: {0}'.format(category))
                print('Type use --list_categories to view possible categories')
    else:            
        for program in sorted(data):
            version = data[program]["version"]
            if version:
                col_one = "{}(v.{}): ".format(program, version)
            else:
                col_one = program
            col_two = data[program]["description"]
            display_info(col_one, col_two)

def prog_display(args, data):
    all_args = vars(args)
    program = autocomplete(args.program, data)
    if program:
        version = data[program]["version"]
        if version:
            col_one = "{}(v.{}): ".format(program, version)
        else:
            col_one = program
        col_two = data[program]["description"]
        display_info(col_one, col_two)
        flags = []
        for arg in all_args:
            if all_args[arg] in data[program]:
                flags.append(all_args[arg])
        for flag in sorted(flags):
            header = flag + ': '
            if type(data[program][flag]) == type(list()):
                value = ', '.join(sorted(data[program][flag]))
            else:
                value = data[program][flag]
            if value:
                output = value
            else:
                output = 'NA'
            display_info(header, output)
    else:
        output = ("Can not locate \"{}\". Please verify that the program that "
                  "you are searching for is already installed on the server, "
                  "and/or not misspelled, by usings \"utils list\""
                  .format(args.program))
        print_out(output)
        sys.exit(1)

def prog_edit(args, data):
    all_args = vars(args)
    if not args.append:
        match = autocomplete(args.program, data)
    else:
        match = False
    if args.remove:
        if match:
            answer = raw_input("Delete \"{}\" [y, n]? ".format(match))
            if answer.lower() == 'y':
                del data[match]
            elif answer.lower() == 'n':
                sys.exit(0)
            else:
                print("\"{}\" is not a valid option".format(answer))
                sys.exit(1)
        else:
            print_out("\"{}\" does not exists in the database of available "
                      "programs. Nothing done.".format(args.program))
            sys.exit(1)
    elif args.edit:
        if match:
            categories = relevant_values(all_args, match, data)
            for category in categories:
                if type(all_args[category]) == type(list()) and \
                    all_args[category][0] == '+':
                    all_args[category].remove('+')
                    data[match][category].extend(all_args[category])
                elif type(all_args[category]) == type(list()) and \
                    all_args[category][0] == '-':
                    data[match][category] = []
                elif type(all_args[category]) == type(str()) and \
                    all_args[category] == '-':
                    data[match][category] = ""  
                else:
                    data[match][category] = all_args[category]
        else:
            print_out("\"{}\" does not exists in database. Nothing to edit."
                      .format(args.program))
    elif args.append:
        if not match:
            data[args.program] = {"description": "", "version": "", 
                                  "previous versions": [], "commands": [], 
                                  "installation method": "", "dependencies": [],
                                  "categories": []
                                 }
            categories = relevant_values(all_args, args.program, data)
            for category in categories:
                data[args.program][category] += all_args[category]
        else:
            print_out("\"{}\" already exists in database. Use \"utils edit -e "
                      "<program>\" to modify an entry".format(args.program))
            sys.exit(1)

    utils = io_check(args.database, 'w')
    with open(utils, 'w') as out_h:
        out_h.write(json.dumps(data, sort_keys=True))

def print_out(line, width=79, initial='', subsequent=''):
    output = textwrap.fill(line, width, initial_indent=initial, 
                          subsequent_indent=subsequent)
    print(output)

def main():
    args = argument_parser().parse_args()
    utils = args.database
    with open(utils, 'rU') as in_h:
        json_data = json.load(in_h)
    args.func(args, json_data)

if __name__ == "__main__":
    main()
