#!/usr/bin/env python

__description__ = 'Simple Shellcode Generator'
__author__ = 'Didier Stevens'
__version__ = '0.0.1'
__date__ = '2011/09/12'

"""

Source code put in public domain by Didier Stevens, no Copyright
https://DidierStevens.com
Use at your own risk

History:
  2011/09/12: start

Todo:
"""

import optparse
import time

def HashIt(str):
    hash = 0
    for c in str:
        hash = (hash + (ord(c) | 0x60)) << 1
    return hash

def GenerateHeader():
    assemblerCode = ''
    assemblerCode += '; Shellcode generated by simple-shellcode-generator.py\n'
    assemblerCode += '; Generated for NASM assembler (http://www.nasm.us)\n'
    assemblerCode += '; https://DidierStevens.com\n'
    assemblerCode += '; Use at your own risk\n'
    assemblerCode += ';\n'
    assemblerCode += '; History:\n'
    assemblerCode += ';   %04d/%02d/%02d: generated\n' % time.localtime()[0:3]
    assemblerCode += '\n'
    assemblerCode += 'BITS 32\n'
    assemblerCode += '\n'
    return assemblerCode

def ExtractLibraryName(library):
    return library.split('.')[0]

def GenerateEQUsForLibrary(library, functions):
    assemblerCode = ''
    libraryName = ExtractLibraryName(library).upper()
    assemblerCode += '%s_HASH equ 0x%08X\n' % (libraryName, HashIt(library))
    assemblerCode += '%s_NUMBER_OF_FUNCTIONS equ %d\n' % (libraryName, len(functions))
    for function in functions:
        assemblerCode += '%s_%s_HASH equ 0x%08X\n' % (libraryName, function.upper(), HashIt(function))
    assemblerCode += '\n'
    return assemblerCode

def GenerateEQUs(dFunctions):
    assemblerCode = ''
    for library in dFunctions.keys():
        assemblerCode += GenerateEQUsForLibrary(library, dFunctions[library])
    return assemblerCode

def GenerateEntryCode():
    assemblerCode = ''
    assemblerCode += 'segment .text\n'
    assemblerCode += '	call geteip\n'
    assemblerCode += 'geteip:\n'
    assemblerCode += '	pop ebx\n'
    assemblerCode += '\n'
    return assemblerCode

def GenerateEnvironmentSetup(library):
    assemblerCode = ''
    libraryName = ExtractLibraryName(library).upper()
    assemblerCode += '	; Setup environment for %s\n' % library
    assemblerCode += '	lea esi, [%s_FUNCTIONS_TABLE-geteip+ebx]\n' % libraryName
    assemblerCode += '	push esi\n'
    assemblerCode += '	lea esi, [%s_HASHES_TABLE-geteip+ebx]\n' % libraryName
    assemblerCode += '	push esi\n'
    assemblerCode += '	push %s_NUMBER_OF_FUNCTIONS\n' % libraryName
    assemblerCode += '	push %s_HASH\n' % libraryName
    assemblerCode += '	call LookupFunctions\n'
    assemblerCode += '\n'
    return assemblerCode

def GenerateEnvironmentSetups(dFunctions):
    assemblerCode = ''
    for library in dFunctions.keys():
        assemblerCode += GenerateEnvironmentSetup(library)
    return assemblerCode

def GenerateTrailer():
    assemblerCode = ''
    assemblerCode += '	ret\n'
    assemblerCode += '\n'
    assemblerCode += '%include "sc-api-functions.asm"\n'
    assemblerCode += '\n'
    return assemblerCode

def GenerateEnvironmentTables(dFunctions):
    assemblerCode = ''
    for library in dFunctions.keys():
        assemblerCode += GenerateEnvironmentTable(library, dFunctions[library])
    return assemblerCode

def GenerateEnvironmentTable(library, functions):
    global dFunctionLabels

    assemblerCode = ''
    libraryName = ExtractLibraryName(library).upper()
    assemblerCode += '%s_HASHES_TABLE:\n' % libraryName
    for function in functions:
        assemblerCode += '	dd %s_%s_HASH\n' % (libraryName, function.upper())
    assemblerCode += '\n'
    assemblerCode += '%s_FUNCTIONS_TABLE:\n' % libraryName
    for function in functions:
        functionLabel = '%s_%s' % (libraryName, function.upper())
        assemblerCode += '%s dd 0x00000000\n' % functionLabel
        dFunctionLabels[function] = functionLabel
    assemblerCode += '\n'
    return assemblerCode

def FileToLines(filename):
    try:
        f = open(filename, 'r')
    except:
        print('Error opening file %s' % filename)
        return None
    try:
        lines = f.readlines()
    except:
        print('Error reading file %s' % filename)
        return None
    finally:
        f.close()
    return lines

def ParseShellcodeDefinition(lines):
    dFunctions = {}
    lCalls = []
    for line in lines:
        function = line.rstrip('\n').split(' ')
        if not function[0] in dFunctions:
            dFunctions[function[0]] = []
        dFunctions[function[0]].append(function[1])
        lCalls.append([function[1], function[2:]])
    return dFunctions, lCalls

def GenerateArguments(arguments):
    global counterString
    global counterPint

    assemblerCode = ''
    arguments.reverse()
    for argument in arguments:
        if argument == 'int':
            assemblerCode += '	push 0x00\n'
        elif argument == 'str':
            counterString += 1
            assemblerCode += '	lea eax, [STRING%d-geteip+ebx]\n' % counterString
            assemblerCode += '	push eax\n'
        elif argument == 'pint':
            counterPint += 1
            assemblerCode += '	lea eax, [VAR%d-geteip+ebx]\n' % counterPint
            assemblerCode += '	push eax\n'
        else:
            assemblerCode += '	push %s\n' % argument
    return assemblerCode

def GenerateCall(function, arguments):
    global dFunctionLabels

    assemblerCode = ''
    assemblerCode += '	; call to %s\n' % function
    assemblerCode += GenerateArguments(arguments)
    assemblerCode += '	call [%s-geteip+ebx]\n' % dFunctionLabels[function]
    return assemblerCode

def GenerateCalls(lCalls):
    assemblerCode = ''
    for call in lCalls:
        assemblerCode += GenerateCall(call[0], call[1])
        assemblerCode += '\n'
    return assemblerCode

def GenerateStrings(counterString):
    assemblerCode = ''
    for i in range(1, counterString + 1):
        assemblerCode += 'STRING%d: db "String %d", 0\n' % (i, i)
    if counterString > 0:
        assemblerCode += '\n'
    return assemblerCode

def GeneratePints(counterPint):
    assemblerCode = ''
    for i in range(1, counterPint + 1):
        assemblerCode += 'VAR%d: dd 0x00000000\n' % i
    if counterPint > 0:
        assemblerCode += '\n'
    return assemblerCode

def StringToFile(content, filename):
    try:
        f = open(filename, 'w')
    except:
        print('Error opening file %s' % filename)
        return
    try:
        f.write(content)
    except:
        print('Error writing file %s' % filename)
    finally:
        f.close()

def ShellcodeGenerator(definition, literal, output):
    global dFunctionLabels
    global counterString
    global counterPint

    assemblerCode = ''
    dFunctionLabels = {}
    counterString = 0
    counterPint = 0
    if literal:
        lines = [definition]
    else:
        lines = FileToLines(definition)
    if lines != None:
        dFunctions, lCalls = ParseShellcodeDefinition(lines)
        assemblerCode += GenerateHeader()
        assemblerCode += GenerateEQUs(dFunctions)
        assemblerCode += GenerateEntryCode()
        assemblerCode += GenerateEnvironmentSetups(dFunctions)
        environmentTables = GenerateEnvironmentTables(dFunctions)
        assemblerCode += GenerateCalls(lCalls)
        assemblerCode += GenerateTrailer()
        assemblerCode += environmentTables
        assemblerCode += GenerateStrings(counterString)
        assemblerCode += GeneratePints(counterPint)
        if output == None:
            print(assemblerCode)
        else:
            StringToFile(assemblerCode, output)

def Main():
    oParser = optparse.OptionParser(usage='usage: %prog [options] definition\n' + __description__, version='%prog ' + __version__)
    oParser.add_option('-l', '--literal', action='store_true', default=False, help='provide literal definition in stead of filename')
    oParser.add_option('-o', '--output', help='write generated shellcode to (.asm) file')
    (options, args) = oParser.parse_args()

    if len(args) != 1:
        oParser.print_help()
        print('')
        print('  Source code put in the public domain by Didier Stevens, no Copyright')
        print('  Use at your own risk')
        print('  https://DidierStevens.com')
        return
    else:
        ShellcodeGenerator(args[0], options.literal, options.output)

if __name__ == '__main__':
    Main()