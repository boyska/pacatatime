#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This install just few packages at a time

import os
import popen2
from optparse import OptionParser
import urlparse
import re

BASE_DIR = "/tmp/pacatatime/cache"
PKG_URL = re.compile('.*/(.*)-[\d.]+-\d+-\w+\.pkg\..*')

def get_uris(args):
    if not args:
        cmd = "pacman -Sup"
    else:
        cmd = "pacman -Sp %s" % (' '.join(args))
    output = popen2.popen2(cmd)[0]
    uris = []
    #line=output.readline()#we need to skip first 2 lines
    for line in output.readlines():
        uris.append(line.strip())
    return uris
        
def count_dependencies(package):
    cmd = "pacman -Sp %s" % package
    output = popen2.popen2(cmd)[0]
    out = output.readlines()
    return len(out)
    
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

def package_name(url):
    #TODO: fix bug, for example shared-mime-info (regexp -(\d\.)* ?) 
    #TODO: use pacman -Qip for this
    #Input: package-v.e.rs.i-on
    #Output: package
    path = urlparse.urlsplit(url).path
    mat = PKG_URL.search(path)
    if mat:
        return mat.group(1)
    else:
        return None

def parse_input(uri_list):
    '''
    Input: string containing all packages name+ver, as returned by pacman -Qu
    Output: a list of packages names
    '''
    
    pkgs = {} #Name->Url
    for uri in uri_list:
        name = package_name(uri)
        if name:
            pkgs[name] = uri
    return pkgs

def install(packages, skip_deps):
    '''
    Input: list of packages to install
    Installs in batch mode only if they're not up to date
    '''
    #TODO: migrate to subprocess
    if not skip_deps:
        os.system('pacman -S --noconfirm --needed\
            --cachedir /tmp/pacatatime/cache %s' % (' '.join(packages)))
    else:
        os.system('pacman -Sd --noconfirm --needed\
        --cachedir /tmp/pacatatime/cache %s' % (' '.join(packages)))

def clean_cache():
    print "CANCELLO LA CACHE"
    os.system('rm -rf %s/*' % BASE_DIR)

def parse_options(**default_options):
    usage = "usage: %prog [options] [packages]..."
    parser = OptionParser(usage)
    parser.add_option("-t", "--at-a-time", dest="atatime",
    help="how many packages will be installed at a time")
    parser.add_option("-p", "--pretend", action="store_true", dest="pretend", 
    default=False, help="only print the packages we're going to install")
    parser.add_option("-d", "--skip-dependencies", action="store_true",
    dest="skip_deps", default=False, help="skip dependency check")
    parser.set_defaults(**default_options)
    (options, args) = parser.parse_args()
    return options, args

def main():
    options, args = parse_options(atatime=1) #default options in args
    AT_A_TIME = int(options.atatime)
    if args:
        uris = get_uris(args)
    else:
        uris = get_uris([])
    packages = parse_input(uris)
    
    os.system('mkdir -p %s' % BASE_DIR)
    clean = 0
    if options.pretend:
        print "We're installing:"
        print ' '.join(packages.keys())
        print "Splitted as follows:"
    while packages:
        pkg_list = packages.keys()
        pkg_list.sort(key=count_dependencies)
        step_pkgs = pkg_list[0:AT_A_TIME]
        if options.pretend:
            print ' '.join(step_pkgs)
        else:
            install(step_pkgs, options.skip_deps)
            clean_cache()
        for pkg in step_pkgs:
            del packages[pkg]


if __name__ == '__main__':
    main()

