#!/usr/bin/python -tt
#
# Script to set up a Xen guest and kick off an install
#
# Copyright 2005-2006  Red Hat, Inc.
# Jeremy Katz <katzj@redhat.com>
# Option handling added by Andrew Puch <apuch@redhat.com>
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.


import os, sys, string
from optparse import OptionParser
import xeninst

MIN_RAM = 256

### Utility functions
def yes_or_no(s):
    s = s.lower()
    if s in ("y", "yes", "1", "true", "t"):
        return True
    elif s in ("n", "no", "0", "false", "f"):
        return False
    raise ValueError, "A yes or no response is required" 

def prompt_for_input(prompt = "", val = None):
    if val is not None:
        return val
    print prompt, " ", 
    return sys.stdin.readline().strip()


def check_xen():
    if not os.path.isdir("/proc/xen") and 0:
        print >> sys.stderr, "Can only install guests if running under a Xen kernel!"
        sys.exit(1)


### General input gathering functions
def get_full_virt():
    while 1:
        res = prompt_for_input("Would you like a fully virtualized guest (yes or no)?  This will allow you to run unmodified operating systems.")
        try:
            return yes_or_no(res)
        except ValueError, e:
            print "ERROR: ", e

def get_name(name, guest):
    while 1:
    	name = prompt_for_input("What is the name of your virtual machine?", name)
        try:
            guest.name = name
            break
        except ValueError, e:
            print "ERROR: ", e            
            name = None

def get_memory(memory, guest):
    while 1:
    	memory = prompt_for_input("How much RAM should be allocated (in megabytes)?", memory)
        if memory < MIN_RAM:
            print "ERROR: Installs currently require %d megs of RAM." %(MIN_RAM,)
            print ""
            continue
        try:
            guest.memory = memory
            break
        except ValueError:
            print "ERROR: ", e
            memory = None

def get_uuid(uuid, guest):
    if uuid: 
        try:
            guest.uuid = uuid
        except ValueError, e:
            print "ERROR: ", e

def get_disks(disk, size, guest):
    # FIXME: need to handle a list of disks at some point
    while 1:
        disk = prompt_for_input("What would you like to use as the disk (path)?", disk)
        while 1:
            if os.path.exists(disk):
                break
            size = prompt_for_input("How large would you like the disk to be (in gigabytes)?", size)
            try:
                size = float(size)
                break
            except Exception, e:
                print "ERROR: ", e
                size = None

        try:
            d = xeninst.XenDisk(disk, size)
        except ValueError, e:
            print "ERROR: ", e
            disk = size = None
            continue

        guest.disks.append(d)
        break

def get_network(mac, bridge, guest):
    # FIXME: need to handle multiple network interfaces at some point
    if bridge is not None: 
        n = xeninst.XenNetworkInterface(mac, bridge)
    else:
        n = xeninst.XenNetworkInterface(mac)
    guest.nics.append(n)


### Paravirt input gathering functions
def get_paravirt_install(src, guest):
    while 1:
    	src = prompt_for_input("What is the install location?", src)
        try:
            guest.location = src
            break
        except ValueError, e:
            print "ERROR: ", e
            src = None

def get_paravirt_extraargs(extra, guest):
    guest.extra = extra


### fullvirt input gathering functions
def get_fullvirt_cdrom(cdpath, guest):
    while 1:
    	cdpath = prompt_for_input("What would you like to use for the virtual CD image?", cdpath)
        try:
            guest.cdrom = cdpath
            break
        except ValueError, e:
            print "ERROR: ", e
            cdpath = None


### Option parsing
def parse_args():
    parser = OptionParser()
    parser.add_option("-n", "--name", type="string", dest="name",
                      help="Name of the guest instance")
    parser.add_option("-r", "--ram", type="int", dest="memory",
                      help="Memory to allocate for guest instance in megabytes")
    parser.add_option("-u", "--uuid", type="string", dest="uuid",
                      help="UUID for the guest; if none is given a random UUID will be generated")

    # disk options
    parser.add_option("-f", "--file", type="string", dest="diskfile",
                      help="File to use as the disk image")
    parser.add_option("-s", "--file-size", type="float", dest="disksize",
                      help="Size of the disk image (if it doesn't exist) in gigabytes")
    
    # network options
    parser.add_option("-m", "--mac", type="string", dest="mac",
                      help="Fixed MAC address for the guest; if none is given a random address will be used")
    parser.add_option("-b", "--bridge", type="string", dest="bridge",
		      help="Bridge to connect guest NIC to, if none specified, the default (xenbr0) is used")
    
    
    # vmx/svm options
    if xeninst.util.is_hvm_capable():
        parser.add_option("-v", "--hvm", action="store_true", dest="fullvirt",
                          help="This guest should be a fully virtualized guest")
        parser.add_option("-c", "--cdrom", type="string", dest="cdrom",
                          help="File to use a virtual CD-ROM device for fully virtualized guests")

    # paravirt options
    parser.add_option("-p", "--paravirt", action="store_false", dest="fullvirt",
                      help="This guest should be a paravirtualized guest")
    parser.add_option("-l", "--location", type="string", dest="location",
                      help="Installation source for paravirtualized guest (eg, nfs:host:/path, http://host/path, ftp://host/path)")
    parser.add_option("-x", "--extra-args", type="string",
                      dest="extra", default="",
                      help="Additional arguments to pass to the installer with paravirt guests")


    (options,args) = parser.parse_args()
    return options


### Let's do it!
def main():
    options = parse_args()

    # check to ensure we're really on a xen kernel
    check_xen()

    # first things first, are we trying to create a fully virt guest?
    hvm = False
    if xeninst.util.is_hvm_capable():
        hvm = options.fullvirt
    if hvm is None:
        hvm = get_full_virt()
    if hvm:
        guest = xeninst.FullVirtGuest()
    else:
        guest = xeninst.ParaVirtGuest()

    # now let's get some of the common questions out of the way
    get_name(options.name, guest)
    get_memory(options.memory, guest)
    get_uuid(options.uuid, guest)

    # set up disks
    get_disks(options.diskfile, options.disksize, guest)

    # set up network information
    get_network(options.mac, options.bridge, guest)

    # and now for the full-virt vs paravirt specific questions
    if not hvm: # paravirt
        get_paravirt_install(options.location, guest)
        get_paravirt_extraargs(options.extra, guest)
    else:
        get_fullvirt_cdrom(options.cdrom, guest)

    # we've got everything -- try to start the install
    try:
        print "\n\nStarting install..."
        r = guest.start_install(True)
        print r
    except RuntimeError, e:
        print >> sys.stderr, "ERROR: ", e
        sys.exit(1)


if __name__ == "__main__":
    main()
