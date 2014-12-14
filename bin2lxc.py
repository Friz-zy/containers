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
import platform
from getpass import getuser
from subprocess import Popen, PIPE

ldd = Popen(['which', 'ldd'], stdout=PIPE, stderr=PIPE).communicate()[0].strip()

if os.path.splitdrive(sys.executable)[0]:
    root = os.path.splitdrive(sys.executable)[0]
else:
    root = "/"

rootfs_structure = [
    'bin',
    'dev',
    'dev/pts',
    'etc',
    'home',
    'lib',
    'lib64',
    'lxc_putold',
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

# os.stat(path)
# st_mode
# os.minor(st_dev)
# os.major(st_dev)
nodes = [
    ('console', 33204, 2, 252),
    ('full', 33204, 2, 252),
    ('null', 33204, 2, 252),
    ('random', 33204, 2, 252),
    ('tty', 33204, 2, 252),
    ('tty1', 33200, 2, 252),
    ('tty2', 33200, 2, 252),
    ('tty3', 33200, 2, 252),
    ('tty4', 33200, 2, 252),
    ('urandom', 33204, 2, 252),
    ('zero', 33204, 2, 252),
]

links = [
    ('core', '/proc/kcore'),
    ('fd', '/proc/self/fd/'),
    ('kmsg', 'console'),
    ('ptmx', '/dev/pts/ptmx'),
    ('shm', '/run/shm/'),
    ('stderr', 'fd/2'),
    ('stdin', 'fd/0'),
    ('stdout', 'fd/1'),
]

config = """

# Distribution configuration
lxc.include = /usr/share/lxc/config/ubuntu.common.conf
lxc.include = /usr/share/lxc/config/ubuntu.userns.conf
lxc.arch = {arch}

# Container specific configuration
lxc.id_map = u 0 100000 65536
lxc.id_map = g 0 100000 65536
lxc.rootfs = {rootfs}
lxc.utsname = {name}

# Network configuration
lxc.network.type = veth
lxc.network.link = lxcbr0
"""


def copy(src, dst):
    if os.path.isfile(src):
        if not os.path.exists(os.path.dirname(dst)):
            os.makedirs(os.path.dirname(dst))
        shutil.copy2(src, dst)
    elif os.path.isdir(src):
        if not os.path.exists(os.path.dirname(dst)):
            os.makedirs(os.path.dirname(dst))
        shutil.copytree(src, dst)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This utility create lxc rootfs and сopy binaries with required libs to it')
    parser.add_argument('-r', '--rootfs', action='store', dest='rootfs', help='chroot rootfs')
    parser.add_argument('-p', '--path', action='store', dest='path', help='main path')
    parser.add_argument('-n', '--name', action='store', dest='name', help='name')
    parser.add_argument('-u', '--mapped-uid', action='store', dest='uid', help='mapped uid')
    parser.add_argument('-g', '--mapped-gid', action='store', dest='gid', help='mapped gid')
    parser.add_argument('-b', '--binaries', action='store', dest='binaries', help='binaries for copying')
    parser.add_argument('-c', '--configs', action='store', dest='configs', default="", help='binaries configs for copying')
    args = parser.parse_args()

    rootfs = args.rootfs
    path = args.path
    name = args.name
    binaries = args.binaries or ""
    configs = args.configs or ""
    uid = int(args.uid) or os.getuid()
    gid = int(args.gid) or os.getgid()

    if not rootfs or not path or not name:
        print("not enough arguments")
        sys.exit(1)

    if not os.path.exists(rootfs):
        os.mkdir(rootfs)
    os.chown(rootfs, uid, gid)

    for d in rootfs_structure:
        di = os.path.join(rootfs, d)
        if not os.path.exists(di):
            os.mkdir(di)
        os.chown(di, uid, gid)

    for node in nodes:
        pth = os.path.join(os.path.join(rootfs, 'dev'), node[0])
        mode = node[1]
        dev = os.makedev(node[2], node[3])
        if not os.path.exists(pth):
            os.mknod(pth, mode, dev)
        os.chown(pth, uid, gid)

    for l in links:
        pth = os.path.join(os.path.join(rootfs, 'dev'), l[0])
        os.symlink(l[1], pth)

    pconfig = os.path.join(path, "config")
    with open(pconfig, "w+") as f:
        f.write(config.format(arch=platform.processor(), rootfs=rootfs, name=name))

    if binaries:
        for b in binaries.split(","):
            b = Popen(['which', b], stdout=PIPE, stderr=PIPE).communicate()[0].strip()
            bnew = os.path.join(rootfs, b[len(root):])
            copy(b, bnew)
            os.chown(bnew, uid, gid)
            stdout = Popen([ldd, b], stdout=PIPE, stderr=PIPE).communicate()[0].strip()
            for l in stdout.split('\n'):
                if "=" in l and len(l.split()) > 3:
                    b = l.split()[2]
                elif "=" not in l:
                    b = l.split()[0]
                else:
                    continue
                bnew = os.path.join(rootfs, b[len(root):])
                copy(b, bnew)
                os.chown(bnew, uid, gid)

    if configs:
        for c in configs.split(','):
            new = os.path.join(rootfs, c[len(root):])
            copy(c, new)
            os.chown(new, uid, gid)
