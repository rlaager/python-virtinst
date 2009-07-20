#
# Copyright(c) FUJITSU Limited 2007.
#
# Cloning a virtual machine module.
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
"""
Module for cloning an existing virtual machine

General workflow for cloning:

    - Instantiate CloneDesign. Requires at least a libvirt connection and
      either the name of an existing domain to clone (original_guest), or
      a string of libvirt xml representing the guest to clone
      (original_guest_xml)

    - Run 'setup' from the CloneDesign instance to prep for cloning

    - Run 'CloneManager.start_duplicate', passing the CloneDesign instance
"""

import logging
import re

import libxml2
import urlgrabber.progress as progress
import libvirt

import Guest
from VirtualNetworkInterface import VirtualNetworkInterface
from VirtualDisk import VirtualDisk
from virtinst import Storage
from virtinst import _virtinst as _
import _util

def _listify(val):
    """
    Return (was_val_a_list, listified_val)
    """
    if type(val) is list:
        return True, val
    else:
        return False, [val]

def generate_clone_disk_path(origpath, design):
    basename = origpath
    suffix = ""

    # Try to split the suffix off the existing disk name. Ex.
    # foobar.img -> foobar-clone.img
    #
    # If the suffix is greater than 7 characters, assume it isn't
    # a file extension and is part of the disk name, at which point
    # just stick '-clone' on the end.
    if basename.count(".") and len(basename.rsplit(".", 1)[1]) <= 7:
        basename, suffix = basename.rsplit(".", 1)
        suffix = "." + suffix

    return _util.generate_name(basename + "-clone",
                               lambda p: VirtualDisk.path_exists(design.original_conn, p),
                               suffix,
                               lib_collision=False)

def generate_clone_name(design):
    # If the orig name is "foo-clone", we don't want the clone to be
    # "foo-clone-clone", we want "foo-clone1"
    basename = design.original_guest

    match = re.search("-clone[1-9]*$", basename)
    start_num = 0
    if match:
        num_match = re.search("[1-9]+$", match.group())
        if num_match:
            start_num = int(str(num_match.group()))
        basename = basename.replace(match.group(), "")

    basename = basename + "-clone"
    return _util.generate_name(basename,
                               design.original_conn.lookupByName,
                               sep="", start_num=start_num)


#
# This class is the design paper for a clone virtual machine.
#
class CloneDesign(object):

    # Reasons why we don't default to cloning.
    CLONE_POLICY_NO_READONLY   = 1
    CLONE_POLICY_NO_SHAREABLE  = 2
    CLONE_POLICY_NO_EMPTYMEDIA = 3

    def __init__(self, connection):
        # hypervisor connection
        if not isinstance(connection, libvirt.virConnect):
            raise ValueError(_("Connection must be a 'virConnect' instance."))
        self._hyper_conn = connection

        # original guest name or uuid
        self._original_guest        = None
        self._original_dom          = None
        self._original_virtual_disks = []
        self._original_xml          = None

        # clone guest
        self._clone_name         = None
        self._clone_devices      = []
        self._clone_virtual_disks = []
        self._clone_bs           = 1024*1024*10
        self._clone_mac          = []
        self._clone_uuid         = None
        self._clone_sparse       = True
        self._clone_xml          = None

        self._force_target       = []
        self._skip_target        = []
        self._preserve           = True

        # Default clone policy for back compat: don't clone readonly,
        # shareable, or empty disks
        self._clone_policy       = [self.CLONE_POLICY_NO_READONLY,
                                    self.CLONE_POLICY_NO_SHAREABLE,
                                    self.CLONE_POLICY_NO_EMPTYMEDIA]

        # Throwaway guest to use for easy validation
        self._valid_guest        = Guest.Guest(connection=connection)

        # Generate a random UUID at the start
        while 1:
            uuid = _util.uuidToString(_util.randomUUID())
            if _util.vm_uuid_collision(self._hyper_conn, uuid):
                continue
            self.clone_uuid = uuid
            break


    # Getter/Setter methods

    def get_original_guest(self):
        return self._original_guest
    def set_original_guest(self, original_guest):
        if self._lookup_vm(original_guest):
            self._original_guest = original_guest
    original_guest = property(get_original_guest, set_original_guest,
                              doc="Original guest name.")

    def set_original_xml(self, val):
        if type(val) is not str:
            raise ValueError(_("Original xml must be a string."))
        self._original_xml = val
        self._original_guest = _util.get_xml_path(self.original_xml,
                                                  "/domain/name")
    def get_original_xml(self):
        return self._original_xml
    original_xml = property(get_original_xml, set_original_xml,
                            doc="XML of the original guest.")

    def get_clone_name(self):
        return self._clone_name
    def set_clone_name(self, name):
        try:
            self._valid_guest.set_name(name)
        except ValueError, e:
            raise ValueError, _("Invalid name for new guest: %s") % (str(e),)

        # Make sure new VM name isn't taken.
        try:
            if self._hyper_conn.lookupByName(name) is not None:
                raise ValueError(_("Domain name '%s' already in use.") %
                                 name)
        except libvirt.libvirtError:
            pass

        self._clone_name = name
    clone_name = property(get_clone_name, set_clone_name,
                          doc="Name to use for the new guest clone.")

    def set_clone_uuid(self, uuid):
        try:
            self._valid_guest.set_uuid(uuid)
        except ValueError, e:
            raise ValueError, _("Invalid uuid for new guest: %s") % (str(e),)

        if _util.vm_uuid_collision(self._hyper_conn, uuid):
            raise ValueError(_("UUID '%s' is in use by another guest.") %
                             uuid)
        self._clone_uuid = uuid
    def get_clone_uuid(self):
        return self._clone_uuid
    clone_uuid = property(get_clone_uuid, set_clone_uuid,
                          doc="UUID to use for the new guest clone")

    def set_clone_devices(self, devpath):
        # Devices here is a string path. Every call to set_clone_devices
        # Adds the path (if valid) to the internal _clone_devices list

        disklist = []
        is_list, pathlist = _listify(devpath)

        # Check path is valid
        # XXX: What if disk is being preserved, and storage is readonly?
        try:
            for path in pathlist:
                device = VirtualDisk.DEVICE_DISK
                if not path:
                    device = VirtualDisk.DEVICE_CDROM

                disk = VirtualDisk(path, size=.0000001,
                                   conn=self._hyper_conn,
                                   device=device)
                disklist.append(disk)
        except Exception, e:
            raise ValueError(_("Could not use path '%s' for cloning: %s") %
                             (devpath, str(e)))

        if is_list:
            self._clone_virtual_disks = []
            self._clone_devices = []

        self._clone_virtual_disks.extend(disklist)
        self._clone_devices.extend(pathlist)
    def get_clone_devices(self):
        return self._clone_devices
    clone_devices = property(get_clone_devices, set_clone_devices,
                             doc="Paths to use for the new disk locations.")

    def get_clone_virtual_disks(self):
        return self._clone_virtual_disks
    clone_virtual_disks = property(get_clone_virtual_disks,
                                   doc="VirtualDisk instances for the new"
                                       " disk paths")

    def set_clone_mac(self, mac):
        is_list, maclist = _listify(mac)

        for m in maclist:
            VirtualNetworkInterface(m, conn=self.original_conn)

        if is_list:
            self._clone_mac = []

        self._clone_mac.extend(maclist)
    def get_clone_mac(self):
        return self._clone_mac
    clone_mac = property(get_clone_mac, set_clone_mac,
                         doc="MAC address for the new guest clone.")

    def get_clone_bs(self):
        return self._clone_bs
    def set_clone_bs(self, rate):
        self._clone_bs = rate
    clone_bs = property(get_clone_bs, set_clone_bs,
                        doc="Block size to use when cloning guest storage.")

    def get_original_devices_size(self):
        ret = []
        for disk in self.original_virtual_disks:
            ret.append(disk.size)
        return ret
    original_devices_size = property(get_original_devices_size,
                                     doc="Size of the original guest's disks."
                                         " DEPRECATED: Get this info from"
                                         " original_virtual_disks")

    def get_original_devices(self):
        ret = []
        for disk in self.original_virtual_disks:
            ret.append(disk.path)
        return ret
    original_devices = property(get_original_devices,
                                doc="Original disk paths that will be cloned. "
                                    "DEPRECATED: Get this info from "
                                    "original_virtual_disks")

    def get_original_virtual_disks(self):
        return self._original_virtual_disks
    original_virtual_disks = property(get_original_virtual_disks,
                                      doc="VirtualDisk instances of the "
                                          "original disks being cloned.")

    def get_hyper_conn(self):
        return self._hyper_conn
    def set_hyper_conn(self, conn):
        self._hyper_conn = conn
    original_conn = property(get_hyper_conn, set_hyper_conn,
                             doc="Libvirt virConnect instance we are cloning "
                                 "on")

    def get_original_dom(self):
        return self._original_dom
    original_dom = property(get_original_dom,
                            doc="Libvirt virDomain instance of the original "
                                 "guest. May not be available if cloning from "
                                 "XML.")

    def get_clone_xml(self):
        return self._clone_xml
    def set_clone_xml(self, clone_xml):
        self._clone_xml = clone_xml
    clone_xml = property(get_clone_xml, set_clone_xml,
                         doc="Generated XML for the guest clone.")

    def get_clone_sparse(self):
        return self._clone_sparse
    def set_clone_sparse(self, flg):
        self._clone_sparse = flg
    clone_sparse = property(get_clone_sparse, set_clone_sparse,
                            doc="Whether to attempt sparse allocation during "
                                "cloning.")

    def get_preserve(self):
        return self._preserve
    def set_preserve(self, flg):
        self._preserve = flg
    preserve = property(get_preserve, set_preserve,
                        doc="If true, preserve ALL original disk devices.")

    def set_force_target(self, dev):
        if type(dev) is list:
            self._force_target = dev[:]
        else:
            self._force_target.append(dev)
    def get_force_target(self):
        return self._force_target
    force_target = property(get_force_target, set_force_target,
                            doc="List of disk targets that we force cloning "
                                "despite CloneManager's recommendation.")

    def set_skip_target(self, dev):
        if type(dev) is list:
            self._skip_target = dev[:]
        else:
            self._skip_target.append(dev)
    def get_skip_target(self):
        return self._skip_target
    skip_target = property(get_skip_target, set_skip_target,
                           doc="List of disk targets that we skip cloning "
                               "despite CloneManager's recommendation. This "
                               "takes precedence over force_target.")

    def set_clone_policy(self, policy_list):
        if type(policy_list) != list:
            raise ValueError(_("Cloning policy must be a list of rules."))
        self._clone_policy = policy_list
    def get_clone_policy(self):
        return self._clone_policy
    clone_policy = property(get_clone_policy, set_clone_policy,
                            doc="List of policy rules for determining which "
                                "vm disks to clone. See CLONE_POLICY_*")

    # Functional methods

    def setup_original(self):
        """
        Validate and setup all parameters needed for the original (cloned) VM
        """
        logging.debug("Validating original guest parameters")

        if self.original_guest == None and self.original_xml == None:
            raise RuntimeError(_("Original guest name or xml is required."))

        if self.original_guest != None and not self.original_xml:
            self._original_dom = self._lookup_vm(self.original_guest)
            self.original_xml = self._original_dom.XMLDesc(0)

        # Pull clonable storage info from the original xml
        self._original_virtual_disks = self._get_original_devices_info(self._original_xml)

        logging.debug("Original paths: %s" % (self.original_devices))
        logging.debug("Original sizes: %s" % (self.original_devices_size))

        # If domain has devices to clone, it must be 'off' or 'paused'
        if self._original_dom and len(self.original_devices) != 0:
            status = self._original_dom.info()[0]

            if status not in [libvirt.VIR_DOMAIN_SHUTOFF,
                              libvirt.VIR_DOMAIN_PAUSED]:
                raise RuntimeError, _("Domain with devices to clone must be "
                                      "paused or shutoff.")


    def setup_clone(self):
        """
        Validate and set up all parameters needed for the new (clone) VM
        """
        logging.debug("Validating clone parameters.")

        self._clone_xml = self.original_xml

        # XXX: Make sure a clone name has been specified? or generate one?

        logging.debug("Clone paths: %s" % (self._clone_devices))

        # We simply edit the original VM xml in place
        doc = libxml2.parseDoc(self._clone_xml)
        ctx = doc.xpathNewContext()
        typ = ctx.xpathEval("/domain")[0].prop("type")

        # changing name
        node = ctx.xpathEval("/domain/name")
        node[0].setContent(self._clone_name)

        # We always have a UUID since one is generated at init time
        node = ctx.xpathEval("/domain/uuid")
        node[0].setContent(self._clone_uuid)

        # changing mac
        count = ctx.xpathEval("count(/domain/devices/interface/mac)")
        for i in range(1, int(count+1)):
            node = ctx.xpathEval("/domain/devices/interface[%d]/mac/@address" % i)
            try:
                node[0].setContent(self._clone_mac[i-1])
            except Exception:
                while 1:
                    mac = _util.randomMAC(typ)
                    dummy, msg = self._check_mac(mac)
                    if msg is not None:
                        continue
                    else:
                        break
                node[0].setContent(mac)

        if len(self.clone_virtual_disks) < len(self.original_virtual_disks):
            raise ValueError(_("More disks to clone that new paths specified. "
                               "(%(passed)d specified, %(need)d needed") %
                               {"passed" : len(self.clone_virtual_disks),
                                "need"   : len(self.original_virtual_disks) })

        # Changing storage XML
        for i in range(0, len(self.original_virtual_disks)):
            orig_disk = self._original_virtual_disks[i]
            clone_disk = self._clone_virtual_disks[i]

            self._change_storage_xml(ctx, orig_disk, clone_disk)

            # Sync 'size' between the two
            if orig_disk.size:
                clone_disk.size = orig_disk.size

            # Setup proper cloning inputs for the new virtual disks
            if orig_disk.vol_object and clone_disk.vol_install:
                # Source and dest are managed. If they share the same pool,
                # replace vol_install with a CloneVolume instance, otherwise
                # simply set input_vol on the dest vol_install
                if (clone_disk.vol_install.pool.name() ==
                    orig_disk.vol_object.storagePoolLookupByVolume().name()):
                    newname = clone_disk.vol_install.name
                    clone_disk.vol_install = Storage.CloneVolume(newname, orig_disk.vol_object)
                else:
                    clone_disk.vol_install.input_vol = orig_disk.vol_object

            else:
                clone_disk.clone_path = orig_disk.path

        # Save altered clone xml
        self._clone_xml = str(doc)

        ctx.xpathFreeContext()
        doc.freeDoc()

    def setup(self):
        """
        Helper function that wraps setup_original and setup_clone, with
        additional debug logging.
        """
        self.setup_original()
        logging.debug("Original guest xml is\n%s" % (self._original_xml))

        self.setup_clone()
        logging.debug("Clone guest xml is\n%s" % (self._clone_xml))


    # Private helper functions

    # Check if new mac address is valid
    def _check_mac(self, mac):
        nic = VirtualNetworkInterface(macaddr=mac, conn=self.original_conn)
        return nic.is_conflict_net(self._hyper_conn)

    def _change_storage_xml(self, ctx, orig_disk, clone_disk):
        """
        Swap the original disk path out for the clone disk path in the
        passed XML context
        """
        base_path   = ("/domain/devices/disk[target/@dev='%s']" %
                       orig_disk.target)
        disk        = ctx.xpathEval(base_path)[0]
        driver      = ctx.xpathEval(base_path + "/driver")
        disk_type   = ctx.xpathEval(base_path + "/@type")
        source_node = ctx.xpathEval(base_path + "/source")
        source_node = source_node and source_node[0]

        # If no destination path, our job is easy
        if not clone_disk.path:
            if source_node:
                source_node.unlinkNode()
                source_node.freeNode()
            return

        if not source_node:
            # No original source, but new path specified: create <source> tag
            source_node = disk.newChild(None, "source", None)
        else:
            source_node.get_properties().unlinkNode()

        # Change disk type/driver
        if clone_disk.type == clone_disk.TYPE_FILE:
            dtype, prop, drvval = ("file", "file", "file")
        else:
            dtype, prop, drvval = ("block", "dev", "phy")

        # Only change these type/driver values if they are in our minimal
        # known whitelist, to try and avoid future problems
        if disk_type[0].getContent() in [ "file", "block" ]:
            disk_type[0].setContent(dtype)
        if driver and driver[0].prop("name") in [ "file", "block" ]:
            driver[0].setProp("name", drvval)

        source_node.setProp(prop, clone_disk.path)

    # Parse disk paths that need to be cloned from the original guest's xml
    # Return a tuple of lists:
    # ([list of VirtualDisk instances of the source paths to clone]
    #  [indices in the original xml of those disks])
    def _get_original_devices_info(self, xml):

        disks   = []
        lst     = []

        count = _util.get_xml_path(xml, "count(/domain/devices/disk)")
        for i in range(1, int(count+1)):
            # Check if the disk needs cloning
            (path, target) = self._do_we_clone_device(xml, i)
            if target == None:
                continue
            lst.append((path, target))

        # Set up virtual disk to encapsulate all relevant path info
        for path, target in lst:
            d = None
            try:
                if (path and
                    not VirtualDisk.path_exists(self._hyper_conn, path)):
                    raise ValueError(_("Disk '%s' does not exist.") %
                                     path)

                device = VirtualDisk.DEVICE_DISK
                if not path:
                    # Tell VirtualDisk we are a cdrom to allow empty media
                    device = VirtualDisk.DEVICE_CDROM

                d = VirtualDisk(path, conn=self._hyper_conn, device=device)
                d.target = target
            except Exception, e:
                raise ValueError(_("Could not determine original disk "
                                   "information: %s" % str(e)))
            disks.append(d)

        return disks

    # Pull disk #i from the original guest xml, return it's source path
    # if it should be cloned
    # Cloning policy based on 'clone_policy', 'force_target' and 'skip_target'
    def _do_we_clone_device(self, xml, i):
        base_path = "/domain/devices/disk[%d]" % i
        source  = _util.get_xml_path(xml, "%s/source/@dev | %s/source/@file" %
                                     (base_path, base_path))
        target  = _util.get_xml_path(xml, base_path + "/target/@dev")
        ro      = _util.get_xml_path(xml, "count(%s/readonly)" % base_path)
        share   = _util.get_xml_path(xml, "count(%s/shareable)" % base_path)

        if not target:
            raise ValueError("XML has no 'dev' attribute in disk target")

        if target in self.skip_target:
            return (None, None)

        if target in self.force_target:
            return (source, target)

        # No media path
        if not source and self.CLONE_POLICY_NO_EMPTYMEDIA in self.clone_policy:
            return (None, None)

        # Readonly disks
        if ro and self.CLONE_POLICY_NO_READONLY in self.clone_policy:
            return (None, None)

        # Shareable disks
        if share and self.CLONE_POLICY_NO_SHAREABLE in self.clone_policy:
            return (None, None)

        return (source, target)

    # Simple wrapper for checking a vm exists and returning the domain
    def _lookup_vm(self, name):
        try:
            return self._hyper_conn.lookupByName(name)
        except libvirt.libvirtError:
            raise ValueError(_("Domain '%s' was not found.") % str(name))


def start_duplicate(design, meter=None):
    """
    Actually perform the duplication: cloning disks if needed and defining
    the new clone xml.
    """

    logging.debug("Starting duplicate.")

    if not meter:
        meter = progress.BaseMeter()

    dom = None
    try:
        # Define domain first so we can catch any xml errors before duplicating
        # storage
        dom = design.original_conn.defineXML(design.clone_xml)

        if design.preserve == True:
            _do_duplicate(design, meter)

    except Exception, e:
        logging.debug("Duplicate failed: %s" % str(e))
        if dom:
            dom.undefine()
        raise

    logging.debug("Duplicating finished.")

# Iterate over the list of disks, and clone them using the appropriate
# clone method
def _do_duplicate(design, meter):

    # Now actually do the cloning
    for dst_dev in design.clone_virtual_disks:
        if dst_dev.clone_path == "/dev/null":
            # Not really sure why this check was here, but keeping for compat
            logging.debug("Source dev was /dev/null. Skipping")
            continue
        elif dst_dev.clone_path == dst_dev.path:
            logging.debug("Source and destination are the same. Skipping.")
            continue

        # VirtualDisk.setup handles everything
        dst_dev.setup(meter)

