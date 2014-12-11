#!/usr/bin/env python
# coding=utf-8

"""
The MIT License (MIT)

Copyright (c) 2014 Filipp Kucheryavy aka Frizzy <filipp.s.frizzy@gmail.com>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
""" 

import os
import sys
import shutil
import argparse

ldd, _ = os.Popen(['which', 'ldd']).communicate()

if os.path.splitdrive(sys.executable)[0]:
    root = os.path.splitdrive(sys.executable)[0]
else:
    root = "/"

rootfs_structure = [
    'bin',
    'dev',
    'etc',
    'home',
    'lib',
    'lib64',
    'opt',
    'proc',
    'root',
    'run',
    'sbin',
    'sys',
    'tmp',
    'usr',
    'var',
]

nodes = [
    ('tty', 'crw-rw-rw-')
    ('console', 'crw-------')
    ('tty0', 'crw--w----')
    ('tty1' 'crw-rw----')
    ('tty5' 'crw-rw----')
    ('ram0', 'brw-rw----')
    ('null', 'crw-rw-rw-')
    ('zero', 'crw-rw-rw-')
    ('random', 'crw-rw-rw-')
    ('urandom', 'crw-rw-rw-')
]

def copy(src, dst):
    if os.path.isfile(src):
        if not os.path.exists(os.path.dirname(dst)):
            os.makedirs(os.path.dirname(dst))
        shutil.copy(src, dst)
    elif os.path.isdir(src):
        if not os.path.exists(os.path.dirname(dst)):
            os.makedirs(os.path.dirname(dst))
        shutil.copytree(src, dst)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This utility create chroot rootfs and сopy binary with required libs to it')
    parser.add_argument('--rootfs', action='store', dest='rootfs', help='chroot rootfs')
    parser.add_argument('-p|--path', action='store', dest='path', help='main path')
    parser.add_argument('-n|--name', action='store', dest='name', help='name')
    parser.add_argument('-b|--binaries', action='store', dest='binaries', help='binaries for copying')
    parser.add_argument('-c', action='store', dest='config', default="", help='binaries configs for copying')
    args = parser.parse_args()

    if os.getuid() != 0:
        print("you are not root")
        sys.exit(1)

    if os.path.exists(rootfs):
        q = "Directory %s exist. Do you want to copy binary into it? " % rootfs
        y = ("y", "Y", "yes", "Yes")
        try:
            if not str(raw_input(q)) in y:
                sys.exit(1)
        except:
            if not str(input(q)) in y:
                sys.exit(1)
    else:
        os.mkdir(rootfs)

    for d in rootfs_structure:
        di = os.path.join(rootfs, d)
        if not os.path.exists(di):
            os.mkdir(di)

    for node in nodes:
        name = os.path.join(os.path.join(rootfs, 'dev'), node[0])
        mode = node[1]
        os.mknod(name, mode)

    for b in binaries.split(","):
        bnew = os.path.join(rootfs, b[len(root):])
        copy(b, bnew)
        stdout = os.popen('%s %s' % (ldd, b))
        for l in stdout:
            if "=" in l and len(l.split()) > 3:
                b = l.split()[2]
            elif "=" not in l:
                b = l.split()[0]
            else:
                continue
            bnew = os.path.join(rootfs, b[len(root):])
            copy(b, bnew)

    if config:
        for c in config.split(','):
            copy(c, os.path.join(rootfs, c[len(root):]))
