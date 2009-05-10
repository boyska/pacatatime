#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This install just few packages at a time
#TODO: stdin packages list
#TODO: getopt (clean_max, at_a_time)

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
	return name_version.rsplit('-',2)[0]

def parse_input(input):
	'''
	Input: string containing all packages name+ver, as returned by pacman -Qu
	Output: a list of packages names
	'''
	pkgs = []
	pkgs.extend([package_name(x) for x in input.split(' ') if x.strip() != ''])
	return pkgs

def install(packages):
	'''
	Input: list of packages to install
	Installs in batch mode only if they're not up to date
	'''
	os.system('pacman -S --noconfirm --needed --cachedir /tmp/pacatatime/cache %s' % (' '.join(packages)))

def clean_cache():
	#TODO: fix. atm it doesn't work as expected
	print "CANCELLO LA CACHE"
	os.system('yes|pacman -Scc')

def parse_options(**default_options):
	usage = "usage: %prog [options] [packages]..."
	parser = OptionParser(usage)
	parser.add_option("-t", "--at-a-time", dest="atatime",
	help="how many packages will be installed at a time")
	parser.set_defaults(**default_options)
	(options, args) = parser.parse_args()
	return options,args
	

def main():
	options, args = parse_options(atatime=3) #default options in args
	AT_A_TIME = int(options.atatime)
	clean=0
	packages = parse_input(get_list())
	os.system('mkdir -p /tmp/pacatatime/cache')
	for i in range(0, len(packages), AT_A_TIME):
		step_pkgs = packages[i:i+AT_A_TIME - 1]
		install(step_pkgs)
		clean = clean + 1;
		if clean == CLEAN_MAX:
			clean_cache()
			clean = 0
			

if __name__ == '__main__':
	main()
	