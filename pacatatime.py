#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This install just few packages at a time

import os
import popen2
from optparse import OptionParser

CLEAN_MAX = 5 #how many packages we can install before cleaning cache

def get_list():
    #Output: interesting part of pacman -Qu
    output = popen2.popen2("pacman -Qu")[0]

    try:
        while True:
            try:
                line = output.readline()
            except EOFError:
                return '' #nothing to read
            if line.strip() == '':
                break #first part completed
        
        first_line = output.readline()
        if first_line.find(':') == -1: #no updates found
            return ''
        packages = first_line.split(': ', 2)[1]
        while True:
            try:
                line = output.readline()
            except EOFError:
                return '' #nothing to read
            if line.strip() == '':
                return packages #first part completed
            packages = '%s %s' % (packages, line)
        raise NotImplementedError
    finally:
        output.close()

def package_name(name_version):
    #TODO: fix bug, for example shared-mime-info (regexp -(\d\.)* ?) 
    #Input: package-v.e.rs.i-on
    #Output: package
    return name_version.rsplit('-', 2)[0]

def parse_input(input_text):
    '''
    Input: string containing all packages name+ver, as returned by pacman -Qu
    Output: a list of packages names
    '''
    pkgs = []
    pkgs.extend([package_name(x) 
                for x in input_text.split(' ') if x.strip() != ''])
    return pkgs

def install(packages):
    '''
    Input: list of packages to install
    Installs in batch mode only if they're not up to date
    '''
    #TODO: migrate to subprocess
    os.system('pacman -S --noconfirm --needed\
                --cachedir /tmp/pacatatime/cache %s' % (' '.join(packages)))

def clean_cache():
    #TODO: fix. atm it doesn't work as expected
    print "CANCELLO LA CACHE"
    os.system('yes|pacman -Scc')

def parse_options(**default_options):
    usage = "usage: %prog [options] [packages]..."
    parser = OptionParser(usage)
    parser.add_option("-t", "--at-a-time", dest="atatime",
    help="how many packages will be installed at a time")
    parser.add_option("-p", "--pretend", action="store_true", dest="pretend", 
    default=False, help="only print the packages we're going to install")
    parser.set_defaults(**default_options)
    (options, args) = parser.parse_args()
    return options, args
    

def main():
    options, args = parse_options(atatime=3) #default options in args
    AT_A_TIME = int(options.atatime)
    if args: #packages are user-supplied
        packages = args
    else:
        packages = parse_input(get_list())
    os.system('mkdir -p /tmp/pacatatime/cache')
    clean = 0
    if options.pretend:
        print "We're installing:"
        print ' '.join(packages)
        print "Splitted as follows:"
    for i in range(0, len(packages), AT_A_TIME):
        step_pkgs = packages[i:i+AT_A_TIME]
        if options.pretend:
            print ' '.join(step_pkgs)
            continue
        install(step_pkgs)
        clean = clean + AT_A_TIME
        if clean == CLEAN_MAX:
            clean_cache()
            clean = 0
            

if __name__ == '__main__':
    main()

