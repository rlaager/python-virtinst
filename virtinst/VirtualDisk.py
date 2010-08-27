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

import os, stat, pwd, statvfs
import subprocess
import logging
import re

import urlgrabber.progress as progress
import libvirt

import _util
import Storage
from VirtualDevice import VirtualDevice
from virtinst import _virtinst as _

def _vdisk_create(path, size, kind, sparse = True):
    force_fixed = "raw"
    path = os.path.expanduser(path)
    if kind in force_fixed or not sparse:
        _type = kind + ":fixed"
    else:
        _type = kind + ":sparse"
    try:
        rc = subprocess.call([ '/usr/sbin/vdiskadm', 'create', '-t', _type,
            '-s', str(size), path ])
        return rc == 0
    except OSError:
        return False

def _vdisk_clone(path, clone):
    logging.debug("Using vdisk clone.")

    path = os.path.expanduser(path)
    clone = os.path.expanduser(clone)
    try:
        rc = subprocess.call([ '/usr/sbin/vdiskadm', 'clone', path, clone ])
        return rc == 0
    except OSError:
        return False

def _qemu_sanitize_drvtype(phystype, fmt):
    """
    Sanitize libvirt storage volume format to a valid qemu driver type
    """
    raw_list = [ "iso" ]

    if phystype == VirtualDisk.TYPE_BLOCK and not fmt:
        return VirtualDisk.DRIVER_QEMU_RAW

    if fmt in raw_list:
        return VirtualDisk.DRIVER_QEMU_RAW

    return fmt

def _name_uid(user):
    """
    Return UID for string username
    """
    pwdinfo = pwd.getpwnam(user)
    return pwdinfo[2]

def _is_dir_searchable(uid, username, path):
    """
    Check if passed directory is searchable by uid
    """
    try:
        statinfo = os.stat(path)
    except OSError:
        return False

    if uid == statinfo.st_uid:
        flag = stat.S_IXUSR
    elif uid == statinfo.st_gid:
        flag = stat.S_IXGRP
    else:
        flag = stat.S_IXOTH

    if bool(statinfo.st_mode & flag):
        return True

    # Check POSIX ACL (since that is what we use to 'fix' access)
    cmd = ["getfacl", path]
    try:
        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE)
        out, err = proc.communicate()
    except OSError:
        logging.debug("Didn't find the getfacl command.")
        return False

    if proc.returncode != 0:
        logging.debug("Cmd '%s' failed: %s" % (cmd, err))
        return False

    return bool(re.search("user:%s:..x" % username, out))


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
        5. An active connection and a path. The base of the path must
           point to the target path for an active pool.

    For cases 3 and 4, the lookup will be performed, and 'vol_object'
    will be set to the returned virStorageVol. For the last case, 'volInstall'
    will be populated for a StorageVolume instance. All the above cases also
    work on a local connection as well, the only difference being that
    option 3 won't neccessarily error out if the volume isn't found.

    __init__ and setting all properties performs lots of validation,
    and will throw ValueError's if problems are found.
    """

    _virtual_device_type = VirtualDevice.VIRTUAL_DEV_DISK

    DRIVER_FILE = "file"
    DRIVER_PHY = "phy"
    DRIVER_TAP = "tap"
    DRIVER_QEMU = "qemu"
    driver_names = [DRIVER_FILE, DRIVER_PHY, DRIVER_TAP, DRIVER_QEMU]

    DRIVER_QEMU_RAW = "raw"
    # No list here, since there are many other valid values

    DRIVER_TAP_RAW = "aio"
    DRIVER_TAP_QCOW = "qcow"
    DRIVER_TAP_VMDK = "vmdk"
    DRIVER_TAP_VDISK = "vdisk"
    driver_types = [DRIVER_TAP_RAW, DRIVER_TAP_QCOW,
        DRIVER_TAP_VMDK, DRIVER_TAP_VDISK]

    CACHE_MODE_NONE = "none"
    CACHE_MODE_WRITETHROUGH = "writethrough"
    CACHE_MODE_WRITEBACK = "writeback"
    cache_types = [CACHE_MODE_NONE, CACHE_MODE_WRITETHROUGH,
        CACHE_MODE_WRITEBACK]

    DEVICE_DISK = "disk"
    DEVICE_CDROM = "cdrom"
    DEVICE_FLOPPY = "floppy"
    devices = [DEVICE_DISK, DEVICE_CDROM, DEVICE_FLOPPY]

    TYPE_FILE = "file"
    TYPE_BLOCK = "block"
    TYPE_DIR = "dir"
    types = [TYPE_FILE, TYPE_BLOCK, TYPE_DIR]

    @staticmethod
    def path_exists(conn, path):
        """
        Check if path exists. If we can't determine, return False
        """
        is_remote = _util.is_uri_remote(conn.getURI())
        try:
            vol = None
            try:
                vol = conn.storageVolLookupByPath(path)
            except:
                pass

            if vol:
                return True

            if not is_remote:
                return os.path.exists(path)
        except:
            pass

        return False

    @staticmethod
    def check_path_search_for_user(conn, path, username):
        """
        Check if the passed user has search permissions for all the
        directories in the disk path.

        @return: List of the directories the user cannot search, or empty list
        @rtype : C{list}
        """
        if _util.is_uri_remote(conn.getURI()):
            return []

        try:
            uid = _name_uid(username)
        except Exception, e:
            logging.debug("Error looking up username: %s" % str(e))
            return []

        fixlist = []

        if os.path.isdir(path):
            dirname = path
            base = "-"
        else:
            dirname, base = os.path.split(path)

        while base:
            if not _is_dir_searchable(uid, username, dirname):
                fixlist.append(dirname)

            dirname, base = os.path.split(dirname)

        return fixlist

    @staticmethod
    def fix_path_search_for_user(conn, path, username):
        """
        Try to fix any permission problems found by check_path_search_for_user

        @return: Return a dictionary of entries { broken path : error msg }
        @rtype : C{dict}
        """
        def fix_perms(dirname, useacl=True):
            if useacl:
                cmd = ["setfacl", "--modify", "user:%s:x" % username, dirname]
                proc = subprocess.Popen(cmd,
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
                out, err = proc.communicate()

                logging.debug("Ran command '%s'" % cmd)
                if out or err:
                    logging.debug("out=%s\nerr=%s" % (out, err))

                if proc.returncode != 0:
                    raise ValueError(err)
            else:
                mode = os.stat(dirname).st_mode
                os.chmod(dirname, mode | stat.S_IXOTH)

        fixlist = VirtualDisk.check_path_search_for_user(conn, path, username)
        if not fixlist:
            return []

        fixlist.reverse()
        errdict = {}

        useacl = True
        for dirname in fixlist:
            try:
                try:
                    fix_perms(dirname, useacl)
                except:
                    # If acl fails, fall back to chmod and retry
                    if not useacl:
                        raise
                    useacl = False

                    fix_perms(dirname, useacl)
            except Exception, e:
                errdict[dirname] =  str(e)

        return errdict

    @staticmethod
    def path_in_use_by(conn, path, check_conflict=False):
        """
        Return a list of VM names that are using the passed path.

        @param conn: virConnect to check VMs
        @param path: Path to check for
        @param check_conflict: Only return names that are truly conflicting:
                               this will omit guests that are using the disk
                               with the 'shareable' flag, and possible other
                               heuristics
        """
        if not path:
            return

        active, inactive = _util.fetch_all_guests(conn)
        vms = active + inactive

        def count_cb(ctx):
            c = 0

            template = "count(/domain/devices/disk["
            if check_conflict:
                template += "not(shareable) and "
            template += "source/@%s='%s'])"

            for dtype in ["dev", "file", "dir"]:
                xpath = template % (dtype, path)
                c += ctx.xpathEval(xpath)

            return c

        names = []
        for vm in vms:
            xml = vm.XMLDesc(0)
            tmpcount = _util.get_xml_path(xml, func = count_cb)
            if tmpcount:
                names.append(vm.name())

        return names

    @staticmethod
    def stat_local_path(path):
        """
        Return tuple (storage type, storage size) for the passed path on
        the local machine. This is a best effort attempt.

        @return: tuple of
                 (True if regular file, False otherwise, default is True,
                  max size of storage, default is 0)
        """
        try:
            return _util.stat_disk(path)
        except:
            return (True, 0)

    def __init__(self, path=None, size=None, transient=False, type=None,
                 device=DEVICE_DISK, driverName=None, driverType=None,
                 readOnly=False, sparse=True, conn=None, volObject=None,
                 volInstall=None, volName=None, bus=None, shareable=False,
                 driverCache=None, selinuxLabel=None, format=None,
                 validate=True):
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
        @param volName: Existing StorageVolume lookup information,
                        (parent pool name, volume name)
        @type volName: C{tuple} of (C{str}, C{str})
        @param bus: Emulated bus type (ide, scsi, virtio, ...)
        @type bus: C{str}
        @param shareable: If disk can be shared among VMs
        @type shareable: C{bool}
        @param driverCache: Disk cache mode (none, writethrough, writeback)
        @type driverCache: member of cache_types
        @param selinuxLabel: Used for labelling new or relabel existing storage
        @type selinuxLabel: C{str}
        @param format: Storage volume format to use when creating storage
        @type format: C{str}
        @param validate: Whether to validate passed parameters against the
                         local system. Omitting this may cause issues, be
                         warned!
        @type validate: C{bool}
        """

        VirtualDevice.__init__(self, conn=conn)

        self._path = None
        self._size = None
        self._type = None
        self._device = None
        self._sparse = None
        self._readOnly = None
        self._vol_object = None
        self._vol_install = None
        self._bus = None
        self._shareable = None
        self._driver_cache = None
        self._selinux_label = None
        self._clone_path = None
        self._format = None
        self._validate = validate

        # XXX: No property methods for these
        self.transient = transient
        self._driverName = driverName
        self._driverType = driverType
        self.target = None

        self.set_read_only(readOnly, validate=False)
        self.set_sparse(sparse, validate=False)
        self.set_type(type, validate=False)
        self.set_device(device, validate=False)
        self._set_path(path, validate=False)
        self._set_size(size, validate=False)
        self._set_vol_object(volObject, validate=False)
        self._set_vol_install(volInstall, validate=False)
        self._set_bus(bus, validate=False)
        self._set_shareable(shareable, validate=False)
        self._set_driver_cache(driverCache, validate=False)
        self._set_selinux_label(selinuxLabel, validate=False)
        self._set_format(format, validate=False)

        if volName:
            self.__lookup_vol_name(volName)

        self.__validate_params()


    def __repr__(self):
        """
        prints a simple string representation for the disk instance
        """
        return "%s:%s" %(self.type, self.path)



    def _get_path(self):
        retpath = self._path
        if self.vol_object:
            retpath = self.vol_object.path()
        elif self.vol_install:
            retpath = (_util.get_xml_path(self.vol_install.pool.XMLDesc(0),
                                          "/pool/target/path") + "/" +
                       self.vol_install.name)

        return retpath
    def _set_path(self, val, validate=True):
        if val is not None:
            self._check_str(val, "path")
            val = os.path.abspath(val)

        if validate:
            self._vol_install = None
            self._vol_object = None
            self._type = None

        self.__validate_wrapper("_path", val, validate)
    path = property(_get_path, _set_path)

    def _get_clone_path(self):
        return self._clone_path
    def _set_clone_path(self, val, validate=True):
        if val is not None:
            self._check_str(val, "path")
            val = os.path.abspath(val)

            # Pass the path to a VirtualDisk, which should provide validation
            # for us
            try:
                # If this disk isn't managed, don't pass 'conn' to this
                # validation disk, to ensure we have permissions for manual
                # cloning
                conn = self.__storage_specified() and self.conn or None
                VirtualDisk(conn=conn, path=val)
            except Exception, e:
                raise ValueError(_("Error validating clone path: %s") % e)
        self.__validate_wrapper("_clone_path", val, validate)
    clone_path = property(_get_clone_path, _set_clone_path)

    def _get_size(self):
        retsize = self._size
        if self.vol_install:
            newsize = self.vol_install.capacity/1024.0/1024.0/1024.0

        return retsize
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
    def set_driver_name(self, val):
        self._driverName = val
    driver_name = property(get_driver_name, set_driver_name)

    def get_driver_type(self):
        return self._driverType
    def set_driver_type(self, val):
        self._driverType = val
    driver_type = property(get_driver_type, set_driver_type)

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

    def _get_bus(self):
        return self._bus
    def _set_bus(self, val, validate=True):
        if val is not None:
            self._check_str(val, "bus")
        self.__validate_wrapper("_bus", val, validate)
    bus = property(_get_bus, _set_bus)

    def _get_shareable(self):
        return self._shareable
    def _set_shareable(self, val, validate=True):
        self._check_bool(val, "shareable")
        self.__validate_wrapper("_shareable", val, validate)
    shareable = property(_get_shareable, _set_shareable)

    def _get_driver_cache(self):
        return self._driver_cache
    def _set_driver_cache(self, val, validate=True):
        if val is not None:
            self._check_str(val, "cache")
            if val not in self.cache_types:
                raise ValueError, _("Unknown cache mode '%s'" % val)
        self.__validate_wrapper("_driver_cache", val, validate)
    driver_cache = property(_get_driver_cache, _set_driver_cache)

    # If there is no selinux support on the libvirt connection or the
    # system, we won't throw errors if this is set, just silently ignore.
    def _get_selinux_label(self):
        # If selinux_label manually specified, return it
        # If we are using existing storage, pull the label from it
        # If we are installing via vol_install, pull from the parent pool
        # If we are creating local storage, use the expected label
        retlabel = self._selinux_label
        if not retlabel:
            retlabel = ""
            if self.__creating_storage() and not self.__storage_specified():
                retlabel = self._expected_security_label()
            else:
                retlabel = self._storage_security_label()

        return retlabel
    def _set_selinux_label(self, val, validate=True):
        if val is not None:
            self._check_str(val, "selinux_label")

            if (self._support_selinux() and
                not _util.selinux_is_label_valid(val)):
                # XXX Not valid if we support changing labels remotely
                raise ValueError(_("SELinux label '%s' is not valid.") % val)

        self.__validate_wrapper("_selinux_label", val, validate)
    selinux_label = property(_get_selinux_label, _set_selinux_label)

    def _get_format(self):
        return self._format
    def _set_format(self, val, validate=True):
        if val is not None:
            self._check_str(val, "format")
        self.__validate_wrapper("_format", val, validate)
    format = property(_get_format, _set_format)

    # Validation assistance methods

    # Initializes attribute if it hasn't been done, then validates args.
    # If validation fails, reset attribute to original value and raise error
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

    def __set_format(self):
        if not self.format:
            return

        if not self.__creating_storage():
            return

        if self.vol_install:
            if not hasattr(self.vol_install, "format"):
                raise ValueError(_("Storage type does not support format "
                                   "parameter."))
            if self.vol_install.format != self.format:
                self.vol_install.format = self.format

        elif self.format != "raw":
            raise RuntimeError(_("Format cannot be specified for "
                                 "unmanaged storage."))

    def __set_size(self):
        """
        Fill in 'size' attribute for existing storage.
        """

        if self.__creating_storage():
            return

        if self.__storage_specified() and self.vol_object:
            newsize = _util.get_xml_path(self.vol_object.XMLDesc(0),
                                         "/volume/capacity")
            try:
                newsize = float(newsize) / 1024.0 / 1024.0 / 1024.0
            except:
                newsize = 0
        elif self.path is None:
            newsize = 0
        else:
            ignore, newsize = _util.stat_disk(self.path)
            newsize = newsize / 1024.0 / 1024.0 / 1024.0

        if newsize != self.size:
            self._set_size(newsize, validate=False)

    def __set_dev_type(self):
        """
        Detect disk 'type' () from passed storage parameters
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
            if self.vol_install.file_type == libvirt.VIR_STORAGE_VOL_FILE:
                dtype = self.TYPE_FILE
            else:
                dtype = self.TYPE_BLOCK
        elif self.path:
            if os.path.isdir(self.path):
                dtype = self.TYPE_DIR
            elif _util.stat_disk(self.path)[0]:
                dtype = self.TYPE_FILE
            else:
                dtype = self.TYPE_BLOCK

        if not dtype:
            dtype = self.type or self.TYPE_BLOCK

        elif self.type and dtype != self.type:
            raise ValueError(_("Passed type '%s' does not match detected "
                               "storage type '%s'" % (self.type, dtype)))
        self.set_type(dtype, validate=False)

    def __set_driver(self):
        """
        Set driverName and driverType from passed parameters

        Where possible, we want to force driverName = "raw" if installing
        a QEMU VM. Without telling QEMU to expect a raw file, the emulator
        is forced to autodetect, which has security implications:

        http://lists.gnu.org/archive/html/qemu-devel/2008-04/msg00675.html
        """
        drvname = self._driverName
        drvtype = self._driverType

        if self.conn:
            driver = _util.get_uri_driver(self._get_uri())
            if driver.lower() == "qemu":
                drvname = self.DRIVER_QEMU

        if self.format:
            if drvname == self.DRIVER_QEMU:
                drvtype = _qemu_sanitize_drvtype(self.type, self.format)

        elif self.vol_object:
            fmt = _util.get_xml_path(self.vol_object.XMLDesc(0),
                                     "/volume/target/format/@type")
            if drvname == self.DRIVER_QEMU:
                drvtype = _qemu_sanitize_drvtype(self.type, fmt)

        elif self.vol_install:
            if drvname == self.DRIVER_QEMU:
                if hasattr(self.vol_install, "format"):
                    drvtype = _qemu_sanitize_drvtype(self.type,
                                                     self.vol_install.format)

        elif self.__creating_storage():
            if drvname == self.DRIVER_QEMU:
                drvtype = self.DRIVER_QEMU_RAW

        elif self.path and os.path.exists(self.path):
            if _util.is_vdisk(self.path):
                drvname = self.DRIVER_TAP
                drvtype = self.DRIVER_TAP_VDISK

        # User already set driverName to a different value, respect that
        if self._driverName and self._driverName != drvname:
            return
        self._driverName = drvname or None

        if self._driverType and self._driverType != drvtype:
            return
        self._driverType = drvtype or None

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
        if not _util.is_storage_capable(self.conn):
            raise ValueError(_("Connection does not support storage lookup."))
        try:
            pool = self.conn.storagePoolLookupByName(name_tuple[0])
            self._set_vol_object(pool.storageVolLookupByName(name_tuple[1]),
                                validate=False)
        except Exception, e:
            raise ValueError(_("Couldn't lookup volume object: %s" % str(e)))

    def __storage_specified(self):
        """
        Return bool representing if managed storage parameters have
        been explicitly specified or filled in
        """
        return (self.vol_object != None or self.vol_install != None)

    def __creating_storage(self):
        """
        Return True if the user requested us to create a device
        """
        return not (self.__no_storage() or
                    (self.__storage_specified() and self.vol_object) or
                    (self.path and os.path.exists(self.path)))

    def __no_storage(self):
        """
        Return True if no path or storage was specified
        """
        return (not self.__storage_specified() and not self.path)

    def __check_if_path_managed(self):
        """
        Determine if we can use libvirt storage apis to create or lookup
        'self.path'
        """
        vol = None
        verr = None

        def lookup_vol_by_path():
            try:
                vol = self.conn.storageVolLookupByPath(self.path)
                vol.info()
                return vol, None
            except Exception, e:
                return None, e

        pool = _util.lookup_pool_by_path(self.conn,
                                         os.path.dirname(self.path))
        vol = lookup_vol_by_path()[0]


        # Is pool running?
        if pool and pool.info()[0] != libvirt.VIR_STORAGE_POOL_RUNNING:
            pool = None

        # Attempt to lookup path as a storage volume
        if pool and not vol:
            try:
                # Pool may need to be refreshed, but if it errors,
                # invalidate it
                if pool:
                    pool.refresh(0)

                vol, verr = lookup_vol_by_path()
            except Exception, e:
                vol = None
                pool = None
                verr = str(e)

        if vol:
            self._set_vol_object(vol, validate=False)
            return

        if not pool:
            if not self._is_remote():
                # Building local disk
                return

            if not verr:
                # Since there is no error, no pool was ever found
                err = (_("Cannot use storage '%(path)s': '%(rootdir)s' is "
                         "not managed on the remote host.") %
                         { 'path' : self.path,
                           'rootdir' : os.path.dirname(self.path)})
            else:
                err = (_("Cannot use storage %(path)s: %(err)s") %
                        { 'path' : self.path, 'err' : verr })

            raise ValueError(err)

        # Path wasn't a volume. See if base of path is a managed
        # pool, and if so, setup a StorageVolume object
        if self.size == None:
            raise ValueError(_("Size must be specified for non "
                               "existent volume path '%s'" % self.path))

        logging.debug("Path '%s' is target for pool '%s'. "
                      "Creating volume '%s'." %
                      (os.path.dirname(self.path), pool.name(),
                       os.path.basename(self.path)))

        volclass = Storage.StorageVolume.get_volume_for_pool(pool_object=pool)
        cap = (self.size * 1024 * 1024 * 1024)
        if self.sparse:
            alloc = 0
        else:
            alloc = cap

        vol = volclass(name=os.path.basename(self.path),
                       capacity=cap, allocation=alloc, pool=pool)
        self._set_vol_install(vol, validate=False)


    def _storage_security_label(self):
        """
        Return SELinux label of existing storage, or None
        """
        context = ""

        if self.__no_storage():
            return context

        if self.vol_object:
            context = _util.get_xml_path(self.vol_object.XMLDesc(0),
                                         "/volume/target/permissions/label")
        elif self.vol_install:
            # XXX: If user entered a manual label, should we sync this
            # to vol_install?
            l = _util.get_xml_path(self.vol_install.pool.XMLDesc(0),
                                   "/pool/target/permissions/label")
            context = l or ""
        else:
            context = _util.selinux_getfilecon(self.path)

        return context


    def __validate_params(self):
        """
        function to validate all the complex interaction between the various
        disk parameters.
        """
        if not self._validate:
            return

        # No storage specified for a removable device type (CDROM, floppy)
        if self.__no_storage():
            if (self.device != self.DEVICE_FLOPPY and
                self.device != self.DEVICE_CDROM):
                raise ValueError(_("Device type '%s' requires a path") %
                                 self.device)

            self._type = self.TYPE_BLOCK
            return True

        storage_capable = bool(self.conn and
                               _util.is_storage_capable(self.conn))

        if storage_capable and not self.__storage_specified():
            # Try to lookup self.path storage objects
            self.__check_if_path_managed()

        if self._is_remote():
            if not storage_capable:
                raise ValueError, _("Connection doesn't support remote "
                                    "storage.")
            if not self.__storage_specified():
                raise ValueError, _("Must specify libvirt managed storage "
                                    "if on a remote connection")

        # The main distinctions from this point forward:
        # - Are we doing storage API operations or local media checks?
        # - Do we need to create the storage?

        managed_storage = self.__storage_specified()
        create_media = self.__creating_storage()

        self.__set_dev_type()
        self.__set_size()
        self.__set_format()
        self.__set_driver()

        # If not creating the storage, our job is easy
        if not create_media:
            # Make sure we have access to the local path
            if not managed_storage:
                if (os.path.isdir(self.path) and
                    not _util.is_vdisk(self.path) and
                    not self.device == self.DEVICE_FLOPPY):
                    raise ValueError(_("The path '%s' must be a file or a "
                                       "device, not a directory") % self.path)

            return True


        if self.device == self.DEVICE_FLOPPY or \
           self.device == self.DEVICE_CDROM:
            raise ValueError, _("Cannot create storage for %s device.") % \
                                self.device

        if not managed_storage:
            if self.type is self.TYPE_BLOCK:
                raise ValueError, _("Local block device path '%s' must "
                                    "exist.") % self.path

            # Path doesn't exist: make sure we have write access to dir
            if not os.access(os.path.dirname(self.path), os.R_OK):
                raise ValueError("No read access to directory '%s'" %
                                 os.path.dirname(self.path))
            if self.size is None:
                raise ValueError, _("size is required for non-existent disk "
                                    "'%s'" % self.path)
            if not os.access(os.path.dirname(self.path), os.W_OK):
                raise ValueError, _("No write access to directory '%s'") % \
                                    os.path.dirname(self.path)

        # Applicable for managed or local storage
        ret = self.is_size_conflict()
        if ret[0]:
            raise ValueError, ret[1]
        elif ret[1]:
            logging.warn(ret[1])

    # Storage creation routines
    def _do_create_storage(self, progresscb):
        # If a clone_path is specified, but not vol_install.input_vol,
        # that means we are cloning unmanaged -> managed, so skip this
        if (self.vol_install and
            (not self.clone_path or self.vol_install.input_vol)):
            self._set_vol_object(self.vol_install.install(meter=progresscb),
                                 validate=False)
            # Then just leave: vol_install should handle any selinux stuff
            return

        if self.clone_path:
            text = (_("Cloning %(srcfile)s") %
                    {'srcfile' : os.path.basename(self.clone_path)})
        else:
            text=_("Creating storage file %s") % os.path.basename(self.path)

        size_bytes = long(self.size * 1024L * 1024L * 1024L)
        progresscb.start(filename=self.path, size=long(size_bytes),
                         text=text)

        if self.clone_path:
            # VDisk clone
            if (_util.is_vdisk(self.clone_path) or
                (os.path.exists(self.path) and _util.is_vdisk(self.path))):

                if (not _util.is_vdisk(self.clone_path) or
                    os.path.exists(self.path)):
                    raise RuntimeError, _("copying to an existing vdisk is not"
                                          " supported")
                if not _vdisk_clone(self.clone_path, self.path):
                    raise RuntimeError, _("failed to clone disk")
                progresscb.end(size_bytes)

            else:
                # Plain file clone
                self._clone_local(progresscb, size_bytes)

        elif _util.is_vdisk(self.path):
            # Create vdisk
            progresscb.update(1024)
            if not _vdisk_create(self.path, size_bytes, "vmdk", self.sparse):
                raise RuntimeError, _("Error creating vdisk %s" % self.path)

            progresscb.end(self.size)
        else:
            # Plain file creation
            self._create_local_file(progresscb, size_bytes)

    def _create_local_file(self, progresscb, size_bytes):
        """
        Helper function which attempts to build self.path
        """
        fd = None

        try:
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_DSYNC)
                if self.sparse:
                    os.ftruncate(fd, size_bytes)
                    progresscb.update(self.size)
                else:
                    buf = '\x00' * 1024 * 1024 # 1 meg of nulls
                    for i in range(0, long(self.size * 1024L)):
                        os.write(fd, buf)
                        progresscb.update(long(i * 1024L * 1024L))
            except OSError, e:
                raise RuntimeError(_("Error creating diskimage %s: %s") %
                                   (self.path, str(e)))
        finally:
            if fd is not None:
                os.close(fd)
            progresscb.end(size_bytes)

    def _clone_local(self, meter, size_bytes):

        # if a destination file exists and sparse flg is True,
        # this priority takes a existing file.
        if (os.path.exists(self.path) == False and self.sparse == True):
            clone_block_size = 4096
            sparse = True
            fd = None
            try:
                fd = os.open(self.path, os.O_WRONLY | os.O_CREAT)
                os.ftruncate(fd, size_bytes)
            finally:
                if fd:
                    os.close(fd)
        else:
            clone_block_size = 1024*1024*10
            sparse = False

        logging.debug("Local Cloning %s to %s, sparse=%s, block_size=%s" %
                      (self.clone_path, self.path, sparse, clone_block_size))

        zeros = '\0' * 4096

        src_fd, dst_fd = None, None
        try:
            try:
                src_fd = os.open(self.clone_path, os.O_RDONLY)
                dst_fd = os.open(self.path, os.O_WRONLY | os.O_CREAT)

                i=0
                while 1:
                    l = os.read(src_fd, clone_block_size)
                    s = len(l)
                    if s == 0:
                        meter.end(size_bytes)
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
                    if i < size_bytes:
                        meter.update(i)
            except OSError, e:
                raise RuntimeError(_("Error cloning diskimage %s to %s: %s") %
                                       (self.clone_path, self.path, str(e)))
        finally:
            if src_fd is not None:
                os.close(src_fd)
            if dst_fd is not None:
                os.close(dst_fd)

    def setup_dev(self, conn=None, meter=None):
        """
        Build storage (if required)

        If storage doesn't exist (a non-existent file 'path', or 'vol_install'
        was specified), we create it.

        @param conn: Optional connection to use if self.conn not specified
        @param meter: Progress meter to report file creation on
        @type meter: instanceof urlgrabber.BaseMeter
        """
        return self.setup(meter)

    def setup(self, progresscb=None):
        """
        DEPRECATED: Please use setup_dev instead
        """
        if not progresscb:
            progresscb = progress.BaseMeter()

        if self.__creating_storage() or self.clone_path:
            self._do_create_storage(progresscb)

        # Relabel storage if it was requested
        storage_label = self._storage_security_label()
        if storage_label and storage_label != self.selinux_label:
            if not self._support_selinux():
                logging.debug("No support for changing selinux context.")
            elif not self._security_can_fix():
                logging.debug("Can't fix selinux context in this case.")
            else:
                logging.debug("Changing path=%s selinux label %s -> %s" %
                              (self.path, storage_label, self.selinux_label))
                _util.selinux_setfilecon(self.path, self.selinux_label)

    def _get_xml_config(self, disknode=None):
        """
        @param disknode: device name in host (xvda, hdb, etc.). self.target
                         takes precedence.
        @type disknode: C{str}
        """
        typeattr = self.type
        if self.type == VirtualDisk.TYPE_BLOCK:
            typeattr = 'dev'

        if self.target:
            disknode = self.target
        if not disknode:
            raise ValueError(_("'disknode' or self.target must be set!"))

        path = None
        if self.vol_object:
            path = self.vol_object.path()
        elif self.path:
            path = self.path
        if path:
            path = _util.xml_escape(path)

        ret = "    <disk type='%s' device='%s'>\n" % (self.type, self.device)

        dname = self.driver_name
        if not dname and self.driver_cache:
            self.driver_name = "qemu"

        if path:
            drvxml = ""
            if not self.driver_name is None:
                drvxml += " name='%s'" % self.driver_name

            if not self.driver_type is None:
                drvxml += " type='%s'" % self.driver_type

            if not self.driver_cache is None:
                drvxml += " cache='%s'" % self.driver_cache

            if drvxml:
                ret += "      <driver%s/>\n" % drvxml

        if path is not None:
            ret += "      <source %s='%s'/>\n" % (typeattr, path)

        bus_xml = ""
        if self.bus is not None:
            bus_xml = " bus='%s'" % self.bus
        ret += "      <target dev='%s'%s/>\n" % (disknode, bus_xml)

        ro = self.read_only

        if self.device == self.DEVICE_CDROM:
            ro = True
        if self.shareable:
            ret += "      <shareable/>\n"
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

        if self.vol_install:
            return self.vol_install.is_size_conflict()

        if not self.__creating_storage():
            return (False, None)

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

    def is_conflict_disk(self, conn, return_names=False):
        """
        check if specified storage is in use by any other VMs on passed
        connection.

        @param conn: connection to check for collisions on
        @type conn: libvirt.virConnect
        @param return_names: Whether or not to return a list of VM names using
                             the same storage (default = False)
        @type return_names: C{bool}

        @return: True if a collision, False otherwise (list of names if
                 return_names passed)
        @rtype: C{bool}
        """
        if self.vol_object:
            path = self.vol_object.path()
        else:
            path = self.path

        if not path:
            return False

        if not conn:
            conn = self.conn

        check_conflict = self.shareable
        names = self.path_in_use_by(conn, path,
                                    check_conflict=check_conflict)

        ret = False
        if names:
            ret = True
        if return_names:
            ret = names

        return ret

    def _support_selinux(self):
        """
        Return True if we have the requisite libvirt and library support
        for selinux commands
        """
        caps = self._get_caps()
        if (not caps and False):
            #caps.host.secmodel is None or
            #caps.host.secmodel.model != "selinux"):
            # XXX: Libvirt support isn't strictly required, but all the
            #      our label guesses are built with svirt in mind
            return False

        elif self._is_remote():
            return False

        elif not _util.have_selinux():
            # XXX: When libvirt supports changing labels via storage APIs,
            #      this will need changing.
            return False

        elif self.__storage_specified() and self.path:
            try:
                statinfo = os.stat(self.path)
            except:
                return False

            # Not sure if this is even the correct metric for
            # 'Can we change the file context'
            return os.geteuid() in ['0', statinfo.st_uid]

        return True

    def _expected_security_label(self):
        """
        Best guess at what the expected selinux label should be for the disk
        """
        label = None

        # XXX: These are really only approximations in the remote case?
        # XXX: Maybe libvirt should expose the relevant selinux labels in
        #      the capabilities XML?

        if not self._support_selinux():
            pass
        elif self.__no_storage():
            pass
        elif self.read_only:
            label = _util.selinux_readonly_label()
        elif self.shareable:
            # XXX: Should this be different? or do we not care about MLS here?
            label = _util.selinux_rw_label()
        else:
            label = _util.selinux_rw_label()

        return label or ""

    def _security_can_fix(self):
        can_fix = True

        if not self._support_selinux():
            can_fix = False
        elif self.__no_storage():
            can_fix = False
        elif self.type == VirtualDisk.TYPE_BLOCK:
            # Shouldn't change labelling on block devices (though we can)
            can_fix = False
        elif not self.read_only:
            # XXX Leave all other (R/W disk) relabeling up to libvirt/svirt
            # for now
            can_fix = False

        return can_fix

    def _get_target_type(self):
        """
        Returns the suggested disk target prefix (hd, xvd, sd ...) from
        the passed parameters.
        @returns: str prefix, or None if no reasonable guess can be made
        """
        # The upper limits here aren't necessarilly 1024, but let the HV
        # error as appropriate.
        if self.bus == "virtio":
            return ("vd", 1024)
        elif self.bus == "scsi" or self.bus == "usb":
            return ("sd", 1024)
        elif self.bus == "xen":
            return ("xvd", 1024)
        elif self.bus == "fdc" or self.device == self.DEVICE_FLOPPY:
            return ("fd", 2)
        elif self.bus == "ide":
            return ("hd", 4)
        else:
            return (None, None)

    def generate_target(self, skip_targets):
        """
        Generate target device ('hda', 'sdb', etc..) for disk, excluding
        any targets in list 'skip_targets'. Sets self.target, and returns the
        generated value
        @param used_targets: list of targets to exclude
        @type used_targets: C{list}
        @raise ValueError: can't determine target type, no targets available
        @returns generated target
        @rtype C{str}
        """

        # Only use these targets if there are no other options
        except_targets = ["hdc"]

        prefix, maxnode = self._get_target_type()
        if prefix is None:
            raise ValueError(_("Cannot determine device bus/type."))

        # Special case: IDE cdrom should prefer hdc for back compat
        if self.device == self.DEVICE_CDROM and prefix == "hd":
            if "hdc" not in skip_targets:
                self.target = "hdc"
                return self.target

        # Regular scanning
        for i in range(maxnode):
            gen_t = "%s%c" % (prefix, ord('a') + i)
            if gen_t in except_targets:
                continue
            if gen_t not in skip_targets:
                self.target = gen_t
                return self.target

        # Check except_targets for any options
        for t in except_targets:
            if t.startswith(prefix) and t not in skip_targets:
                self.target = t
                return self.target
        raise ValueError(_("No more space for disks of type '%s'" % prefix))


class XenDisk(VirtualDisk):
    """
    Back compat class to avoid ABI break.
    """
    pass
