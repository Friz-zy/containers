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
from subprocess import Popen, PIPE

ldd = Popen(['which', 'ldd'], stdout=PIPE, stderr=PIPE).communicate()[0].strip()

rootfs_structure = [
    '/bin',
    '/dev',
    '/dev/pts',
    '/etc',
    '/home',
    '/lib',
    '/lib64',
    '/lxc_putold',
    '/opt',
    '/proc',
    '/root',
    '/run',
    '/run/lock',
    '/sbin',
    '/sys',
    '/tmp',
    '/usr',
    '/usr/bin',
    '/usr/games',
    '/usr/include',
    '/usr/lib',
    '/usr/local',
    '/usr/sbin',
    '/usr/share',
    '/usr/src',
    '/var',
    '/var/backups',
    '/var/cache',
    '/var/crash',
    '/var/lib',
    '/var/local',
    '/var/log',
    '/var/mail',
    '/var/opt',
    '/var/spool',
    '/var/tmp',
]

# os.stat(path)
# st_mode
# os.minor(st_dev)
# os.major(st_dev)
nodes = [
    ('/dev/console', 33204, 2, 252),
    ('/dev/full', 33204, 2, 252),
    ('/dev/null', 33204, 2, 252),
    ('/dev/random', 33204, 2, 252),
    ('/dev/tty', 33204, 2, 252),
    ('/dev/tty1', 33200, 2, 252),
    ('/dev/tty2', 33200, 2, 252),
    ('/dev/tty3', 33200, 2, 252),
    ('/dev/tty4', 33200, 2, 252),
    ('/dev/urandom', 33204, 2, 252),
    ('/dev/zero', 33204, 2, 252),
]

links = [
    ('/dev/core', '/proc/kcore'),
    ('/dev/fd', '/proc/self/fd/'),
    ('/dev/kmsg', '/dev/console'),
    ('/dev/ptmx', '/dev/pts/ptmx'),
    ('/dev/shm', '/run/shm/'),
    ('/dev/stderr', '/dev/fd/2'),
    ('/dev/stdin', '/dev/fd/0'),
    ('/dev/stdout', '/dev/fd/1'),
    ('/var/lock', '/run/lock'),
    ('/var/run', '/run'),
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

network_binaries = ",".join((
    "sh","bash","ifconfig",
    "dhclient","dhclient-script",
    "ip","hostname","sleep",""
    ))

# recommended_binaries = "init.lxc,"

dhconf = "send host-name = gethostname();\n"

init = """
ifconfig eth0 up
dhclient eth0 -cf /etc/dhclient.conf
exec /bin/bash
"""


def copy(src, dst):
    """copy file or directory.

    Copy file or directory with metadata
      and permission bits.

    """
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
    parser.add_argument('--network', action='store_true', dest='network', default="", help='copy sh, ifconfig, dhclient, init.lxc + up network')
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
        di = rootfs + d
        if not os.path.exists(di):
            os.mkdir(di)
        os.chown(di, uid, gid)

    for node in nodes:
        pth = rootfs + node[0]
        mode = node[1]
        dev = os.makedev(node[2], node[3])
        if not os.path.exists(pth):
            os.mknod(pth, mode, dev)
        os.chown(pth, uid, gid)

    for l in links:
        pth = rootfs + l[0]
        os.symlink(l[1], pth)

    pconfig = path + "/config"
    with open(pconfig, "w+") as f:
        f.write(config.format(
            arch=platform.processor(), rootfs=rootfs, name=name
            ))

    if args.network:
        binaries = network_binaries + binaries
        if not os.path.exists(rootfs + "/var/lib/dhcp/"):
            os.mkdir(rootfs + "/var/lib/dhcp/")
        if not os.path.exists(rootfs + "/etc/fstab"):
            with open(rootfs + "/etc/fstab", 'w') as f:
                f.write("")
        pdhconf = rootfs + '/etc/dhclient.conf'
        with open(pdhconf, 'w') as f:
            f.write(dhconf)
        os.chown(pdhconf, uid, gid)
        pinit = rootfs + '/sbin/init'
        with open(pinit, 'w') as f:
            f.write(init)
        st = os.stat(pinit)
        # +x=73
        os.chmod(pinit, st.st_mode | 73)
        os.chown(pinit, uid, gid)

    if binaries:
        for b in binaries.split(","):
            p = Popen(['which', b], stdout=PIPE, stderr=PIPE)
            b = p.communicate()[0].strip()
            bnew = rootfs + b
            copy(b, bnew)
            os.chown(bnew, uid, gid)
            p = Popen([ldd, b], stdout=PIPE, stderr=PIPE)
            stdout = p.communicate()[0].strip()
            for l in stdout.split('\n'):
                if 'lib' in l:
                    if "=" in l and len(l.split()) > 3:
                        b = l.split()[2]
                    elif "=" not in l:
                        b = l.split()[0]
                    else:
                        continue
                    bnew = rootfs + b
                    copy(b, bnew)
                    os.chown(bnew, uid, gid)

    if configs:
        for c in configs.split(','):
            new = rootfs + c
            copy(c, new)
            os.chown(new, uid, gid)
