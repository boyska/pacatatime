#This install just few packages at a time
#TODO: stdin packages list
#TODO: getopt (clean_max, at_a_time)

import os
import popen2

CLEAN_MAX = 5 #how many packages we can install before cleaning cache
AT_A_TIME = 3

def get_list():
	#TODO (something with pacman -Qu)
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
		
		packages = output.readline().split(': ', 2)[1]
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
	#Input: string containing all packages name+ver, as returned by pacman -Qu
	#Output: a list of packages names
	pkgs = []
	pkgs.extend([package_name(x) for x in input.split(' ') if x.strip() != ''])
	return pkgs

def install(packages):
	#Input: list of packages to install
	#Installs in batch mode only if they're not up to date
	os.system('pacman -S --noconfirm --needed --cachedir /tmp/pacatatime/cache %s' % (' '.join(packages)))

def clean_cache():
	#TODO: fix. atm it doesn't work as expected
	print "CANCELLO LA CACHE"
	os.system('yes|pacman -Scc')

if __name__ == '__main__':
	clean=0
	packages = parse_input(get_list())
	print packages
	os.system('mkdir -p /tmp/pacatatime/cache')
	for i in range(0, len(packages), AT_A_TIME):
		print i
		step_pkgs = packages[i:i+AT_A_TIME - 1]
		install(step_pkgs)
		clean = clean + 1;
		if clean == CLEAN_MAX:
			clean_cache()
			clean = 0
