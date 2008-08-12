#
# Classes for building disk device xml
#
# Copyright 2006-2008  Red Hat, Inc.
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

import os, stat, statvfs
import libxml2
import logging
import libvirt
import __builtin__

import util
import Storage
from VirtualDevice import VirtualDevice
from virtinst import _virtinst as _

class VirtualDisk(VirtualDevice):
    """
    Builds a libvirt domain disk xml description

    The VirtualDisk class is used for building libvirt domain xml descriptions
    for disk devices. If creating a disk object from an existing local block
    device or file, a path is all that should be required. If you want to
    create a local file, a size also needs to be specified.

    The remote case is a bit more complex. The options are:
        1. A libvirt virStorageVol instance (passed as 'volObject') for an
           existing storage volume.
        2. A virtinst L{StorageVolume} instance for creating a volume (passed
           as 'volInstall').
        3. An active connection ('conn') and a path to a storage volume on
           that connection.
        4. An active connection and a tuple of the form ("poolname",
           "volumename")

    For the last two cases, the lookup will be performed, and 'vol_object'
    will be set to the returned virStorageVol. All the above cases also
    work on a local connection as well, the only difference being that
    option 3 won't neccessarily error out if the volume isn't found.

    __init__ and setting all properties performs lots of validation,
    and will throw ValueError's if problems are found.
    """

    DRIVER_FILE = "file"
    DRIVER_PHY = "phy"
    DRIVER_TAP = "tap"
    driver_names = [DRIVER_FILE, DRIVER_PHY, DRIVER_TAP]

    DRIVER_TAP_RAW = "aio"
    DRIVER_TAP_QCOW = "qcow"
    DRIVER_TAP_VMDK = "vmdk"
    driver_types = [DRIVER_TAP_RAW, DRIVER_TAP_QCOW, DRIVER_TAP_VMDK]

    DEVICE_DISK = "disk"
    DEVICE_CDROM = "cdrom"
    DEVICE_FLOPPY = "floppy"
    devices = [DEVICE_DISK, DEVICE_CDROM, DEVICE_FLOPPY]

    TYPE_FILE = "file"
    TYPE_BLOCK = "block"
    types = [TYPE_FILE, TYPE_BLOCK]

    def __init__(self, path=None, size=None, transient=False, type=None,
                 device=DEVICE_DISK, driverName=None, driverType=None,
                 readOnly=False, sparse=True, conn=None, volObject=None,
                 volInstall=None, volName=None):
        """
        @param path: filesystem path to the disk image.
        @type path: C{str}
        @param size: size of local file to create in gigabytes
        @type size: C{int} or C{long} or C{float}
        @param transient: whether to keep disk around after guest install
        @type transient: C{bool}
        @param type: disk media type (file, block, ...)
        @type type: C{str}
        @param device: Emulated device type (disk, cdrom, floppy, ...)
        @type device: member of devices
        @param driverName: name of driver
        @type driverName: member of driver_names
        @param driverType: type of driver
        @type driverType: member of driver_types
        @param readOnly: Whether emulated disk is read only
        @type readOnly: C{bool}
        @param sparse: Create file as a sparse file
        @type sparse: C{bool}
        @param conn: Connection disk is being installed on
        @type conn: libvirt.virConnect
        @param volObject: libvirt storage volume object to use
        @type volObject: libvirt.virStorageVol
        @param volInstall: StorageVolume instance to build for new storage
        @type volInstall: L{StorageVolume}
        """

        VirtualDevice.__init__(self, conn=conn)
        self.set_read_only(readOnly, validate=False)
        self.set_sparse(sparse, validate=False)
        self.set_type(type, validate=False)
        self.set_device(device, validate=False)
        self._set_path(path, validate=False)
        self._set_size(size, validate=False)
        self._set_vol_object(volObject, validate=False)
        self._set_vol_install(volInstall, validate=False)

        self.transient = transient
        self._driverName = driverName
        self._driverType = driverType
        self.target = None

        if volName:
            self.__lookup_vol_name(volName)

        self.__validate_params()


    def __repr__(self):
        """
        prints a simple string representation for the disk instance
        """
        return "%s:%s" %(self.type, self.path)



    def _get_path(self):
        return self._path
    def _set_path(self, val, validate=True):
        if val is not None:
            self._check_str(val, "path")
            val = os.path.abspath(val)
        self.__validate_wrapper("_path", val, validate)
    path = property(_get_path, _set_path)

    def _get_size(self):
        return self._size
    def _set_size(self, val, validate=True):
        if val is not None:
            if type(val) not in [int, float, long] or val < 0:
                raise ValueError, _("'size' must be a number greater than 0.")
        self.__validate_wrapper("_size", val, validate)
    size = property(_get_size, _set_size)

    def get_type(self):
        return self._type
    def set_type(self, val, validate=True):
        if val is not None:
            self._check_str(val, "type")
            if val not in self.types:
                raise ValueError, _("Unknown storage type '%s'" % val)
        self.__validate_wrapper("_type", val, validate)
    type = property(get_type, set_type)

    def get_device(self):
        return self._device
    def set_device(self, val, validate=True):
        self._check_str(val, "device")
        if val not in self.devices:
            raise ValueError, _("Unknown device type '%s'" % val)
        self.__validate_wrapper("_device", val, validate)
    device = property(get_device, set_device)

    def get_driver_name(self):
        return self._driverName
    driver_name = property(get_driver_name)

    def get_driver_type(self):
        return self._driverType
    driver_type = property(get_driver_type)

    def get_sparse(self):
        return self._sparse
    def set_sparse(self, val, validate=True):
        self._check_bool(val, "sparse")
        self.__validate_wrapper("_sparse", val, validate)
    sparse = property(get_sparse, set_sparse)

    def get_read_only(self):
        return self._readOnly
    def set_read_only(self, val, validate=True):
        self._check_bool(val, "read_only")
        self.__validate_wrapper("_readOnly", val, validate)
    read_only = property(get_read_only, set_read_only)

    def _get_vol_object(self):
        return self._vol_object
    def _set_vol_object(self, val, validate=True):
        if val is not None and not isinstance(val, libvirt.virStorageVol):
            raise ValueError, _("vol_object must be a virStorageVol instance")
        self.__validate_wrapper("_vol_object", val, validate)
    vol_object = property(_get_vol_object, _set_vol_object)

    def _get_vol_install(self):
        return self._vol_install
    def _set_vol_install(self, val, validate=True):
        if val is not None and not isinstance(val, Storage.StorageVolume):
            raise ValueError, _("vol_install must be a StorageVolume "
                                " instance.")
        self.__validate_wrapper("_vol_install", val, validate)
    vol_install = property(_get_vol_install, _set_vol_install)


    # Validation assistance methods
    def __validate_wrapper(self, varname, newval, validate=True):
        try:
            orig = getattr(self, varname)
        except:
            orig = newval
        setattr(self, varname, newval)
        if validate:
            try:
                self.__validate_params()
            except:
                setattr(self, varname, orig)
                raise

    def __set_dev_type(self):
        """
        Detect disk 'type' from passed storage parameters
        """

        dtype = None
        if self.vol_object:
            # vol info is [ vol type (file or block), capacity, allocation ]
            t = self.vol_object.info()[0]
            if t == libvirt.VIR_STORAGE_VOL_FILE:
                dtype = self.TYPE_FILE
            elif t == libvirt.VIR_STORAGE_VOL_BLOCK:
                dtype = self.TYPE_BLOCK
            else:
                raise ValueError, _("Unknown storage volume type.")
        elif self.vol_install:
            if isinstance(self.vol_install, Storage.FileVolume):
                dtype = self.TYPE_FILE
            else:
                raise ValueError, _("Unknown dev type for vol_install.")
        elif self.path:
            if stat.S_ISBLK(os.stat(self.path)[stat.ST_MODE]):
                dtype = self.TYPE_BLOCK
            else:
                dtype = self.TYPE_FILE

        logging.debug("Detected storage as type '%s'" % dtype)
        if self.type is not None and dtype != self.type:
            raise ValueError(_("Passed type '%s' does not match detected "
                               "storage type '%s'" % (self.type, dtype)))
        self.set_type(dtype, validate=False)

    def __lookup_vol_name(self, name_tuple):
        """
        lookup volume via tuple passed via __init__'s volName parameter
        """
        if type(name_tuple) is not tuple or len(name_tuple) != 2 \
           or (type(name_tuple[0]) is not type(name_tuple[1]) is not str):
            raise ValueError(_("volName must be a tuple of the form "
                               "('poolname', 'volname')"))
        if not self.conn:
            raise ValueError(_("'volName' requires a passed connection."))
        if not util.is_storage_capable(self.conn):
            raise ValueError(_("Connection does not support storage lookup."))
        try:
            pool = self.conn.storagePoolLookupByName(name_tuple[0])
            self._set_vol_object(pool.storageVolLookupByName(name_tuple[1]),
                                validate=False)
        except Exception, e:
            raise ValueError(_("Couldn't lookup volume object: %s" % str(e)))


    def __validate_params(self):
        """
        function to validate all the complex interaction between the various
        disk parameters.
        """

        # if storage capable, try to lookup path
        # if no obj: if remote, error
        storage_capable = False
        if self.conn:
            storage_capable = util.is_storage_capable(self.conn)
        if storage_capable:
            if self.path is not None and self.vol_object is None:
                v = None
                try:
                    v = self.conn.storageVolLookupByPath(self.path)
                except Exception, e:
                    if self._is_remote():
                        raise ValueError(_("'%s' is not managed on remote "
                                           "host: %s" % (self.path, str(e))))
                    else:
                        logging.debug("Didn't find path '%s' managed on "
                                      "connection: %s" % (self.path, str(e)))
                if v:
                    self._set_vol_object(v, validate=False)
        else:
            if self._is_remote():
                raise ValueError, _("Connection doesn't support remote "
                                    "storage.")

        if self._is_remote() and not (self.vol_object or self.vol_install):
            raise ValueError, _("Must specify libvirt managed storage if on "
                                "a remote connection")

        # Only floppy or cdrom can be created w/o media
        if self.path is None and not self.vol_object and not self.vol_install:
            if self.device != self.DEVICE_FLOPPY and \
               self.device != self.DEVICE_CDROM:
                raise ValueError, _("Device type '%s' requires a path") % \
                                  self.device
            # If no path, our work is done
            return True

        if self.vol_object:
            logging.debug("Overwriting 'path' from passed volume object.")
            self._set_path(self.vol_object.path(), validate=False)

        if self.vol_install:
            logging.debug("Overwriting 'size' with 'path' with values from "
                          "passed StorageVolume")
            self._set_size(self.vol_install.capacity*1024*1024*1024,
                          validate=False)
            self._set_path(self.vol_install.target_path, validate=False)

        if self.vol_object or self.vol_install or self._is_remote():
            logging.debug("Using storage api objects for VirtualDisk")
            using_path = False
        else:
            logging.debug("Using self.path for VirtualDisk.")
            using_path = True

        if ((using_path and os.path.exists(self.path))
                        or self.vol_object):
            logging.debug("VirtualDisk storage exists.")

            if using_path and os.path.isdir(self.path):
                raise ValueError, _("The path must be a file or a device,"
                                    " not a directory")
            self.__set_dev_type()
            return True

        logging.debug("VirtualDisk storage does not exist.")
        if self.device == self.DEVICE_FLOPPY or \
           self.device == self.DEVICE_CDROM:
            raise ValueError, _("Cannot create storage for %s device.") % \
                                self.device

        if using_path:
            # Not true for api?
            if self.type is self.TYPE_BLOCK:
                raise ValueError, _("Local block device path must exist.")
            self.set_type(self.TYPE_FILE, validate=False)

            # Path doesn't exist: make sure we have write access to dir
            if not os.access(os.path.dirname(self.path), os.W_OK):
                raise ValueError, _("No write access to directory '%s'") % \
                                    os.path.dirname(self.path)
            if not self.size:
                raise ValueError, _("size is required for non-existent disk "
                                    "'%s'" % self.path)
        else:
            self.__set_dev_type()

        ret = self.is_size_conflict()
        if ret[0]:
            raise ValueError, ret[1]
        elif ret[1]:
            logging.warn(ret[1])



    def setup(self, progresscb=None):
        """
        Build storage (if required)

        If storage doesn't exist (a non-existent file 'path', or 'vol_install'
        was specified), we create it.

        @param progresscb: progress meter
        @type progresscb: instanceof urlgrabber.BaseMeter
        """
        if self.vol_object:
            return
        elif self.vol_install:
            self.vol_object = self.vol_install.install(meter=progresscb)
            return
        elif self.type == VirtualDisk.TYPE_FILE and self.path is not None \
             and not os.path.exists(self.path):
            size_bytes = long(self.size * 1024L * 1024L * 1024L)

            if progresscb:
                progresscb.start(filename=self.path,size=long(size_bytes), \
                                 text=_("Creating storage file..."))
            fd = None
            try:
                try:
                    fd = os.open(self.path, os.O_WRONLY | os.O_CREAT)
                    if self.sparse:
                        os.lseek(fd, size_bytes, 0)
                        os.write(fd, '\x00')
                        if progresscb:
                            progresscb.update(self.size)
                    else:
                        buf = '\x00' * 1024 * 1024 # 1 meg of nulls
                        for i in range(0, long(self.size * 1024L)):
                            os.write(fd, buf)
                            if progresscb:
                                progresscb.update(long(i * 1024L * 1024L))
                except OSError, e:
                    raise RuntimeError, _("Error creating diskimage %s: %s" % \
                                        (self.path, str(e)))
            finally:
                if fd is not None:
                    os.close(fd)
                if progresscb:
                    progresscb.end(size_bytes)
        # FIXME: set selinux context?

    def get_xml_config(self, disknode):
        """
        @param disknode: device name in host (xvda, hdb, etc.)
        @type disknode: C{str}
        """
        typeattr = 'file'
        if self.type == VirtualDisk.TYPE_BLOCK:
            typeattr = 'dev'

        path = self.path
        if self.path:
            path = util.xml_escape(path)

        ret = "    <disk type='%(type)s' device='%(device)s'>\n" % { "type": self.type, "device": self.device }
        if not(self.driver_name is None):
            if self.driver_type is None:
                ret += "      <driver name='%(name)s'/>\n" % { "name": self.driver_name }
            else:
                ret += "      <driver name='%(name)s' type='%(type)s'/>\n" % { "name": self.driver_name, "type": self.driver_type }
        if path is not None:
            ret += "      <source %(typeattr)s='%(disk)s'/>\n" % { "typeattr": typeattr, "disk": path }
        if self.target is not None:
            disknode = self.target
        ret += "      <target dev='%(disknode)s'/>\n" % { "disknode": disknode }

        ro = self.read_only

        if self.device == self.DEVICE_CDROM:
            ro = True
        if ro:
            ret += "      <readonly/>\n"
        ret += "    </disk>"
        return ret

    def is_size_conflict(self):
        """
        reports if disk size conflicts with available space

        returns a two element tuple:
            1. first element is True if fatal conflict occurs
            2. second element is a string description of the conflict or None
        Non fatal conflicts (sparse disk exceeds available space) will
        return (False, "description of collision")
        """

        if self.vol_object or self.size is None or not self.path \
           or os.path.exists(self.path) or self.type != self.TYPE_FILE:
            return (False, None)

        if self.vol_install:
            return self.vol_install.is_size_conflict()

        ret = False
        msg = None
        vfs = os.statvfs(os.path.dirname(self.path))
        avail = vfs[statvfs.F_FRSIZE] * vfs[statvfs.F_BAVAIL]
        need = long(self.size * 1024L * 1024L * 1024L)
        if need > avail:
            if self.sparse:
                msg = _("The filesystem will not have enough free space"
                        " to fully allocate the sparse file when the guest"
                        " is running.")
            else:
                ret = True
                msg = _("There is not enough free space to create the disk.")


            if msg:
                msg += _(" %d M requested > %d M available") % \
                        ((need / (1024*1024)), (avail / (1024*1024)))
        return (ret, msg)

    def is_conflict_disk(self, conn):
        """
        check if specified storage is in use by any other VMs on passed
        connection.

        @param conn: connection to check for collisions on
        @type conn: libvirt.virConnect

        @return: True if a collision, False otherwise
        @rtype: C{bool}
        """
        vms = []
        # get working domain's name
        ids = conn.listDomainsID();
        for id in ids:
            try:
                vm = conn.lookupByID(id)
                vms.append(vm)
            except libvirt.libvirtError:
                # guest probably in process of dieing
                logging.warn("Failed to lookup domain id %d" % id)
        # get defined domain
        names = conn.listDefinedDomains()
        for name in names:
            try:
                vm = conn.lookupByName(name)
                vms.append(vm)
            except libvirt.libvirtError:
                # guest probably in process of dieing
                logging.warn("Failed to lookup domain name %s" % name)

        count = 0
        for vm in vms:
            doc = None
            try:
                doc = libxml2.parseDoc(vm.XMLDesc(0))
            except:
                continue
            ctx = doc.xpathNewContext()
            try:
                try:
                    count += ctx.xpathEval("count(/domain/devices/disk/source[@dev='%s'])" % self.path)
                    count += ctx.xpathEval("count(/domain/devices/disk/source[@file='%s'])" % self.path)
                except:
                    continue
            finally:
                if ctx is not None:
                    ctx.xpathFreeContext()
                if doc is not None:
                    doc.freeDoc()
        if count > 0:
            return True
        else:
            return False



class XenDisk(VirtualDisk):
    """
    Back compat class to avoid ABI break.
    """
    pass
