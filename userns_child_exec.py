#!/usr/bin/env python
# coding=utf-8
""" 
Licensed under GNU General Public License v2 or later

Create a child process that executes a shell command in new
  namespace(s); allow UID and GID mappings to be specified when
  creating a user namespace.

Example:
  First, we look at the run-time environment:
```
$ uname -rs     # Need Linux 3.8 or later
Linux 3.8.0
$ id -u         # Running as unprivileged user
1000
$ id -g
1000
```
  Now start a new shell in new user (-U), mount (-m), and PID (-p)
    namespaces, with user ID (-M) and group ID (-G) 1000 mapped to 0
    inside the user namespace:
```
$ ./userns_child_exec -p -m -U -M '0 1000 1' -G '0 1000 1' bash
```
  The shell has PID 1, because it is the first process in the new PID
    namespace:
```
bash$ echo $$
1
```
  Inside the user namespace, the shell has user and group ID 0, and a
    full set of permitted and effective capabilities:
```
bash$ cat /proc/$$/status | egrep '^[UG]id'
Uid: 0    0    0    0
Gid: 0    0    0    0
bash$ cat /proc/$$/status | egrep '^Cap(Prm|Inh|Eff)'
CapInh:   0000000000000000
CapPrm:   0000001fffffffff
CapEff:   0000001fffffffff
```
  Mounting a new /proc filesystem and listing all of the processes
    visible in the new PID namespace shows that the shell can't see any
    processes outside the PID namespace:
```
bash$ mount -t proc proc /proc
bash$ ps ax
PID TTY      STAT   TIME COMMAND
1  pts/3    S      0:00 bash
22 pts/3    R+     0:00 ps ax
```

Src: http://man7.org/linux/man-pages/man7/user_namespaces.7.html

Also useful:
*https://github.com/torvalds/linux/blob/4f671fe2f9523a1ea206f63fe60a7c7b3a56d5c7/include/uapi/linux/sched.h
*https://stackoverflow.com/questions/13373629/clone-process-support-in-python
*https://docs.python.org/2.7/library/ctypes.html
*https://stackoverflow.com/questions/10730838/how-to-create-multiple-network-namespace-from-a-single-process-instance
*https://docs.python.org/2/library/multiprocessing.html
*http://www.python-course.eu/forking.php

Translated to Python: Filipp Kucheryavy aka Frizzy
"""


import os
import sys
import signal
import logging
import argparse
from ctypes import *


libc = CDLL("libc.so.6")
"""Import libc.so.6 as libc"""

STACK_SIZE = 1024 * 1024
"""#define STACK_SIZE (1024 * 1024)"""

flags = 0
"""
The low byte of flags contains the number of the termination signal
  sent to the parent when the child dies.  If this signal is specified
  as anything other than SIGCHLD, then the parent process must specify
  the __WALL or __WCLONE options when waiting for the child with
  wait(2).  If no signal is specified, then the parent process is not
  signaled when the child terminates.

flags may also be bitwise-or'ed with zero or more of the
  constants, in order to specify what is shared between the calling
  process and the child process

"""

CLONE_NEWIPC = 0x08000000
"""New ipc namespace constant"""
CLONE_NEWNS = 0x00020000
"""New mount namespace group constant"""
CLONE_NEWNET = 0x40000000
"""New network namespace constant"""
CLONE_NEWPID = 0x20000000
"""New pid namespace constant"""
CLONE_NEWUTS = 0x04000000
"""New utsname namespace constant"""
CLONE_NEWUSER = 0x10000000
"""New user namespace constant"""

pipe_fd = os.pipe()

parser = argparse.ArgumentParser(
    description="""
Create a child process that executes a shell
command in a new user namespace,
and possibly also other new namespace(s).""",
    epilog="""
If -z, -M, or -G is specified, -U is required.
It is not permitted to specify both -z and either -M or -G.

Map strings for -M and -G consist of records of the form:

    ID-inside-ns   ID-outside-ns   len

A map string can contain multiple records, separated
 by commas;
the commas are replaced by newlines before writing
 to map files.
""",
    formatter_class=argparse.ArgumentDefaultsHelpFormatter)
aa = parser.add_argument
aa('argv', type=str, nargs='*', default=[],
   help='Command with options for executing')
aa('-i', action='store_true', dest='newipc',
   help='New IPC namespace')
aa('-m', action='store_true', dest='newns',
   help='New mount namespace')
aa('-n', action='store_true', dest='newnet',
   help='New network namespace')
aa('-p', action='store_true', dest='newpid',
   help='New PID namespace')
aa('-u', action='store_true', dest='newuts',
   help='New UTS namespace')
aa('-U', action='store_true', dest='newuser',
   help='New user namespace')
aa('-M', type=str, dest='uid_map',
   help='Specify UID map for user namespace')
aa('-G', type=str, dest='gid_map',
   help='Specify GID map for user namespace')
aa('-z', action='store_true', dest='map_zero',
   help='Map user\'s UID and GID to 0 in user namespace'
   '(equivalent to: -M \'0 <uid> 1\' -G \'0 <gid> 1\')')
aa('-v', action='store_true', dest='verbose',
   help='Display verbose messages')
args = parser.parse_args()

def errExit(msg):
    logging.error(msg)
    sys.exit(1)

def update_map(mapping, map_file):
    """

    Update the mapping file 'map_file', with the value provided in
    'mapping', a string that defines a UID or GID mapping. A UID or
    GID mapping consists of one or more newline-delimited records
    of the form:

        ID_inside-ns    ID-outside-ns   length

    Requiring the user to supply a string that contains newlines is
    of course inconvenient for command-line use. Thus, we permit the
    use of commas to delimit records in this string, and replace them
    with newlines before writing the string to the file.

    """
    #Replace commas in mapping string with newlines
    mapping = mapping.replace(',', '\n')

    with open(map_file, 'w') as f:
        f.write(mapping)

def childFunc():
    """Start function for cloned child.
    
    Using global variables instead of parameters
      because i got a problem with passing parameters...

    Wait until the parent has updated the UID and GID mappings.
    See the comment in main(). We wait for end of file on a
      pipe that will be closed by the parent process once it has
      updated the mappings.

    """
    # Close our descriptor for the write
    # end of the pipe so that we see EOF
    # when parent closes its descriptor

    os.close(pipe_fd[1])
    if os.read(pipe_fd[0], 1):
        logging.error("Failure in child: parent doesn't close its descriptor")
        sys.exit(1)

    # Execute a shell command
    print("About to exec %s\n" % args.argv[0])
    os.execvp(args.argv[0], args.argv)

if __name__ == '__main__':
    #class child_args(Structure):
    #    _fields_ = [("argv", c_char_p * len(args.argv)), # Command to be executed by child, with args
    #                ("pipe_fd", c_int * 2)]              # Pipe used to synchronize parent and child

    #struct child_args {
    #    char **argv;        /* Command to be executed by child, with args */
    #    int    pipe_fd[2];  /* Pipe used to synchronize parent and child */
    #};

    #argv = []            # Command to be executed by child, with args
    #pipe_fd = os.pipe()  # Pipe used to synchronize parent and child
    #arr = (c_char_p * len(args.argv))(*args.argv)
    #child_args = child_args(arr, os.pipe())

    # We use a pipe to synchronize the parent and child, in order to
    # ensure that the parent sets the UID and GID maps before the child
    # calls execve(). This ensures that the child maintains its
    # capabilities during the execve() in the common case where we
    # want to map the child's effective user ID to 0 in the new user
    # namespace. Without this synchronization, the child would lose
    # its capabilities if it performed an execve() with nonzero
    # user IDs (see the capabilities(7) man page for details of the
    # transformation of a process's capabilities during execve()).

    # -M or -G without -U is nonsensical
    if (((args.uid_map or args.gid_map or args.map_zero)
       and not args.newuser)
       or (args.map_zero and (args.uid_map or args.gid_map))
       ):
        parser.usage()
        sys.exit(1)

    if args.newipc:
        flags |= CLONE_NEWIPC
    if args.newns:
        flags |= CLONE_NEWNS
    if args.newnet:
        flags |= CLONE_NEWNET
    if args.newpid:
        flags |= CLONE_NEWPID
    if args.newuts:
        flags |= CLONE_NEWUTS
    if args.newuser:
        flags |= CLONE_NEWUSER

    # Create the child in new namespace(s)
    childFunc = CFUNCTYPE(c_int)(childFunc)
    child_stack = c_char_p(" " * STACK_SIZE)
    child_stack_pointer = c_void_p(cast(child_stack, c_void_p).value + STACK_SIZE)
    child_pid = libc.clone(childFunc, child_stack_pointer, flags | signal.SIGCHLD)

    if child_pid == -1:
        logging.error("Can not execute clone")
        sys.exit(1)

    # Parent falls through to here

    if args.verbose:
        logging.info("PID of child created by clone() is %ld\n",
                    child_pid)

    # Update the UID and GID maps in the child
    if args.uid_map or args.map_zero:
        map_path = "/proc/%s/uid_map" % child_pid
        if args.map_zero:
            args.uid_map = "0 %d 1" % os.getuid()  
        update_map(args.uid_map, map_path)

    if args.gid_map or args.map_zero:
        map_path = "/proc/%s/gid_map" % child_pid
        if args.map_zero:
            args.gid_map = "0 %d 1" % os.getgid() 
        update_map(args.gid_map, map_path)

    # Close the write end of the pipe, to signal to the child that we
    # have updated the UID and GID maps
    os.close(pipe_fd[1])

    # Wait for child
    pid, status = os.waitpid(child_pid, 0)
    logging.info("Child returned: pid %s, status %s", pid, status)

    if args.verbose:
        logging.info("terminating")
