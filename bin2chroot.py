#!/usr/bin/env python
# coding=utf-8
# original idea:
#   http://www.cyberciti.biz/faq/howto-run-nginx-in-a-chroot-jail/
#   http://bash.cyberciti.biz/web-server/nginx-chroot-helper-bash-shell-script/
"""
Copyright (c) by Filipp Kucheryavy aka Frizzy <filipp.s.frizzy@gmail.com>
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted 
provided that the following conditions are met:

a. Redistributions of source code must retain the above copyright notice, this list of 
conditions and the following disclaimer. 

b. Redistributions in binary form must reproduce the above copyright notice, this list of 
conditions and the following disclaimer in the documentation and/or other materials provided 
with the distribution. 

c. Neither the name of the nor the names of its contributors may be used to endorse or promote 
products derived from this software without specific prior written permission. 

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS 
OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY 
AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE 
COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, 
EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF 
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER 
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF 
ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
""" 

import os
import sys
import shutil
import argparse

mknode = "/bin/mknod"
ldd = "/usr/bin/ldd"

if os.path.splitdrive(sys.executable)[0]:
    root = os.path.splitdrive(sys.executable)[0]
else:
    root = "/"

root_structure = ["etc",
                  "dev",
                  "var",
                  "usr",
                  "tmp",
                  "lib",
                  "lib64",]

etc_files = ["group",
             "prelink.cache",
             "services",
             "adjtime",
             "shells",
             #"gshadow",
             #"shadow",
             "hosts.deny",
             "localtime",
             "nsswitch.conf",
             "nscd.conf",
             "prelink.conf",
             "protocols",
             "hosts",
             #"passwd",
             "ld.so.cache",
             "ld.so.conf",
             "resolv.conf",
             "host.conf",]

etc_dir = ["ld.so.conf.d",
           "prelink.conf.d",]

var_dir = ["tmp",
           "run",]

def bin2chroot(directory, binaries, config=""):
    if os.getuid() != 0:
        print("you are not root")
        sys.exit(1)

    if os.path.exists(directory):
        q = "Directory %s exist. Do you want to copy binary into it? " % directory
        y = ("y", "Y", "yes", "Yes")
        try:
            if not str(raw_input(q)) in y:
                sys.exit(1)
        except:
            if not str(input(q)) in y:
                sys.exit(1)
    else:
        os.mkdir(directory)

    for d in root_structure:
        di = os.path.join(directory, d)
        if not os.path.exists(di):
            os.mkdir(di)

    if os.path.exists(os.path.join(directory, "var")):
        for d in var_dir:
            tmp = os.path.join(directory, "var", d)
            if not os.path.exists(tmp):
                os.mkdir(tmp))

    os.system("%s -m 0666 %s c 1 3" % (mknode, os.path.join(directory, "dev", "null")))
    os.system("%s -m 0666 %s c 1 8" % (mknode, os.path.join(directory, "dev", "random")))
    os.system("%s -m 0444 %s c 1 9" % (mknode, os.path.join(directory, "dev", "urandom")))

    for b in binaries.split(","):
        bnew = os.path.join(directory, b[len(root):])
        copy(b, bnew)
        stdout = os.popen('%s %s' % (ldd, b))
        for l in stdout:
            if "=" in l and len(l.split()) > 3:
                b = l.split()[2]
            elif "=" not in l:
                b = l.split()[0]
            else:
                continue
            bnew = os.path.join(directory, b[len(root):])
            copy(b, bnew)
        
    for f in etc_files:
        copy(os.path.join(root, "etc", f), os.path.join(directory, "etc", f))

    for d in etc_dir:
        copy(s.path.join(root, "etc", d), os.path.join(directory, "etc", d))

    if config:
        copy(config, os.path.join(directory, config[len(root):]))

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
    parser = argparse.ArgumentParser(description='This utility create chroot directory and сopy binary with required libs to it')
    parser.add_argument('directory', action='store', help='chroot directory')
    parser.add_argument('binaries', action='store', help='binaries for copying')
    parser.add_argument('-c', action='store', dest='config', default="", help='binaries for copying')
    args = parser.parse_args()
    print("hello %s" % os.getlogin())
    bin2chroot(args.directory, args.binaries, args.config)
    print("All done, bye!")
    sys.exit(0)