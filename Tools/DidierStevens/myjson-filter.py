#!/usr/bin/env python

from __future__ import print_function

__description__ = 'myjson-filter'
__author__ = 'Didier Stevens'
__version__ = '0.0.5'
__date__ = '2023/09/17'

"""
Source code put in the public domain by Didier Stevens, no Copyright
https://DidierStevens.com
Use at your own risk

History:
  2022/03/28: start
  2022/04/04: continue
  2022/04/09: added option -l
  2022/04/09: 0.0.3 refactoring; added option -t
  2023/03/29: 0.0.4 added option -W
  2023/09/17: 0.0.5 added YARA support

Todo:
"""

import optparse
import sys
import binascii
import json
import re
import textwrap
import hashlib
import string
import os.path

try:
    import yara
except ImportError:
    pass

WRITE_VIR = 'vir'
WRITE_HASH = 'hash'
WRITE_HASHVIR = 'hashvir'
WRITE_IDVIR = 'idvir'

dValidWriteValues = {
  WRITE_VIR: 'filename is item name + extension vir',
  WRITE_HASH: 'filename is sha256 hash',
  WRITE_HASHVIR: 'filename is sha256 hash + extension vir',
  WRITE_IDVIR: 'filename is item id + extension vir'
}

def PrintManual():
    manual = r'''
Manual:

This tool takes JSON output from tools like oledump, zipdump, ... via stdin, filters the items, and outputs JSON to stdout.

Option -n (--namefilter) can be used to filter items based on their names. The value for option -n is a regular expression to select matching names.

Option -c (--contentfilter) can be used to filter items based on their content. The value for option -c is a regular expression to select matching content.

Option -t (--typefilter) can be used to filter items based on their type determined with file-magic.py. The value for option -t is a regular expression to select matching types.

Flags can be added to regular expressions as follows: #flags#regex.
Flags can be i (ignore case) and v (reverse selection).

Option -y (--yarafilter) can be used to filter items with YARA rules matching the item's content.

Use option -l to list the selected items, in stead of outputing JSON data.

Use option -W to write the selected items to files, in stead of outputing JSON data.
Valid options for -W are:
'''

    for item in dValidWriteValues.items():
        manual += ' %s: %s\n' % item

    for line in manual.split('\n'):
        print(textwrap.fill(line, 79))

def CheckJSON(stringJSON):
    try:
        object = json.loads(stringJSON)
    except:
        print('Error parsing JSON')
        print(sys.exc_info()[1])
        return None
    if not isinstance(object, dict):
        print('Error JSON is not a dictionary')
        return None
    if not 'version' in object:
        print('Error JSON dictionary has no version')
        return None
    if object['version'] != 2:
        print('Error JSON dictionary has wrong version')
        return None
    if not 'id' in object:
        print('Error JSON dictionary has no id')
        return None
    if object['id'] != 'didierstevens.com':
        print('Error JSON dictionary has wrong id')
        return None
    if not 'type' in object:
        print('Error JSON dictionary has no type')
        return None
    if object['type'] != 'content':
        print('Error JSON dictionary has wrong type')
        return None
    if not 'fields' in object:
        print('Error JSON dictionary has no fields')
        return None
    if not 'name' in object['fields']:
        print('Error JSON dictionary has no name field')
        return None
    if not 'content' in object['fields']:
        print('Error JSON dictionary has no content field')
        return None
    if not 'items' in object:
        print('Error JSON dictionary has no items')
        return None
    for item in object['items']:
        item['content'] = binascii.a2b_base64(item['content'])
    return object['items']

def StartsWithGetRemainder(strIn, strStart):
    if strIn.startswith(strStart):
        return True, strIn[len(strStart):]
    else:
        return False, None

def ParseHashOption(value):
    result, remainder = StartsWithGetRemainder(value, '#')
    if not result:
        return '', value
    position = remainder.find('#')
    if position == -1:
        return '', value
    return remainder[:position], remainder[position + 1:]

def ProduceJSON(items):
    for item in items:
        item['content'] = binascii.b2a_base64(item['content']).decode().strip('\n')

    return json.dumps({'version': 2, 'id': 'didierstevens.com', 'type': 'content', 'fields': ['id', 'name', 'content'], 'items': items})

def ParseHashFilter(value):
    flagsRE = 0
    flagReverse = False
    flags, filterExpression = ParseHashOption(value)
    for flag in flags:
        if flag == 'i':
            flagsRE = re.I
        elif flag == 'v':
            flagReverse = True
        else:
            raise Exception('Unknown flag: %s for option %s' % (flag, value))
    return filterExpression, flagsRE, flagReverse

def PrefixIfNeeded(string, prefix=' '):
    if string == '':
        return string
    else:
        return prefix + string

def CleanName(name):
    return ''.join([char if char.lower() in string.digits + string.ascii_letters + '.-_' else '_' for char in name])

def WriteFiles(items, options):
    for item in items:
        if options.write == WRITE_VIR:
            memberFilename = CleanName(item['name']) + '.vir'
        elif options.write == WRITE_IDVIR:
            memberFilename = str(item['id']) + '.vir'
        else:
            memberFilename = hashlib.sha256(item['content']).hexdigest()
            if options.write == WRITE_HASHVIR:
                memberFilename += '.vir'
        print('Writing: %s' % memberFilename)
        with open(memberFilename, 'wb') as fWrite:
            fWrite.write(item['content'])

def File2Strings(filename):
    try:
        f = open(filename, 'r')
    except:
        return None
    try:
        return map(lambda line:line.rstrip('\n'), f.readlines())
    except:
        return None
    finally:
        f.close()

def ProcessAt(argument):
    if argument.startswith('@'):
        strings = File2Strings(argument[1:])
        if strings == None:
            raise Exception('Error reading %s' % argument)
        else:
            return strings
    else:
        return [argument]

def YARACompile(ruledata):
    if ruledata.startswith('#'):
        if ruledata.startswith('#h#'):
            rule = binascii.a2b_hex(ruledata[3:])
        elif ruledata.startswith('#b#'):
            rule = binascii.a2b_base64(ruledata[3:])
        elif ruledata.startswith('#s#'):
            rule = 'rule string {strings: $a = "%s" ascii wide nocase condition: $a}' % ruledata[3:]
        elif ruledata.startswith('#q#'):
            rule = ruledata[3:].replace("'", '"')
        elif ruledata.startswith('#x#'):
            rule = 'rule hexadecimal {strings: $a = { %s } condition: $a}' % ruledata[3:]
        elif ruledata.startswith('#r#'):
            rule = 'rule regex {strings: $a = /%s/ ascii wide nocase condition: $a}' % ruledata[3:]
        else:
            rule = ruledata[1:]
        return yara.compile(source=rule), rule
    else:
        dFilepaths = {}
        if os.path.isdir(ruledata):
            for root, dirs, files in os.walk(ruledata):
                for file in files:
                    filename = os.path.join(root, file)
                    dFilepaths[filename] = filename
        else:
            for filename in ProcessAt(ruledata):
                dFilepaths[filename] = filename
        return yara.compile(filepaths=dFilepaths), ','.join(dFilepaths.values())

def MyJSONFilter(options):
    items = CheckJSON(sys.stdin.read())

    if items == None:
        return

    if options.namefilter != '':
        filterExpression, flagsRE, flagReverse = ParseHashFilter(options.namefilter)
        oRE = re.compile(filterExpression, flagsRE)
        selectedItems = []
        for item in items:
            itemName = item['name']
            if not isinstance(itemName, str):
                itemName = str(itemName)
            if oRE.search(itemName):
                if not flagReverse:
                    selectedItems.append(item)
            elif flagReverse:
                selectedItems.append(item)
        items = selectedItems

    if options.contentfilter != '':
        filterExpression, flagsRE, flagReverse = ParseHashFilter(options.contentfilter)
        oRE = re.compile(filterExpression.encode(), flagsRE)
        selectedItems = []
        for item in items:
            if oRE.search(item['content']):
                if not flagReverse:
                    selectedItems.append(item)
            elif flagReverse:
                selectedItems.append(item)
        items = selectedItems

    if options.typefilter != '':
        filterExpression, flagsRE, flagReverse = ParseHashFilter(options.typefilter)
        oRE = re.compile(filterExpression, flagsRE)
        selectedItems = []
        for item in items:
            if oRE.search(item['magic']):
                if not flagReverse:
                    selectedItems.append(item)
            elif flagReverse:
                selectedItems.append(item)
        items = selectedItems

    if options.yarafilter != '':
        if not 'yara' in sys.modules:
            print('Error: option yara requires the YARA Python module.')
            print("You can use PIP to install yara-python like this: pip install yara-python\npip is located in Python's Scripts folder.\n")
            return
        rules, rulesVerbose = YARACompile(options.yarafilter)
        selectedItems = []
        for item in items:
            if len(rules.match(data=item['content'])):
                selectedItems.append(item)
        items = selectedItems

    if options.list:
        for item in items:
            print('%3d: %s%s' % (item['id'], item['name'], PrefixIfNeeded(item.get('magic', ''))))
            if options.content:
                print(item['content'])
    elif options.write != '':
        WriteFiles(items, options)
    else:
        print(ProduceJSON(items))

def Main():
    moredesc = '''

Source code put in the public domain by Didier Stevens, no Copyright
Use at your own risk
https://DidierStevens.com'''

    oParser = optparse.OptionParser(usage='usage: %prog [options]\n' + __description__ + moredesc, version='%prog ' + __version__, epilog='This tool also accepts flag arguments (#f#), read the man page (-m) for more info.')
    oParser.add_option('-m', '--man', action='store_true', default=False, help='Print manual')
    oParser.add_option('-n', '--namefilter', type=str, default='', help='Regular expression to filter for the item name')
    oParser.add_option('-c', '--contentfilter', type=str, default='', help='Regular expression to filter for the content')
    oParser.add_option('-t', '--typefilter', type=str, default='', help='Regular expression to filter for the type')
    oParser.add_option('-y', '--yarafilter', type=str, default='', help="YARA rule-file, @file, directory or #rule to check")
    oParser.add_option('-l', '--list', action='store_true', default=False, help='List selected items')
    oParser.add_option('-C', '--content', action='store_true', default=False, help='List also content when option -l is used')
    oParser.add_option('-W', '--write', type=str, default='', help='Write all files to disk')
    (options, args) = oParser.parse_args()

    if options.man:
        oParser.print_help()
        PrintManual()
        return

    if len(args) != 0:
        print('Error: this tool expects input from stdin')
        return

    if options.write != '':
        if not options.write in dValidWriteValues:
            print('Invalid write option: %s' % options.write)
            print('Valid write options are:')
            for item in dValidWriteValues.items():
                print('  %s: %s' % item)
            return

    MyJSONFilter(options)

if __name__ == '__main__':
    Main()
