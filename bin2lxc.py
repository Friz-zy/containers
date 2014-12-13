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

# os.stat(path)
# st_mode
# os.minor(st_dev)
# os.major(st_dev)
nodes = [
    ('tty', 8630, 5, 0),
    ('console', 8576, 5, 1),
    ('tty0', 8592, 4, 0),
    ('tty1', 8624, 4, 0),
    ('tty5', 8624, 4, 0),
    ('ram0', 25008, 1, 0),
    ('null', 8630, 1, 3),
    ('zero', 8630, 1, 5),
    ('random', 8630, 1, 8),
    ('urandom', 8630, 1, 9),
]

config = {
    "lxc.id_map": "u 0 100000 65536",
    "lxc.id_map": "g 0 100000 65536",
    "lxc.network.type": "veth",
    "lxc.network.link": "lxcbr0",
    "lxc.mount.entry": "proc proc proc nodev,noexec,nosuid 0 0",
    "lxc.mount.entry": "sysfs sys sysfs ro 0 0",
    "lxc.tty": "1",
}

clines = [
    "# When using LXC with apparmor, uncomment the next line to run unconfined:",
    "#lxc.aa_profile = unconfined"
]


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
    uid = args.uid or os.getuid()
    gid = args.gid or os.getgid()

    if not rootfs or not path or not name:
        print("not enough arguments")
        sys.exit(1)

    if os.getuid() != 0:
        print("you are not root, try this one:")
        print("sudo usermod -v 100000-200000 -w 100000-200000 $USER")
        with open("/etc/lxc/lxc-usernet", "r") as f:
            if getuser() not in f.read():
                print('echo "$USER veth lxcbr0 2" | sudo tee -a /etc/lxc/lxc-usernet')
        print(" ".join((
            "sudo",
            __file__,
            "-r",
            rootfs,
            "-p",
            path,
            "-n",
            name,
            "-u",
            str(uid),
            "-g",
            str(gid),
            "-b",
            binaries,
            "-c",
            configs))
        )
        sys.exit(1)

    if os.path.exists(rootfs):
        q = "Directory %s exist. Do you want to copy binaries into it? " % rootfs
        y = ("y", "Y", "yes", "Yes")
        try:
            if not str(raw_input(q)) in y:
                sys.exit(1)
        except:
            sys.exit(1)
    else:
        os.mkdir(rootfs)
    os.chown(rootfs, uid, gid)

    for d in rootfs_structure:
        di = os.path.join(rootfs, d)
        if not os.path.exists(di):
            os.mkdir(di)
        os.chown(di, uid, gid)

    for node in nodes:
        name = os.path.join(os.path.join(rootfs, 'dev'), node[0])
        mode = node[1]
        dev = os.makedev(node[2], node[3])
        if not os.path.exists(name):
            os.mknod(name, mode, dev)
        os.chown(name, uid, gid)

    pconfig = os.path.join(path, "config")
    with open(pconfig, "a+") as f:
        ctext = f.read()
        for k in config:
            if k not in ctext:
                clines.append(" = ".join((k, config[k])))
        f.writelines(clines)

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
