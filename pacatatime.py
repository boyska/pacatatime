#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This install just few packages at a time

import os
import sys
import popen2
from optparse import OptionParser
import urlparse
import re
from subprocess import Popen, PIPE

from collections import defaultdict

DB_PATH = '/var/lib/pacman'
BASE_DIR = "/tmp/pacatatime/cache"
PKG_URL = re.compile(
        '.*/(.*?)/os/.*/(.*)-([\d\.]+-\d+)[-\w]*\.pkg\..*', re.UNICODE)

class DiGraph(object):
    def __init__(self):
        self.nodes = set()
        self.edges = defaultdict(set) #'name': {set, of, adiacents}
        self.vertex_properties = defaultdict(set) #'name': {set, of, properties}
        #(from, to): {set, of, properties}
        self.edge_properties = defaultdict(set)

    def add_vertex(self, name):
        self.nodes.add(name)

    def add_edge(self, node_from, node_to):
        self.nodes.add(node_from)
        self.nodes.add(node_to)
        self.edges[node_from].add(node_to)

    def get_adiacents(self, node):
        return self.edges[node]

    def pop_vertex(self, name):
        self.nodes.remove(name)
        del self.edges[name]

    def remove_edge(self, node_from, node_to):
        adiacents = self.get_adiacents(node_from)
        adiacents.remove(node_to)

    def get_properties(self, property, node, node_to=None):
        if not node_to: #it's a vertex
            return self.vertex_properties[node]
        else:
            return self.edge_properties[(node_from, node_to)]

    def add_property(self, property, node, node_to=None):
        if not node_to: #it's a vertex
            self.vertex_properties[node].add(property)
        else:
            self.edge_properties[(node_from, node_to)].add(property)
            
    def remove_property(self, property, node, node_to=None):
        if not node_to: #it's a vertex
            self.vertex_properties[node].remove(property)
        else:
            self.edge_properties[(node_from, node_to)].remove(property)

    def has_property(self, property, node, node_to=None):
        if not node_to: #it's a vertex
            if property in self.vertex_properties[node]:
                return True
            else:
                return False
        else:
            if property in self.edge_properties[(node, node_to)]:
                return True
            else:
                return False

    def get_one_leaf(self):
        for name in self.nodes:
            if not self.edges[name]:
                return name

        return None





class PacGraph(object):
    def __init__(self, packages):
        '''
        packages is a list.
        they'll be the only node in the graph with incoming degree = 0
        '''
        self.base_packages = packages
        
        self.graph = DiGraph() #an edge from a to b means "a depends on b"
        
        self._build()
    
    def get_dependencies(self, node):
        '''return adiacent nodes on the graph'''
        raise NotImplementedError
        
    def pop_leaf(self):
        '''
        find a "leaf" and return a tuple (leaf,)
        If there isn't any leaf, return (the, smallest, cycle)
        '''
        graph = self.graph
        for u in graph.nodes:
            if graph.has_property('visited', u):
                continue
            for v in graph.get_adiacents(u):
                if not graph.has_property('visited', v):
                    break
            else: #every adiacent has been visited, it's a leaf!
                graph.add_property('visited', u)
                return  u

        return None


    def _build(self):
        '''build the graph, returns nothing'''
        to_install = self._needed_packages(self.base_packages)#[('name','ver', 'repo'), ...]
        for pkg in to_install:
            for x in self._needed_packages((pkg,)):
                if x != pkg:
                    self.graph.add_edge(pkg, x)
    
    def _needed_packages(self, packages=None):
        '''return a list of names of the needed packages to install self.base_packages'''
        needed = []
        if packages:
            pm = Popen('pacman -Sp %s' % (' '.join(packages)), stdout=PIPE, shell=True)
        else:
            pm = Popen('pacman -Sup %s', stdout=PIPE, shell=True)
        for url in pm.stdout:
            try:
                url = url.strip().decode()
            except UnicodeDecodeError:
                #it is probably an informative string, not a URL. discard it
                continue
            mat = PKG_URL.search(url)
            if mat:
                name = mat.group(2)
                needed.append(name)
        return needed
                    
        
class PacAtATime(object):
    def __init__(self, packages):
        '''
        packages is the list of the packages to be installed.
        Empty if it's a system upgrade
        '''
        self.installing = packages
        self.graph = PacGraph(self.installing)
    
    def get_sequence(self):
        l = []
        while True:
            leaf = self.graph.pop_leaf()
            if not leaf:
                break
            l.append(leaf)
        return l

    def install(self):
        '''install what is asked'''
        to_install = self.get_sequence()
        print to_install
        for pkg in to_install:
            if pkg in self.installing: #explicit
                os.system('pacman -S --noconfirm --needed --asexplicit\
                --cachedir /tmp/pacatatime/cache %s' % pkg)
            else: #dep
                os.system('pacman -S --noconfirm --needed --asdeps\
                --cachedir /tmp/pacatatime/cache %s' % pkg)

    
    def n_packages(self):
        '''return the number of packages to be installed '''
        raise NotImplementedError
    
    def max_packages(self):
        '''return the maximum number of packages to be installed in a single step '''
        raise NotImplementedError
    
    def size(self):
        '''return the total size of the packages to be installed'''
        raise NotImplementedError
        
    def max_size(self):
        '''return the maximum size to be installed in a single step'''
        raise NotImplementedError

    def _install_package(self, package_name):
        raise NotImplementedError
    
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
    if os.getuid() != 0:
        print "pacatatime must be run as root"
        sys.exit(1)
    
    options, args = parse_options(atatime=1) #default options in args
    AT_A_TIME = int(options.atatime)
    installer = PacAtATime(args)
    if not options.pretend:
        installer.install()
    else:
        print installer.get_sequence()

    return 0

if __name__ == '__main__':
    main()

