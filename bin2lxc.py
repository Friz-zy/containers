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

# NOTE: Skype: lxc-create -t bin2lxc -n test3 -- -b /usr/bin/skype --network --gui --exec "/usr/bin/skype"

# NOTE: apt-get: lxc-create -t bin2lxc -n aptget -- -b apt-get,ping -c /etc/apt/sources.list,/etc/apt/trusted.gpg,/etc/apt/apt.conf.d/,/usr/lib/apt/ --network --gui
# NOTE: apt-get run: apt-get -o APT::System="Debian dpkg interface"

# NOTE: use strace and chroot to debug the problem

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
    '/dev/dri',
    '/dev/snd',
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
    '/run/resolvconf',
    '/sbin',
    '/sys',
    '/tmp',
    '/tmp/.X11-unix',
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
    ('/dev/video0', 33204, 2, 252),
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
    ('/etc/resolv.conf', '/run/resolvconf/resolv.conf'),
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

gui_config = """
lxc.id_map = u 0 100000 1000
lxc.id_map = g 0 100000 1000
lxc.id_map = u 1000 1000 1
lxc.id_map = g 1000 1000 1
lxc.id_map = u 1001 101001 64535
lxc.id_map = g 1001 101001 64535

lxc.mount.entry = /dev/dri dev/dri none bind,optional,create=dir
lxc.mount.entry = /dev/snd dev/snd none bind,optional,create=dir
lxc.mount.entry = /tmp/.X11-unix tmp/.X11-unix none bind,optional,create=dir
lxc.mount.entry = /dev/video0 dev/video0 none bind,optional,create=file

lxc.hook.pre-start = {path}/setup-pulse.sh
"""

gui_pulse_script = """#!/bin/sh
PULSE_PATH={rootfs}/root/.pulse_socket

if [ ! -e "$PULSE_PATH" ] || [ -z "$(lsof -n $PULSE_PATH 2>&1)" ]; then
    pactl load-module module-native-protocol-unix auth-anonymous=1 \
        socket=$PULSE_PATH
fi
"""

network_binaries = ",".join((
    "sh","bash","ifconfig",
    "dhclient","dhclient-script",
    "ip","hostname","sleep",""
    ))

network_configs = "/lib/x86_64-linux-gnu/libnss_files.so.2,/lib/x86_64-linux-gnu/libnss_dns.so.2,/lib/x86_64-linux-gnu/libresolv.so.2,"

# recommended_binaries = "init.lxc,"

dhconf = "send host-name = gethostname();\n"

ninit = """
ifconfig eth0 up 2>&1 >/dev/null &
dhclient eth0 -cf /etc/dhclient.conf 2>&1 >/dev/null &
"""

gui_binaries = "ldconfig.real,env,sleep,"

gui_configs = "/etc/ld.so.conf.d,/etc/ld.so.conf,"

rscript = """#!/bin/sh
CONTAINER={name}
CMD_LINE="{execute}"

STARTED=false

if ! lxc-wait -n $CONTAINER -s RUNNING -t 0; then
    lxc-start -n $CONTAINER -d
    lxc-wait -n $CONTAINER -s RUNNING
    STARTED=true
fi

PULSE_SOCKET=/root/.pulse_socket

lxc-attach --clear-env -n $CONTAINER -- sleep 1 & env DISPLAY=$DISPLAY PULSE_SERVER=$PULSE_SOCKET $CMD_LINE

if [ "$STARTED" = "true" ]; then
    lxc-stop -n $CONTAINER -t 10
fi
"""

icon = """[Desktop Entry]
Name=lxc-{name}
Exec={path}/start-{name} %U
Type=Application
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
        if not os.path.exists(dst):
            os.makedirs(dst)
        for item in os.listdir(src):
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                copy(s, d)
            else:
                shutil.copy2(s, d)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='This utility create lxc rootfs and сopy binaries with required libs to it')
    parser.add_argument('-r', '--rootfs', action='store', dest='rootfs', help='chroot rootfs')
    parser.add_argument('-p', '--path', action='store', dest='path', help='main path')
    parser.add_argument('-n', '--name', action='store', dest='name', help='name')
    parser.add_argument('-u', '--mapped-uid', action='store', dest='uid', help='mapped uid')
    parser.add_argument('-g', '--mapped-gid', action='store', dest='gid', help='mapped gid')
    parser.add_argument('-b', '--binaries', action='store', dest='binaries', help='binaries for copying')
    parser.add_argument('-c', '--configs', action='store', dest='configs', default="", help='binaries configs for copying')
    parser.add_argument('--network', action='store_true', dest='network', default="", help='copy network binaries and add commands to init script')
    parser.add_argument('--gui', action='store_true', dest='gui', help='add access to video and audio')
    parser.add_argument('--exec', action='store', dest='execute', default="/bin/bash", help='lxc-start by default execute programm with args (as given string)')
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
        with open(pinit, 'w+') as f:
            f.write(ninit)
        st = os.stat(pinit)
        # +x=73
        os.chmod(pinit, st.st_mode | 73)
        os.chown(pinit, uid, gid)
        # dns
        presolf = rootfs + '/run/resolvconf/resolv.conf'
        with open(presolf, 'w') as f:
            f.write('nameserver 8.8.8.8\nnameserver 8.8.4.4\n')
        os.chown(presolf, uid, gid)
        configs = network_configs + configs

    if args.gui:
        binaries = gui_binaries + binaries
        configs = gui_configs + configs
        with open(pconfig, "r") as f:
            oconf = f.readlines()
            nconf = []
            for l in oconf:
                if not "lxc.id_map" in l:
                    nconf.append(l.rstrip())
            gui_config = gui_config.format(path=path)
            nconf += gui_config.splitlines()
        with open(pconfig, "w") as f:
            f.write("\n".join(nconf))
        pscript = path + "/setup-pulse.sh"
        with open(pscript, "a") as f:
            f.write(gui_pulse_script.format(rootfs=rootfs))
        # +x=73
        os.chmod(pscript, st.st_mode | 73)
        os.chown(pscript, uid, gid)
        ppulse = rootfs + '/root/.pulse'
        if not os.path.exists(ppulse):
            os.mkdir(ppulse)
        os.chown(ppulse, uid, gid)
        cpulse = ppulse + '/client.conf'
        with open(cpulse, 'w') as f:
            f.write("disable-shm=yes")
        os.chown(cpulse, uid, gid)
        prscript = path + '/start-' + name
        with open(prscript, 'w') as f:
            f.write(rscript.format(
                name=name, execute=args.execute
                ))
        # +x=73
        os.chmod(prscript, st.st_mode | 73)
        os.chown(prscript, uid, gid)
        picon =  "{home}/.local/share/applications/lxc-{name}.desktop".format(home=os.path.expanduser("~"), name=name)
        with open(picon, 'w') as f:
            f.write(icon.format(name=name, path=path))
        # +x=73
        os.chmod(picon, st.st_mode | 73)
        os.chown(picon, uid, gid)

    if args.execute:
        pinit = rootfs + '/sbin/init'
        with open(pinit, 'a') as f:
            if not args.gui:
                f.write("ldconfig.real &\nexec " + args.execute)
            else:
                f.write("exec /bin/bash")

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
