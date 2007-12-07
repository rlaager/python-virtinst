#
# Utility functions for the command line drivers
#
# Copyright 2006-2007  Red Hat, Inc.
# Jeremy Katz <katzj@redhat.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free  Software Foundation; either version 2 of the License, or
# (at your option)  any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
# MA 02110-1301 USA.

import os, sys
import logging
import logging.handlers
from optparse import OptionValueError

import libvirt
import util
import Guest

MIN_RAM = 256

#
# Setup helpers
#

def setupLogging(appname, debug=False):
    # set up logging
    vi_dir = os.path.expanduser("~/.virtinst")
    if not os.access(vi_dir,os.W_OK):
        try:
            os.mkdir(vi_dir)
        except IOError, e:
            raise RuntimeError, "Could not create %d directory: " % vi_dir, e

    dateFormat = "%a, %d %b %Y %H:%M:%S"
    fileFormat = "[%(asctime)s " + appname + " %(process)d] %(levelname)s (%(module)s:%(lineno)d) %(message)s"
    streamFormat = "%(asctime)s %(levelname)-8s %(message)s"
    filename = os.path.join(vi_dir, appname + ".log")

    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)
    fileHandler = logging.handlers.RotatingFileHandler(filename, "a",
                                                       1024*1024, 5)

    fileHandler.setFormatter(logging.Formatter(fileFormat,
                                               dateFormat))
    rootLogger.addHandler(fileHandler)

    streamHandler = logging.StreamHandler(sys.stderr)
    streamHandler.setFormatter(logging.Formatter(streamFormat,
                                                 dateFormat))
    if debug:
        streamHandler.setLevel(logging.DEBUG)
    else:
        streamHandler.setLevel(logging.ERROR)
    rootLogger.addHandler(streamHandler)

def getConnection(connect):
    if connect is None or connect.lower()[0:3] == "xen":
        if os.geteuid() != 0:
            print >> sys.stderr, "Must be root to create Xen guests"
            sys.exit(1)

    return libvirt.open(connect)

#
# Prompting
#

def prompt_for_input(prompt = "", val = None):
    if val is not None:
        return val
    print prompt + " ",
    return sys.stdin.readline().strip()

def yes_or_no(s):
    s = s.lower()
    if s in ("y", "yes", "1", "true", "t"):
        return True
    elif s in ("n", "no", "0", "false", "f"):
        return False
    raise ValueError, "A yes or no response is required"

#
# Ask for attributes
#

def get_name(name, guest):
    while 1:
        name = prompt_for_input(_("What is the name of your virtual machine?"), name)
        try:
            guest.name = name
            break
        except ValueError, e:
            print "ERROR: ", e
            name = None

def get_memory(memory, guest):
    while 1:
        try:
            memory = int(prompt_for_input(_("How much RAM should be allocated (in megabytes)?"), memory))
            if memory < MIN_RAM:
                print _("ERROR: Installs currently require %d megs of RAM.") %(MIN_RAM,)
                print ""
                memory = None
                continue
            guest.memory = memory
            break
        except ValueError, e:
            print _("ERROR: "), e
            memory = None

def get_uuid(uuid, guest):
    if uuid:
        try:
            guest.uuid = uuid
        except ValueError, e:
            print _("ERROR: "), e
            sys.exit(1)

def get_vcpus(vcpus, check_cpu, guest, conn):
    while 1:
        if check_cpu is None:
            break
        hostinfo = conn.getInfo()
        cpu_num = hostinfo[4] * hostinfo[5] * hostinfo[6] * hostinfo[7]
        if vcpus <= cpu_num:
            break
        res = prompt_for_input(_("You have asked for more virtual CPUs (%d) than there are physical CPUs (%d) on the host. This will work, but performance will be poor. Are you sure? (yes or no)") %(vcpus, cpu_num))
        try:
            if yes_or_no(res):
                break
            vcpus = int(prompt_for_input(_("How many VCPUs should be attached?")))
        except ValueError, e:
            print _("ERROR: "), e
    if vcpus:
        try:
            guest.vcpus = vcpus
        except ValueError, e:
            print _("ERROR: "), e

def get_network(mac, network, guest):
    if mac == "RANDOM":
        mac = None
    if network == "user":
        n = Guest.VirtualNetworkInterface(mac, type="user")
    elif network[0:6] == "bridge":
        n = Guest.VirtualNetworkInterface(mac, type="bridge", bridge=network[7:])
    elif network[0:7] == "network":
        n = Guest.VirtualNetworkInterface(mac, type="network", network=network[8:])
    else:
        print >> sys.stderr, _("Unknown network type ") + network
        sys.exit(1)
    guest.nics.append(n)

def digest_networks(macs, bridges, networks):
    if type(bridges) != list and bridges != None:
        bridges = [ bridges ]

    if type(macs) != list and macs != None:
        macs = [ macs ]

    if type(networks) != list and networks != None:
        networks = [ networks ]

    if bridges is not None and networks != None:
        print >> sys.stderr, _("Cannot mix both --bridge and --network arguments")
        sys.exit(1)

    # ensure we have equal length lists
    if bridges != None:
        networks = map(lambda b: "bridge:" + b, bridges)

    if networks != None:
        if macs != None:
            if len(macs) != len(networks):
                print >> sys.stderr, _("Need to pass equal numbers of networks & mac addresses")
                sys.exit(1)
        else:
            macs = [ None ] * len(networks)
    else:
        if os.getuid() == 0:
            net = util.default_network()
            networks = [net[0] + ":" + net[1]]
        else:
            networks = ["user"]
        if macs != None:
            if len(macs) > 1:
                print >> sys.stderr, _("Need to pass equal numbers of networks & mac addresses")
                sys.exit(1)
        else:
            macs = [ None ]

    return (macs, networks)

def get_graphics(vnc, vncport, nographics, sdl, keymap, guest):
    if vnc and nographics:
        raise ValueError, _("Can't do both VNC graphics and nographics")
    elif vnc and sdl:
        raise ValueError, _("Can't do both VNC graphics and SDL")
    elif sdl and nographics:
        raise ValueError, _("Can't do both SDL and nographics")
    if nographics:
        guest.graphics = False
        return
    if vnc is not None:
        guest.graphics = (True, "vnc", vncport, keymap)
        return
    if sdl is not None:
        guest.graphics = (True, "sdl")
        return
    while 1:
        res = prompt_for_input(_("Would you like to enable graphics support? (yes or no)"))
        try:
            vnc = yes_or_no(res)
        except ValueError, e:
            print _("ERROR: "), e
            continue
        if vnc:
            guest.graphics = (True, "vnc", vncport, keymap)
        else:
            guest.graphics = False
        break

### Option parsing
def check_before_store(option, opt_str, value, parser):
    if len(value) == 0:
        raise OptionValueError, _("%s option requires an argument") %opt_str
    setattr(parser.values, option.dest, value)

def check_before_append(option, opt_str, value, parser):
    if len(value) == 0:
        raise OptionValueError, _("%s option requires an argument") %opt_str
    parser.values.ensure_value(option.dest, []).append(value)

