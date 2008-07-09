#
# Copyright 2008 Sun Microsystems, Inc.  All rights reserved.
# Use is subject to license terms.
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
#

import shutil
import errno
import os

DISK_FORMAT_NONE = 0
DISK_FORMAT_RAW = 1
DISK_FORMAT_VMDK = 2
DISK_FORMAT_VDISK = 3

DISK_TYPE_DISK = 0
DISK_TYPE_CDROM = 1
DISK_TYPE_ISO = 2

disk_suffixes = {
    DISK_FORMAT_RAW: ".img",
    DISK_FORMAT_VMDK: ".vmdk",
    DISK_FORMAT_VDISK: ".vdisk.xml",
}

qemu_formats = {
    DISK_FORMAT_RAW: "raw",
    DISK_FORMAT_VMDK: "vmdk",
    DISK_FORMAT_VDISK: "vdisk",
}

disk_format_names = {
    "none": DISK_FORMAT_NONE,
    "raw": DISK_FORMAT_RAW,
    "vmdk": DISK_FORMAT_VMDK,
    "vdisk": DISK_FORMAT_VDISK,
}

def ensuredirs(path):
    """
    Make sure that all the containing directories of the given file
    path exist.
    """
    try:
        os.makedirs(os.path.dirname(path))
    except OSError, e: 
        if e.errno != errno.EEXIST:
            raise

class disk(object):
    """Definition of an individual disk instance."""

    def __init__(self, path = None, number = 0, format = None, bus = "ide",
        type = DISK_TYPE_DISK):
        self.path = path
        self.format = format
        self.number = number
        self.bus = bus
        self.type = type
        self.clean = []

    def cleanup(self):
        """
        Remove any generated output.
        """

        for path in self.clean:
            if os.path.isfile(path):
                os.remove(path)

        self.clean = []

    def copy_file(self, infile, outfile):
        """Copy an individual file."""
        self.clean += [ outfile ]
        ensuredirs(outfile)
        shutil.copy(infile, outfile)

    def copy(self, indir, outdir, out_format):
        """
        Copy the underlying disk files to a destination, if necessary.
        Return True if we need a further conversion step.
        """

        if os.path.isabs(self.path):
            return False

        need_copy = False
        need_convert = False

        if self.format == out_format:
            need_convert = False
            need_copy = (indir != outdir)
        else:
            if out_format == DISK_FORMAT_NONE:
                need_copy = (indir != outdir)
                need_convert = False
            else:
                need_copy = (indir != outdir and out_format == DISK_FORMAT_VDISK)
                need_convert = True

        if need_copy:
            if out_format == DISK_FORMAT_VDISK:
                stdin, stdout = os.popen2(["/usr/bin/vdiskadm", "import", "-n",
                    "-f", "-t", qemu_formats[self.format],
                    "\"%s\"" % os.path.join(indir, self.path)])
                paths = stdout.readlines()
                stdin.close()
                stdout.close()
                for path in paths:
                    self.copy_file(os.path.join(indir, path),
                        os.path.join(outdir, path))
                return need_convert

            # this is not correct for all VMDK files, but it will have
            # to do for now
            self.copy_file(os.path.join(indir, self.path),
                os.path.join(outdir, self.path))

        return need_convert

    def convert(self, indir, outdir, output_format):
        """
        Convert a disk into the requested format if possible, in the
        given output directory.  Raises RuntimeError or other
        failures.
        """

        out_format = disk_format_names[output_format]
        indir = os.path.normpath(os.path.abspath(indir))
        outdir = os.path.normpath(os.path.abspath(outdir))

        need_convert = self.copy(indir, outdir, out_format)
        if not need_convert:
            return

        relin = self.path
        relout = self.path.replace(disk_suffixes[self.format],
            disk_suffixes[out_format])
        absin = os.path.join(indir, relin)
        absout = os.path.join(outdir, relout)

        ensuredirs(absout)

        if out_format == DISK_FORMAT_VDISK:
            convert_cmd = ("""/usr/bin/vdiskadm import -t %s "%s" "%s" """ %
                (qemu_formats[out_format], absin, absout)) 
        elif out_format == DISK_FORMAT_RAW:
            convert_cmd = ("""qemu-img convert "%s" -O %s "%s" """ %
                (absin, qemu_formats[out_format], absout))
        else:
            raise NotImplementedError("Cannot convert to disk format %s" %
                output_format)

        ret = os.system(convert_cmd)
        if ret != 0:
            raise RuntimeError("Disk conversion failed with exit status %d"
                % ret)

        self.path = relout
        self.format = out_format

def disk_formats():
    """
    Return a list of supported disk formats.
    """
    return disk_format_names.keys()
