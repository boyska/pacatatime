#!/usr/bin/env python
'''A wrapper on pacman that will install packages/upgrade your system
one package at a time.
It's especially useful for computers with few disk space'''
# -*- coding: utf-8 -*-
#This install just few packages at a time

import os
import sys

from optparse import OptionParser
import re
from collections import defaultdict

import logging
from subprocess import Popen, PIPE
import os.path


DB_PATH = '/var/lib/pacman'
BASE_DIR = "/tmp/pacatatime/cache"
PKG_URL = re.compile(
        '.*/(.*)/os/.*?/(.*)-.*?.pkg.tar.gz', re.UNICODE) #repo, pkg_name+ver


logger = logging.getLogger('pacatatime')

class StopInstallException(Exception):
    def __init__(self):
        pass
    def __str__(self):
        return "User stopped install process"

class DependencyRetrievalError(Exception):
    def __init__(self, packages):
        self.packages = packages
    def __str__(self):
        return "Dependencies could not be retrieved for packages %s" %\
            ','.join(self.packages)
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
        if node in self.edges:
            return self.edges[node]
        return set()

    def remove_vertex(self, name):
        '''removes the node and the vertex it is connected to'''
        self.nodes.discard(name)
        for node in self.nodes:
            adiac = self.get_adiacents(node)
            adiac.discard(name)

        if name in self.edges:
            del self.edges[name]

    def remove_edge(self, node_from, node_to):
        '''removes an edge'''
        adiacents = self.get_adiacents(node_from)
        adiacents.discard(node_to)

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
            self.vertex_labels[node].discard(label)
        else:
            self.edge_labels[(node, node_to)].discard(label)

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

    def clear_label(self, label):
        '''Remove the label for each node and vertex'''
        for vertex in self.nodes:
            self.remove_label(label, vertex)

        for edge in self.edges:
            node_from, node_to = edge
            self.remove_label(label, node_from, node_to)

    def print_as_tree(self):
        for vertex in self.nodes:
            self.print_subtree(vertex, 0)
    def print_subtree(self, vertex, indent):
        if "_tree_visited" in self.get_labels(vertex):
            return
        self.add_label("_tree_visited", vertex)
        print '-'*indent + vertex
        for adiac in self.get_adiacents(vertex):
            self.print_subtree(adiac, indent+1)
    def get_one_leaf(self):
        '''return a vertex with outgoing degree = 0, or None'''
        for name in self.nodes:
            if not self.edges[name]:
                return name
        return None


class PacGraph(DiGraph):
    '''A pacman dependency tree handler'''
    def __init__(self, packages):
        '''
        packages is a list.
        they'll be the only node in the graph with incoming degree = 0
        '''
        DiGraph.__init__(self)
        self.base_packages = packages
        
        self._build()
        
    def get_dependencies(self, node):
        '''return adiacent nodes on the graph'''
        return self.get_adiacents(node)
        
    def pop_leaf(self):
        '''
        find a "leaf" and return a tuple (leaf,)
        If there isn't any leaf, return (the, smallest, cycle)
        '''
        for node in self.nodes:
            if self.has_label('visited', node):
                continue
            for neighbour in self.get_adiacents(node):
                if not self.has_label('visited', neighbour):
                    break
            else: #every adiacent has been visited, it's a leaf!
                #we should do graph.add_label('visited', node)
                #but we defer it to the "installer"!
                #so that we can handle install error properly
                return  node
        
        return None
        
    def _build(self):
        '''build the graph, returns nothing'''
        #[('name','ver', 'repo'), ...]
        to_install = self._needed_packages(self.base_packages)
        for pkg in to_install:
            self.add_vertex(pkg)
            try:
                for needed in self._needed_packages((pkg,)):
                    if needed != pkg:
                        self.add_edge(pkg, needed)
            except DependencyRetrievalError:
                self.add_label("error", pkg)
                logger.warning("Error while retrieving dependencies for %s" % pkg)
                    
    def _needed_packages(self, packages=None):
        '''return a list of needed package names'''
        needed = []
        if packages:
            process = Popen('pacman -Sp --noconfirm %s' % (' '.join(packages)),
                        stdout=PIPE, stderr=PIPE, shell=True)
            process.stdout.next() #dependency resolutions...
        else:
            process = Popen('pacman -Sup --noconfirm %s', stdout=PIPE,
                    stderr=PIPE, shell=True)
            process.stdout.next() #System upgrading...
            process.stdout.next() #dependency resolutions...
        if process.stderr.readlines():
            raise DependencyRetrievalError, packages

        for line in process.stdout:
            url = line.strip().decode()
            mat = PKG_URL.search(url)
            if mat:
                name_ver = mat.group(2)
                repo = mat.group(1)
                name = get_name_from_db(repo, name_ver)
                needed.append(name)
            else:
                logger.warning("url %s doesn't match to a package name" % url)
        return needed
                    

def get_name_from_db(repo, name_ver):
    '''reads the appropriate file in the db, return the name of the package'''
    f = open('/var/lib/pacman/sync/%s/%s/desc' % (repo, name_ver), 'r')
    rightline = False
    for line in f:
        if rightline:
            f.close()
            return line.strip()
        if line == '%NAME%\n':
            rightline = True

    f.close()
    return None



class PacAtATime(object):
    '''The TRUE PacAtATime working object.
    It represents all the capabilities of the software.
    '''
    CACHE_DIR = '/tmp/pacatatime/cache'
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
        last = []
        while True:
            leaf = self.graph.pop_leaf()
            if not leaf:
                break
             
            self.graph.add_label('visited', leaf)
            if not self.graph.has_label("error", leaf):
                valid_sequence.append(leaf)
            else:
                last.append(leaf)
        valid_sequence.extend(last)
        return valid_sequence
        
    def install(self, interactive=False):
        '''install what is asked'''
        to_install = self.get_sequence()
        for pkg in to_install:
            try:
                self._install_package(pkg, pkg in self.installing, interactive)
            except StopInstallException:
                logger.info("the user aborted the installation")
                return -1
            self._clean_cache()
    
    def _install_package(self, package_name, explicit, interactive):
        '''actually installs a package (do the process stuff)'''
        #check how many packages we are installing
        process = Popen('pacman -Sp --noconfirm %s' % package_name,
                    stdout=PIPE, stderr=PIPE, shell=True)
        process.stdout.next() #dependency resolutions...
        howmany = len(tuple(process.stdout))

        if howmany != 1:
            if interactive:
                print 'WARNING! PacAtATime is trying to install'\
                        '%d packages in a single step\n'\
                        'it shouldn\'t be possible to do better, but if you think'\
                        'you can do so, say N to exit and install "by hand"' % howmany

                print 'Do you want to install %d packages in a single step? [Y/n]' % howmany,
                input = raw_input()
                if input == 'n':
                    raise StopInstallException
            else: #batch
                logger.info('Installing %s and %d packages in a single step' % (package_name, howmany-1))

        if explicit:
            os.system('pacman -S --noconfirm --needed --asexplicit '\
            '--cachedir %s %s' % (self.CACHE_DIR, package_name))
        else: #dep
            os.system('pacman -S --noconfirm --needed --asdeps '\
            '--cachedir %s %s' % (self.CACHE_DIR, package_name))

    def _clean_cache(self):
        for (dirpath, dirs, files) in os.walk(self.CACHE_DIR):
            for file in files:
                os.remove(os.path.join(dirpath, file))
            for dir in dirs:
                os.rmdir(os.path.join(dirpath, dir))



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
    parser.add_option("-v", "--verbose", action="store_true",
        dest="verbose", default=False, help="more verbose")
    parser.add_option("-t", "--show-tree", action="store_true",
        dest="show_tree", default=False, help="show dependency tree")
    parser.add_option("-i", "--interactive", action="store_true",
        dest="interactive", default=True, help="ask for action [default]")
    parser.add_option("-b", "--batch", action="store_false",
        dest="interactive", default=True, help="never ask for action")
    parser.set_defaults(**default_options)
    (options, args) = parser.parse_args()
    return options, args

def _logging_init(verbose=0):
    #logging to file
    file_handler = logging.FileHandler(os.path.expanduser('~/.pacatatime.log'), mode='w')
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    if verbose:
        #logging to stderr
        console_handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        logger.addHandler(console_handler)
    logger.setLevel(logging.INFO)

def main():
    '''main program'''
    if os.getuid() != 0:
        print "pacatatime must be run as root"
        sys.exit(1)
    
    options, args = parse_options(verbose=False) #default options in args
    _logging_init(options.verbose)
    installer = PacAtATime(args)
    if options.show_tree:
        installer.graph.print_as_tree()
        sys.exit()
    if not options.pretend:
        installer.install(options.interactive)
    else:
        print 'To be installed:', ', '.join(installer.get_sequence())

    sys.exit()

if __name__ == '__main__':
    main()

