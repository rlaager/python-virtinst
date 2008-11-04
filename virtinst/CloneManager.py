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

import os
import stat
import libxml2
import logging
import urlgrabber.progress as progress
import util
import commands
import libvirt
import Guest
from VirtualDisk import VirtualDisk
from virtinst import _virtinst as _

#
# This class is the design paper for a clone virtual machine.
#
class CloneDesign(object):

    def __init__(self,connection):
        # hypervisor connection
        self._hyper_conn = connection

        # original guest name or uuid 
        self._original_guest        = None
        self._original_dom          = None
        self._original_devices      = []
        self._original_devices_size = []
        self._original_devices_type = []
        self._original_xml          = None

        # clone guest 
        self._clone_name         = None
        self._clone_devices      = []
        self._clone_devices_size = []
        self._clone_devices_type = []
        self._clone_bs           = 1024*1024*10
        self._clone_mac          = []
        self._clone_uuid         = None
        self._clone_sparse       = True
        self._clone_xml          = None

        self._force_target       = []

        self._preserve           = True

        # Throwaway guest to use for easy validation
        self._valid_guest        = Guest.Guest(connection=connection)

    def get_original_guest(self):
        return self._original_guest
    def set_original_guest(self, original_guest):
        if type(original_guest) is not type("str") or len(original_guest)==0:
           raise ValueError, _("Name or UUID of guest to clone is required")

        try:
            self._valid_guest.set_uuid(original_guest)
        except ValueError:
            try:
                self._valid_guest.set_name(original_guest)
            except ValueError:
                raise ValueError, \
                    _("A valid name or UUID of guest to clone is required")
        self._original_guest = original_guest
    original_guest = property(get_original_guest, set_original_guest)

    def get_clone_name(self):
        return self._clone_name
    def set_clone_name(self, name):
        try:
            self._valid_guest.set_name(name)
        except ValueError, e:
            raise ValueError, _("Invalid name for new guest: %s") % (str(e),)
        self._clone_name = name
    clone_name = property(get_clone_name, set_clone_name)

    def set_clone_uuid(self, uuid):
        try:
            self._valid_guest.set_uuid(uuid)
        except ValueError, e:
            raise ValueError, _("Invalid uuid for new guest: %s") % (str(e),)
        self._clone_uuid = uuid
    def get_clone_uuid(self):
        return self._clone_uuid
    clone_uuid = property(get_clone_uuid, set_clone_uuid)

    def set_clone_devices(self, devices):
        if len(devices) == 0:
            raise ValueError, _("New file to use for disk image is required")
        cdev      = []
        cdev_size = []
        cdev.append(devices)
        cdev_size, dummy = self._get_clone_devices_info(cdev)
        devices = self._check_file(self._hyper_conn, devices, cdev_size[0])
        self._clone_devices.append(devices)
    def get_clone_devices(self):
        return self._clone_devices
    clone_devices = property(get_clone_devices, set_clone_devices)

    def set_clone_mac(self, mac):
        Guest.VirtualNetworkInterface(mac, conn=self.original_conn)
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
        return self._original_devices_size
    original_devices_size = property(get_original_devices_size)

    def get_original_devices(self):
        return self._original_devices
    original_devices = property(get_original_devices)

    def get_hyper_conn(self):
        return self._hyper_conn
    original_conn = property(get_hyper_conn)

    def get_original_dom(self):
        return self._original_dom
    original_dom = property(get_original_dom)

    def get_original_xml(self):
        return self._original_xml
    original_xml = property(get_original_xml)

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

    #
    # setup original guest
    #
    def setup_original(self):
        logging.debug("setup_original in")
        try:
            self._original_dom = self._hyper_conn.lookupByName(self._original_guest)
        except libvirt.libvirtError:
            raise RuntimeError, _("Domain %s is not found") % self._original_guest

        #
        # store the xml as same as original xml still setup_clone_xml
        #
        self._original_xml = self._original_dom.XMLDesc(0)
        self._clone_xml    = self._original_dom.XMLDesc(0)
        self._original_devices,     \
        self._original_devices_size,\
        self._original_devices_type = self._get_original_devices_info(self._original_xml)

        #
        # check status. Firt, shut off domain is available.
        #
        status = self._original_dom.info()[0]
        logging.debug("original guest status: %s" % (status))
        if status != libvirt.VIR_DOMAIN_SHUTOFF:
            raise RuntimeError, _("Domain status must be SHUTOFF")

        #
        # check existing
        #
        try:
            if self._hyper_conn.lookupByName(self._clone_name) is not None:
                raise RuntimeError, _("Domain %s already exists") % self._clone_name
        except libvirt.libvirtError:
            pass

        #
        # check used uuid
        # random uuid check is done in start_duplicate function
        #
        if self._check_uuid(self._clone_uuid) == True:
            raise RuntimeError, _("The UUID you entered is already in use by another guest!")

        #
        # check used mac
        #
        for i in self._clone_mac:
            ret, msg = self._check_mac(i)
            if msg is not None:
                if ret:
                    raise RuntimeError, msg
                else:
                    logging.warning(msg)

        logging.debug("setup_original out")

    #
    # setup clone XML
    #
    def setup_clone(self):
        logging.debug("setup_clone in")

        self._clone_devices_size,\
        self._clone_devices_type = self._get_clone_devices_info(self._clone_devices)

        doc = libxml2.parseDoc(self._clone_xml)
        ctx = doc.xpathNewContext()
        type = ctx.xpathEval("/domain")[0].prop("type")

        # changing name
        node = ctx.xpathEval("/domain/name")
        node[0].setContent(self._clone_name)

        # changing devices
        clone_devices = iter(self._clone_devices)
        count = ctx.xpathEval("count(/domain/devices/disk)")
        for i in range(1, int(count+1)):
            node = self._get_available_cloning_device(ctx, i, self._force_target)
            if node == None:
                continue
            node = node[0].get_properties()
            try:
                node.setContent(clone_devices.next())
            except Exception:
                raise ValueError, _("Missing new file to use disk image for %s") % node.getContent()

        # changing uuid
        node = ctx.xpathEval("/domain/uuid")
        if self._clone_uuid is not None:
            node[0].setContent(self._clone_uuid)
        else:
            while 1:
                uuid = util.uuidToString(util.randomUUID())
                if self._check_uuid(uuid) == True:
                    continue
                else:
                    break
            node[0].setContent(uuid)

        # changing mac
        count = ctx.xpathEval("count(/domain/devices/interface/mac)")
        for i in range(1, int(count+1)):
            node = ctx.xpathEval("/domain/devices/interface[%d]/mac/@address" % i)
            try:
                node[0].setContent(self._clone_mac[i-1])
            except Exception:
                while 1:
                    mac = util.randomMAC(type)
                    dummy, msg = self._check_mac(mac)
                    if msg is not None:
                        continue
                    else:
                        break
                node[0].setContent(mac)

        # change disk type
        self._change_disk_type(self._original_devices_type, self._clone_devices_type, ctx)

        # set clone xml
        self._clone_xml = str(doc)

        ctx.xpathFreeContext()
        doc.freeDoc()
        logging.debug("setup_clone out")

    #
    # setup
    #
    def setup(self):
        self.setup_original()
        logging.debug("original guest is\n%s" % (self._original_xml))

        self.setup_clone()
        logging.debug("cloning guest is\n%s" % (self._clone_xml))
  
    #
    # check used uuid func
    # False : OK
    # True  : NG existing
    #
    def _check_uuid(self, uuid):
        check = False
        if uuid is not None:
            try:
                if self._hyper_conn.lookupByUUIDString(uuid) is not None:
                    check = True
                else:
                    pass
            except libvirt.libvirtError:
                pass
        return check

    #
    # check used file func
    # ret : Use File Path
    #
    def _check_file(self, conn, disk, size):
        d = VirtualDisk(disk, size)
        return d.path

    #
    # check used mac func
    #
    def _check_mac(self, mac):
        nic = Guest.VirtualNetworkInterface(macaddr=mac,
                                            conn=self.original_conn)
        return nic.is_conflict_net(self._hyper_conn)

    #
    # get count macaddr
    #
    def _count_mac(self, vms, mac):
        count = 0
        for vm in vms:
            doc = None
            try:
                doc = libxml2.parseDoc(vm.XMLDesc(0))
            except:
                continue
            ctx = doc.xpathNewContext()
            mac_index = (str(doc).upper()).find(mac.upper())
            if mac_index == -1:
                continue
            mac_comp = str(doc)[mac_index:mac_index+17]
            try:
                try:
                    count += ctx.xpathEval("count(/domain/devices/interface/mac[@address='%s'])"
                                           % mac_comp)
                except:
                    continue
            finally:
                if ctx is not None:
                    ctx.xpathFreeContext()
                if doc is not None:
                    doc.freeDoc()
        return count

    #
    # get the original devices information 
    #
    def _get_original_devices_info(self, xml):

        list = []
        size = []
        type = []

        doc = libxml2.parseDoc(xml)
        ctx = doc.xpathNewContext()
        try:
            count = ctx.xpathEval("count(/domain/devices/disk)")
            for i in range(1, int(count+1)):
                node = self._get_available_cloning_device(ctx, i, self._force_target)
                if node == None:
                    continue
                list.append(node[0].get_properties().getContent())
        finally:
            if ctx is not None:
                ctx.xpathFreeContext()
            if doc is not None:
                doc.freeDoc()
        logging.debug("original device list: %s" % (list))

        for i in list:
            mode = os.stat(i)[stat.ST_MODE]
            if stat.S_ISBLK(mode):
                dummy, str = commands.getstatusoutput('fdisk -s %s' % i)
                # check
                if str.isdigit() == False:
                    lines = str.splitlines()
                    # retry eg. for the GPT disk
                    str = lines[len(lines)-1]
                size.append(int(str) * 1024)
                type.append(False)
            elif stat.S_ISREG(mode):
                size.append(os.path.getsize(i))
                type.append(True)
        logging.debug("original device size: %s" % (size))
        logging.debug("original device type: %s" % (type))

        return (list, size, type)

    #
    # get available original device for clone
    #
    def _get_available_cloning_device(self, ctx, i, force):

        node = None
        force_flg = False
        
        node = ctx.xpathEval("/domain/devices/disk[%d]/source" % i)
        if len(node) == 0:
            return None

        target = ctx.xpathEval("/domain/devices/disk[%d]/target/@dev" % i)
        target = target[0].getContent()

        for f_target in force:
            if target == f_target:
                force_flg = True

        ro = ctx.xpathEval("/domain/devices/disk[%d]/readonly" % i)
        if len(ro) != 0 and force_flg == False:
            return None
        share = ctx.xpathEval("/domain/devices/disk[%d]/shareable" % i) 
        if len(share) != 0 and force_flg == False:
            return None

        return node 

    #
    # get the clone devices information
    #
    def _get_clone_devices_info(self, cln_dev_lst):

        size = []
        type = []

        for i in cln_dev_lst:
            if os.path.exists(i) ==  False:
               size.append(0)
               # if not exists, create file necessary
               type.append(True)
               continue
            mode = os.stat(i)[stat.ST_MODE]
            if stat.S_ISBLK(mode):
                dummy, str = commands.getstatusoutput('fdisk -s %s' % i)
                # check
                if str.isdigit() == False:
                    lines = str.splitlines()
                    # retry eg. for the GPT disk
                    str = lines[len(lines)-1]
                size.append(int(str) * 1024)
                type.append(False)
            elif stat.S_ISREG(mode):
                size.append(os.path.getsize(i))
                type.append(True)

        logging.debug("clone device list: %s" % (cln_dev_lst))
        logging.debug("clone device size: %s" % (size))
        logging.debug("clone device type: %s" % (type))

        return (size, type)

    #
    # change disk type in XML
    #
    def _change_disk_type(self, org_type, cln_type, ctx):
        for i in range(len(org_type)):
            disk_type = ctx.xpathEval("/domain/devices/disk[%d]/@type" % (i+1))
            driv_name = ctx.xpathEval("/domain/devices/disk[%d]/driver/@name" % (i+1))

            src = ctx.xpathEval("/domain/devices/disk[%d]/source" % (i+1))
            src_chid_txt = src[0].get_properties().getContent()

            # different type
            if org_type[i] != cln_type[i]:
                # changing from file to disk
                if org_type[i] == True:
                    disk_type[0].setContent("block")
                    driv_name[0].setContent("phy")
                    src[0].get_properties().unlinkNode()
                    src[0].newProp("dev", src_chid_txt)
                # changing from disk to file
                else:
                    disk_type[0].setContent("file")
                    driv_name[0].setContent("file")
                    src[0].get_properties().unlinkNode()
                    src[0].newProp("file", src_chid_txt)

#
# start duplicate
# this function clones the virtual machine according to the ClonDesign object
#
def start_duplicate(design):

    logging.debug("start_duplicate in")

    # do dupulicate
    # at this point, handling the cloning way.
    if design.preserve == True:
        _do_duplicate(design)

    # define clone xml
    design.original_conn.defineXML(design.clone_xml)

    logging.debug("start_duplicate out")

#
# Now this Cloning method is reading and writing devices.
# For future, there are many cloning methods (e.g. fork snapshot cmd).
#
def _do_duplicate(design):

    src_fd = None
    dst_fd = None
    dst_dev_iter = iter(design.clone_devices)
    dst_siz_iter = iter(design.original_devices_size)

    zeros            = '\0' * 4096
    sparse_copy_mode = False

    try:
        for src_dev in design.original_devices: 
            dst_dev = dst_dev_iter.next()
            dst_siz = dst_siz_iter.next()

            size = dst_siz
            meter = progress.TextMeter()
            print _("Cloning from %(src)s to %(dst)s") % {'src' : src_dev, \
                                                       'dst' : dst_dev}
            meter.start(size=size, text=_("Cloning domain..."))

            # skip
            if src_dev == "/dev/null" or src_dev == dst_dev:
                meter.end(size)
                continue
            #
            # create sparse file
            # if a destination file exists and sparse flg is True,
            # this priority takes a existing file.
            #
            if os.path.exists(dst_dev) == False and design.clone_sparse == True:
                design.clone_bs = 4096
                sparse_copy_mode = True
                fd = os.open(dst_dev, os.O_WRONLY | os.O_CREAT)
                os.lseek(fd, dst_siz, 0)
                os.write(fd, '\x00')
                os.close(fd)
            else:
                design.clone_bs = 1024*1024*10
                sparse_copy_mode = False
            logging.debug("dst_dev:%s sparse_copy_mode:%s bs:%d" % (dst_dev,sparse_copy_mode,design.clone_bs))

            src_fd = os.open(src_dev, os.O_RDONLY)
            dst_fd = os.open(dst_dev, os.O_WRONLY | os.O_CREAT)

            i=0
            while 1:
                l = os.read(src_fd, design.clone_bs)
                s = len(l)
                if s == 0:
                    meter.end(size)
                    break
                # check sequence of zeros
                if sparse_copy_mode == True and zeros == l:
                    os.lseek(dst_fd, s, 1)
                else:
                    b = os.write(dst_fd, l)
                    if s != b:
                        meter.end(i)
                        break
                i += s
                if i < size:
                    meter.update(i)

            os.close(src_fd)
            src_fd = None
            os.close(dst_fd)
            dst_fd = None
    finally:
        if src_fd is not None:
           os.close(src_fd)
        if dst_fd is not None:
           os.close(dst_fd)

