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

import os
import libxml2
import logging
import subprocess
import urlgrabber.progress as progress
import _util
import libvirt
import Guest
from VirtualNetworkInterface import VirtualNetworkInterface
from VirtualDisk import VirtualDisk
from virtinst import _virtinst as _

#
# This class is the design paper for a clone virtual machine.
#
class CloneDesign(object):

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

        # Deliberately private: user doesn't need to know this
        self._original_devices_idx = []

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

        self._preserve           = True

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
    original_guest = property(get_original_guest, set_original_guest)

    def set_original_xml(self, val):
        if type(val) is not str:
            raise ValueError(_("Original xml must be a string."))
        self._original_xml = val
    def get_original_xml(self):
        return self._original_xml
    original_xml = property(get_original_xml, set_original_xml)

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
    clone_name = property(get_clone_name, set_clone_name)

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
    clone_uuid = property(get_clone_uuid, set_clone_uuid)

    def set_clone_devices(self, devpath):
        # Devices here is a string path. Every call to set_clone_devices
        # Adds the path (if valid) to the internal _clone_devices list

        # Check path is valid
        try:
            disk = VirtualDisk(devpath, size=.0000001, conn=self._hyper_conn)
        except Exception, e:
            raise ValueError(_("Could not use path '%s' for cloning: %s") %
                             (devpath, str(e)))

        self._clone_virtual_disks.append(disk)
        self._clone_devices.append(devpath)
    def get_clone_devices(self):
        return self._clone_devices
    clone_devices = property(get_clone_devices, set_clone_devices)

    def get_clone_virtual_disks(self):
        return self._clone_virtual_disks
    clone_virtual_disks = property(get_clone_virtual_disks)

    def set_clone_mac(self, mac):
        VirtualNetworkInterface(mac, conn=self.original_conn)
        self._clone_mac.append(mac)
    def get_clone_mac(self):
        return self._clone_mac
    clone_mac = property(get_clone_mac, set_clone_mac)

    def get_clone_bs(self):
        return self._clone_bs
    def set_clone_bs(self, rate):
        self._clone_bs = rate
    clone_bs = property(get_clone_bs, set_clone_bs)

    def get_original_devices_size(self):
        ret = []
        for disk in self.original_virtual_disks:
            ret.append(disk.size)
        return ret
    original_devices_size = property(get_original_devices_size)

    def get_original_devices(self):
        ret = []
        for disk in self.original_virtual_disks:
            ret.append(disk.path)
        return ret
    original_devices = property(get_original_devices)

    def get_original_virtual_disks(self):
        return self._original_virtual_disks
    original_virtual_disks = property(get_original_virtual_disks)

    def get_hyper_conn(self):
        return self._hyper_conn
    original_conn = property(get_hyper_conn)

    def get_original_dom(self):
        return self._original_dom
    original_dom = property(get_original_dom)

    def get_clone_xml(self):
        return self._clone_xml
    def set_clone_xml(self, clone_xml):
        self._clone_xml = clone_xml
    clone_xml = property(get_clone_xml, set_clone_xml)

    def get_clone_sparse(self):
        return self._clone_sparse
    def set_clone_sparse(self, flg):
        self._clone_sparse = flg
    clone_sparse = property(get_clone_sparse, set_clone_sparse)

    def get_preserve(self):
        return self._preserve
    def set_preserve(self, flg):
        self._preserve = flg
    preserve = property(get_preserve, set_preserve)

    def set_force_target(self, dev):
        self._force_target.append(dev)
    def get_force_target(self):
        return self._force_target
    force_target = property(set_force_target)


    # Functional methods

    def setup_original(self):
        """
        Validate and setup all parameters needed for the original (cloned) VM
        """
        logging.debug("Validating original guest parameters")

        if self.original_guest == None and self.original_xml == None:
            raise RuntimeError(_("Original guest name or xml is required."))

        if self.original_guest != None:
            self._original_dom = self._lookup_vm(self.original_guest)
            self.original_xml = self._original_dom.XMLDesc(0)

        # Pull clonable storage info from the original xml
        self._original_virtual_disks, \
        self._original_devices_idx = self._get_original_devices_info(self._original_xml)

        logging.debug("Original paths: %s" % (self.original_devices))
        logging.debug("Original sizes: %s" % (self.original_devices_size))
        logging.debug("Original idxs: %s" % (self._original_devices_idx))

        # If there are any devices that need to be cloned and we are on
        # a remote connection, fail
        if (self.original_devices and
            _util.is_uri_remote(self.original_conn.getURI())):
            raise RuntimeError(_("Cannot clone remote VM storage."))

        # If domain has devices to clone, it must be 'off' or 'paused'
        if self._original_dom and len(self.original_devices) != 0:
            status = self._original_dom.info()[0]

            if status not in [libvirt.VIR_DOMAIN_SHUTOFF,
                              libvirt.VIR_DOMAIN_PAUSED]:
                raise RuntimeError, _("Domain with devices to clone must be "
                                      "paused or shutoff.")

        # Check mac address is not in use
        # XXX: Check this at set time?
        for i in self._clone_mac:
            ret, msg = self._check_mac(i)
            if msg is not None:
                if ret:
                    raise RuntimeError, msg
                else:
                    logging.warning(msg)


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

        # Changing storage paths
        clone_devices = iter(self._clone_devices)
        for i in self._original_devices_idx:
            node = ctx.xpathEval("/domain/devices/disk[%d]/source" % i)
            node = node[0].get_properties()
            try:
                node.setContent(clone_devices.next())
            except Exception:
                raise ValueError, _("Missing path to use as disk clone "
                                    "destination for '%s'") % node.getContent()

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

        # Change xml disk type values if original and clone disk types
        # (block/file) don't match
        for i in range(0, len(self._original_devices_idx)):
            orig_type = (self._original_virtual_disks[i].type ==
                         VirtualDisk.TYPE_FILE)
            clone_type = (self._clone_virtual_disks[i].type ==
                          VirtualDisk.TYPE_FILE)

            self._change_disk_type(orig_type, clone_type,
                                   self._original_devices_idx[i],
                                   ctx)

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

    # Parse disk paths that need to be cloned from the original guest's xml
    # Return a tuple of lists:
    # ([list of paths to clone], [size of those paths],
    #  [file/block type of those paths], [indices of disks to be cloned])
    def _get_original_devices_info(self, xml):

        disks   = []
        lst     = []
        idx_lst = []

        doc = libxml2.parseDoc(xml)
        ctx = doc.xpathNewContext()
        try:
            count = ctx.xpathEval("count(/domain/devices/disk)")
            for i in range(1, int(count+1)):
                # Check if the disk needs cloning
                node = self._get_available_cloning_device(ctx, i,
                                                          self._force_target)
                if node == None:
                    continue
                idx_lst.append(i)
                lst.append(node[0].get_properties().getContent())
        finally:
            if ctx is not None:
                ctx.xpathFreeContext()
            if doc is not None:
                doc.freeDoc()

        # Set up virtual disk to encapsulate all relevant path info
        for path in lst:
            d = None
            try:
                if not _util.disk_exists(self._hyper_conn, path):
                    raise ValueError(_("Disk '%s' does not exist.") %
                                     path)

                d = VirtualDisk(path, conn=self._hyper_conn)
            except Exception, e:
                raise ValueError(_("Could not determine original disk "
                                   "information: %s" % str(e)))
            disks.append(d)

        return (disks, idx_lst)

    # Pull disk #i from the original guest xml, return it's xml
    # if it should be cloned (skips readonly, empty, or sharable disks
    # unless its target is in the 'force' list)
    def _get_available_cloning_device(self, ctx, i, force):

        node = None
        force_flg = False

        node = ctx.xpathEval("/domain/devices/disk[%d]/source" % i)
        # If there is no media path, ignore
        if len(node) == 0:
            return None

        target = ctx.xpathEval("/domain/devices/disk[%d]/target/@dev" % i)
        if len(target) == 0:
            raise ValueError("XML has no 'dev' attribute in disk target")
        target = target[0].getContent()

        for f_target in force:
            if target == f_target:
                force_flg = True

        # Skip readonly disks unless forced
        ro = ctx.xpathEval("/domain/devices/disk[%d]/readonly" % i)
        if len(ro) != 0 and force_flg == False:
            return None
        # Skip sharable disks unless forced
        share = ctx.xpathEval("/domain/devices/disk[%d]/shareable" % i) 
        if len(share) != 0 and force_flg == False:
            return None

        return node

    # Check if original disk type (file/block) is different from
    # requested clones disk type, and alter xml if needed
    def _change_disk_type(self, org_type, cln_type, dev_idx, ctx):

        disk_type = ctx.xpathEval("/domain/devices/disk[%d]/@type" % dev_idx)
        driv_name = ctx.xpathEval("/domain/devices/disk[%d]/driver/@name" %
                                  dev_idx)
        src = ctx.xpathEval("/domain/devices/disk[%d]/source" % dev_idx)
        src_chid_txt = src[0].get_properties().getContent()

        # different type
        if org_type != cln_type:
            if org_type == True:
                # changing from file to disk
                typ, driv, newprop = ("block", "phy", "dev")
            else:
                # changing from disk to file
                typ, driv, newprop = ("file", "file", "file")

            disk_type[0].setContent(typ)
            if driv_name:
                driv_name[0].setContent(driv)
            src[0].get_properties().unlinkNode()
            src[0].newProp(newprop, src_chid_txt)


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

def _vdisk_clone(path, clone):
    logging.debug("Using vdisk clone.")

    path = os.path.expanduser(path)
    clone = os.path.expanduser(clone)
    try:
        rc = subprocess.call([ '/usr/sbin/vdiskadm', 'clone', path, clone ])
        return rc == 0
    except OSError:
        return False

# Iterate over the list of disks, and clone them using the appropriate
# clone method
def _do_duplicate(design, meter):

    IS_UNKNOWN = 0
    IS_LOCAL = 1
    IS_VDISK = 2

    dst_dev_iter = iter(design.clone_virtual_disks)

    clone_type_dict = {}

    # First loop over the devices, validate we can clone them, and
    # determine what clone operation to use
    for src_dev in design.original_virtual_disks:
        dst_dev = dst_dev_iter.next()
        src_path = src_dev.path
        dst_path = dst_dev.path

        clone_type = IS_UNKNOWN

        if (_util.is_vdisk(src_path) or
            (os.path.exists(dst_path) and _util.is_vdisk(dst_path))):

            if (not _util.is_vdisk(src_path) or
                os.path.exists(dst_path)):
                raise RuntimeError, _("copying to an existing vdisk is not"
                                      " supported")
            clone_type = IS_VDISK

        else:
            clone_type = IS_LOCAL

        if clone_type == IS_UNKNOWN:
            raise RuntimeError(_("Could not determine storage type for '%s'")
                               % src_path)
        clone_type_dict[src_path] = clone_type


    dst_dev_iter = iter(design.clone_virtual_disks)
    dst_siz_iter = iter(design.original_devices_size)

    # Now actually do the cloning
    for src_dev in design.original_virtual_disks:
        src_path = src_dev.path
        dst_dev = dst_dev_iter.next()
        dst_path = dst_dev.path
        dst_siz = int(dst_siz_iter.next() * 1024 * 1024 * 1024)

        clone_type = clone_type_dict[src_path]

        if src_path == "/dev/null":
            # Not really sure why this check was here, but keeping for compat
            logging.debug("Source dev was /dev/null. Skipping")
            continue
        elif src_path == dst_path:
            logging.debug("Source and destination are the same. Skipping.")
            continue

        meter.start(size=dst_siz,
                    text=_("Cloning %(srcfile)s") % {'srcfile' : src_path})

        if clone_type == IS_LOCAL:
            _local_clone(src_path, dst_path, dst_siz, design, meter)

        elif clone_type == IS_VDISK:
            if not _vdisk_clone(src_path, dst_path):
                raise RuntimeError, _("failed to clone disk")
            meter.end(dst_siz)


def _local_clone(src_dev, dst_dev, dst_siz, design, meter):

    # if a destination file exists and sparse flg is True,
    # this priority takes a existing file.
    if (os.path.exists(dst_dev) == False and design.clone_sparse == True):
        clone_block_size = 4096
        sparse = True
        try:
            fd = os.open(dst_dev, os.O_WRONLY | os.O_CREAT)
            os.ftruncate(fd, dst_siz)
        finally:
            os.close(fd)
    else:
        clone_block_size = 1024*1024*10
        sparse = False

    logging.debug("Local Cloning %s to %s, sparse=%s, block_size=%s" %
                  (src_dev, dst_dev, sparse, clone_block_size))

    zeros = '\0' * 4096

    try:
        src_fd = os.open(src_dev, os.O_RDONLY)
        dst_fd = os.open(dst_dev, os.O_WRONLY | os.O_CREAT)

        i=0
        while 1:
            l = os.read(src_fd, clone_block_size)
            s = len(l)
            if s == 0:
                meter.end(dst_siz)
                break
            # check sequence of zeros
            if sparse and zeros == l:
                os.lseek(dst_fd, s, 1)
            else:
                b = os.write(dst_fd, l)
                if s != b:
                    meter.end(i)
                    break
            i += s
            if i < dst_siz:
                meter.update(i)

    finally:
        if src_fd is not None:
            os.close(src_fd)
        if dst_fd is not None:
            os.close(dst_fd)
