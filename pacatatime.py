'''A wrapper on pacman that will install packages/upgrade your system
one package at a time.
It's especially useful for computers with few disk space'''
#!/usr/bin/env python
# -*- coding: utf-8 -*-
#This install just few packages at a time

import os
import sys
from optparse import OptionParser
import re
from subprocess import Popen, PIPE

from collections import defaultdict

DB_PATH = '/var/lib/pacman'
BASE_DIR = "/tmp/pacatatime/cache"
PKG_URL = re.compile(
    '.*/(.*)/os/.*/(.*?)-(\d+\.[\w.-]+)', re.UNICODE)

class DiGraph(object):
    
    '''A generic directed graph'''
    def __init__(self):
        '''constructor'''
        self.nodes = set()
        self.edges = defaultdict(set) #'name': {set, of, adiacents}
        self.vertex_labels = defaultdict(set) #'name': {set, of, properties}
        #(from, to): {set, of, properties}
        self.edge_labels = defaultdict(set)

    def add_vertex(self, name):
        '''adds a vertex to the graph'''
        self.nodes.add(name)

    def add_edge(self, node_from, node_to):
        '''Adds an edge to the graph.
        If the nodes aren't in the graph, adds them too.
        '''
        self.nodes.add(node_from)
        self.nodes.add(node_to)
        self.edges[node_from].add(node_to)

    def get_adiacents(self, node):
        '''return a set of adiacent nodes'''
        return self.edges[node]

    def pop_vertex(self, name):
        '''removes the node and the vertex it is connected to'''
        #TODO: it should remove even the edges "pointing" to it
        self.nodes.remove(name)
        del self.edges[name]

    def remove_edge(self, node_from, node_to):
        '''removes an edge'''
        adiacents = self.get_adiacents(node_from)
        adiacents.remove(node_to)

    def get_labels(self, node, node_to=None):
        '''get a set of labels of the node'''
        if not node_to: #it's a vertex
            return self.vertex_labels[node]
        else:
            return self.edge_labels[(node, node_to)]

    def add_label(self, label, node, node_to=None):
        '''Add a label to a vertex/edge.
        If node_to is None, than the label will be applied to a vertex.
        Else, the label will be applied to the edge (node, node_to).
        '''
        if not node_to: #it's a vertex
            self.vertex_labels[node].add(label)
        else:
            self.edge_labels[(node, node_to)].add(label)
            
    def remove_label(self, label, node, node_to=None):
        '''Remove the label from a vertex/edge.
        If node_to is None, than the label will be removed from a vertex.
        Else, the label will be removed from the edge (node, node_to).
        '''
        if not node_to: #it's a vertex
            self.vertex_labels[node].remove(label)
        else:
            self.edge_labels[(node, node_to)].remove(label)

    def has_label(self, label, node, node_to=None):
        '''return True if vertex/edge has that label, else False'''
        if not node_to: #it's a vertex
            if label in self.vertex_labels[node]:
                return True
            else:
                return False
        else:
            if label in self.edge_labels[(node, node_to)]:
                return True
            else:
                return False

    def get_one_leaf(self):
        '''return a vertex with outgoing degree = 0, or None'''
        for name in self.nodes:
            if not self.edges[name]:
                return name
        return None


class PacGraph(object):
    '''A pacman dependency tree handler'''
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
        return self.graph.get_adiacents(node)
        
    def pop_leaf(self):
        '''
        find a "leaf" and return a tuple (leaf,)
        If there isn't any leaf, return (the, smallest, cycle)
        '''
        graph = self.graph
        for node in graph.nodes:
            if graph.has_label('visited', node):
                continue
            for neighbour in graph.get_adiacents(node):
                if not graph.has_label('visited', neighbour):
                    break
            else: #every adiacent has been visited, it's a leaf!
                graph.add_label('visited', node)
                return  node
        
        return None
        
    def _build(self):
        '''build the graph, returns nothing'''
        #[('name','ver', 'repo'), ...]
        to_install = self._needed_packages(self.base_packages)
        for pkg in to_install:
            self.graph.add_vertex(pkg)
            for needed in self._needed_packages((pkg,)):
                if needed != pkg:
                    self.graph.add_edge(pkg, needed)
                    
    def _needed_packages(self, packages=None):
        '''return a list of needed package names'''
        needed = []
        if packages:
            process = Popen('pacman -Sp %s' % (' '.join(packages)),
                        stdout=PIPE, shell=True)
        else:
            process = Popen('pacman -Sup %s', stdout=PIPE, shell=True)
        for line in process.stdout:
            url = line.strip().decode()
            mat = PKG_URL.search(url)
            if mat:
                name = mat.group(2)
                needed.append(name)
        return needed
                    


class PacAtATime(object):
    '''The TRUE PacAtATime working object.
    It represents all the capabilities of the software.
    '''
    def __init__(self, packages):
        '''
        packages is the list of the packages to be installed.
        Empty if it's a system upgrade
        '''
        self.installing = packages
        self.graph = PacGraph(self.installing)
    
    def get_sequence(self):
        '''Returns a valid installing sequence'''
        valid_sequence = []
        while True:
            leaf = self.graph.pop_leaf()
            if not leaf:
                break
            valid_sequence.append(leaf)
        return valid_sequence
        
    def install(self):
        '''install what is asked'''
        to_install = self.get_sequence()
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
        
    def size(self):
        '''return the total size of the packages to be installed'''
        raise NotImplementedError
        
    def max_size(self):
        '''return the maximum size to be installed in a single step'''
        raise NotImplementedError
        
    def _install_package(self, package_name):
        '''actually installs a package (do the process stuff)'''
        raise NotImplementedError


def clean_cache():
    '''removes everything from cache'''
    print "CANCELLO LA CACHE"
    os.system('rm -rf %s/*' % BASE_DIR)

def parse_options(**default_options):
    '''returns a tuple (options, args).
    options is a "strcture", where each field is a boolean.
    args is a list of arguments.
    '''
    usage = "usage: %prog [options] [packages]..."
    parser = OptionParser(usage)
    parser.add_option("-p", "--pretend", action="store_true", dest="pretend", 
    default=False, help="only print the packages we're going to install")
    parser.add_option("-d", "--skip-dependencies", action="store_true",
    dest="skip_deps", default=False, help="skip dependency check")
    parser.set_defaults(**default_options)
    (options, args) = parser.parse_args()
    return options, args

def main():
    '''main program'''
    if os.getuid() != 0:
        print "pacatatime must be run as root"
        sys.exit(1)
    
    options, args = parse_options(atatime=1) #default options in args
    installer = PacAtATime(args)
    if not options.pretend:
        installer.install()
    else:
        print 'To be installed:', ', '.join(installer.get_sequence())

    return 0

if __name__ == '__main__':
    main()

