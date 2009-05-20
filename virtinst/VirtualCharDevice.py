#
# Copyright 2009  Red Hat, Inc.
# Cole Robinson <crobinso@redhat.com>
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

import VirtualDevice
from xml.sax.saxutils import escape as xml_escape

from virtinst import _virtinst as _

class VirtualCharDevice(VirtualDevice.VirtualDevice):
    """
    Base class for all character devices. Shouldn't be instantiated
    directly.
    """

    DEV_SERIAL   = "serial"
    DEV_PARALLEL = "parallel"
    DEV_CONSOLE  = "console"
    dev_types    = [ DEV_SERIAL, DEV_PARALLEL, DEV_CONSOLE ]

    CHAR_PTY    = "pty"
    CHAR_DEV    = "dev"
    CHAR_STDIO  = "stdio"
    CHAR_PIPE   = "pipe"
    CHAR_FILE   = "file"
    CHAR_VC     = "vc"
    CHAR_NULL   = "null"
    CHAR_TCP    = "tcp"
    CHAR_UDP    = "udp"
    CHAR_UNIX   = "unix"
    char_types  = [ CHAR_PTY, CHAR_DEV, CHAR_STDIO, CHAR_FILE, CHAR_VC,
                    CHAR_PIPE, CHAR_NULL, CHAR_TCP, CHAR_UDP, CHAR_UNIX ]

    CHAR_MODE_SERVER = "connect"
    CHAR_MODE_BIND = "bind"
    char_modes = [ CHAR_MODE_SERVER, CHAR_MODE_BIND ]

    CHAR_WIRE_MODE_RAW = "raw"
    CHAR_WIRE_MODE_TELNET = "telnet"
    char_wire_modes = [ CHAR_WIRE_MODE_RAW, CHAR_WIRE_MODE_TELNET ]

    # 'char_type' of class (must be properly set in subclass)
    _char_type = None

    def get_dev_instance(conn, dev_type, char_type):
        """
        Set up the class attributes for the passed char_type
        """

        # By default, all the possible parameters are enabled for the
        # device class. We go through here and del() all the ones that
        # don't apply. This is kind of whacky, but it's nice to to
        # allow an API user to just use hasattr(obj, paramname) to see
        # what parameters apply, instead of having to hardcode all that
        # information.
        if dev_type == VirtualCharDevice.DEV_CONSOLE:
            return VirtualConsoleDevice(conn)

        if char_type == VirtualCharDevice.CHAR_PTY:
            c = VirtualCharPtyDevice
        elif char_type == VirtualCharDevice.CHAR_STDIO:
            c = VirtualCharStdioDevice
        elif char_type == VirtualCharDevice.CHAR_NULL:
            c = VirtualCharNullDevice
        elif char_type == VirtualCharDevice.CHAR_VC:
            c = VirtualCharVcDevice
        elif char_type == VirtualCharDevice.CHAR_DEV:
            c = VirtualCharVcDevice
        elif char_type == VirtualCharDevice.CHAR_FILE:
            c = VirtualCharFileDevice
        elif char_type == VirtualCharDevice.CHAR_PIPE:
            c = VirtualCharPipeDevice
        elif char_type == VirtualCharDevice.CHAR_TCP:
            c = VirtualCharTcpDevice
        elif char_type == VirtualCharDevice.CHAR_UNIX:
            c = VirtualCharUnixDevice
        elif char_type == VirtualCharDevice.CHAR_UDP:
            c = VirtualCharUdpDevice
        else:
            raise ValueError(_("Unknown character device type '%s'.") %
                             char_type)

        return c(conn, dev_type)
    get_dev_instance = staticmethod(get_dev_instance)

    def __init__(self, conn, dev_type):
        if dev_type not in self.dev_types:
            raise ValueError(_("Unknown character device type '%s'") % dev_type)
        self._dev_type = dev_type
        self._virtual_device_type = self._dev_type

        VirtualDevice.VirtualDevice.__init__(self, conn)

        if not self._char_type:
            raise ValueError("Must not be instantiated through a subclass.")

        if self._char_type not in self.char_types:
            raise ValueError(_("Unknown character device type '%s'")
                             % self._char_type)

        # Init
        self._source_path = None
        self._source_mode = self.CHAR_MODE_BIND
        self._source_host = None
        self._source_port = None
        self._connect_host = None
        self._connect_port = None
        self._wire_mode = self.CHAR_WIRE_MODE_RAW

    # Properties
    def get_char_type(self):
        return self._char_type
    char_type = property(get_char_type)


    # Properties functions used by the various subclasses
    def get_source_path(self):
        return self._source_path
    def set_source_path(self, val):
        self._source_path = val

    def get_source_mode(self):
        return self._source_mode
    def set_source_mode(self, val):
        if val not in self.char_modes:
            raise ValueError(_("Unknown character mode '%s'.") % val)
        self._source_mode = val

    def get_source_host(self):
        return self._source_host
    def set_source_host(self, val):
        self._source_host = val

    def get_source_port(self):
        return self._source_port
    def set_source_port(self, val):
        self._source_port = int(val)

    def get_connect_host(self):
        return self._connect_host
    def set_connect_host(self, val):
        self._connect_host = val

    def get_connect_port(self):
        return self._connect_port
    def set_connect_port(self, val):
        self._connect_port = int(val)

    def get_wire_mode(self):
        return self._wire_mode
    def set_wire_mode(self, val):
        if val not in self.char_wire_modes:
            raise ValueError(_("Unknown wire mode '%s'.") % val)
        self._wire_mode = val

    # XML building helpers
    def _char_empty_xml(self):
        """
        Provide source xml for devices with no params (null, stdio, ...)
        """
        return ""

    def _char_file_xml(self):
        """
        Provide source xml for devs that require only a patch (dev, pipe)
        """
        file_xml = ""
        mode_xml = ""
        if self.source_path:
            file_xml = " path='%s'" % xml_escape(self.source_path)
        else:
            raise ValueError(_("A source path is required for character "
                               "device type '%s'" % self.char_type))

        if hasattr(self, "source_mode") and self.source_mode:
            mode_xml = " mode='%s'" % xml_escape(self.source_mode)

        xml = "      <source%s%s/>\n" % (mode_xml, file_xml)
        return xml

    def _char_xml(self):
        raise NotImplementedError("Must be implemented in subclass.")

    def get_xml_config(self):
        xml  = "    <%s type='%s'" % (self._dev_type, self._char_type)
        char_xml = self._char_xml()
        if char_xml:
            xml += ">\n%s" % char_xml
            xml += "    </%s>" % self._dev_type
        else:
            xml += "/>"
        return xml

# Back compat class for building a simple PTY 'console' element
class VirtualConsoleDevice(VirtualCharDevice):
    _char_xml = VirtualCharDevice._char_empty_xml
    _char_type = VirtualCharDevice.CHAR_PTY

    def __init__(self, conn):
        VirtualCharDevice.__init__(self, conn, VirtualCharDevice.DEV_CONSOLE)

# Classes for each device 'type'

class VirtualCharPtyDevice(VirtualCharDevice):
    _char_type = VirtualCharDevice.CHAR_PTY
    _char_xml = VirtualCharDevice._char_empty_xml
class VirtualCharStdioDevice(VirtualCharDevice):
    _char_type = VirtualCharDevice.CHAR_STDIO
    _char_xml = VirtualCharDevice._char_empty_xml
class VirtualCharNullDevice(VirtualCharDevice):
    _char_type = VirtualCharDevice.CHAR_NULL
    _char_xml = VirtualCharDevice._char_empty_xml
class VirtualCharVcDevice(VirtualCharDevice):
    _char_type = VirtualCharDevice.CHAR_VC
    _char_xml = VirtualCharDevice._char_empty_xml

class VirtualCharDevDevice(VirtualCharDevice):
    _char_type = VirtualCharDevice.CHAR_DEV
    _char_xml = VirtualCharDevice._char_file_xml
    source_path = property(VirtualCharDevice.get_source_path,
                           VirtualCharDevice.set_source_path,
                           doc=_("Host character device to attach to guest."))
class VirtualCharPipeDevice(VirtualCharDevice):
    _char_type = VirtualCharDevice.CHAR_PIPE
    _char_xml = VirtualCharDevice._char_file_xml
    source_path = property(VirtualCharDevice.get_source_path,
                           VirtualCharDevice.set_source_path,
                           doc=_("Named pipe to use for input and output."))
class VirtualCharFileDevice(VirtualCharDevice):
    _char_type = VirtualCharDevice.CHAR_FILE
    _char_xml = VirtualCharDevice._char_file_xml
    source_path = property(VirtualCharDevice.get_source_path,
                           VirtualCharDevice.set_source_path,
                           doc=_("File path to record device output."))

class VirtualCharUnixDevice(VirtualCharDevice):
    _char_type = VirtualCharDevice.CHAR_UNIX
    _char_xml = VirtualCharDevice._char_file_xml

    source_mode = property(VirtualCharDevice.get_source_mode,
                           VirtualCharDevice.set_source_mode,
                           doc=_("Target connect/listen mode."))
    source_path = property(VirtualCharDevice.get_source_path,
                           VirtualCharDevice.set_source_path,
                           doc=_("Unix socket path."))

class VirtualCharTcpDevice(VirtualCharDevice):
    _char_type = VirtualCharDevice.CHAR_TCP

    source_mode = property(VirtualCharDevice.get_source_mode,
                           VirtualCharDevice.set_source_mode,
                           doc=_("Target connect/listen mode."))
    source_host = property(VirtualCharDevice.get_source_host,
                           VirtualCharDevice.set_source_host,
                           doc=_("Address to connect/listen to."))
    source_port = property(VirtualCharDevice.get_source_port,
                           VirtualCharDevice.set_source_port,
                           doc=_("Port on target host to connect/listen to."))
    wire_mode = property(VirtualCharDevice.get_wire_mode,
                         VirtualCharDevice.set_wire_mode,
                         doc=_("Format used when sending data."))

    def _char_xml(self):
        if not self.source_host and not self.source_port:
            raise ValueError(_("A host and port must be specified."))

        xml = ("      <source mode='%s' host='%s' service='%s'/>\n" %
               (self.source_mode, self.source_host, self.source_port))
        xml += "      <wire type='%s'/>\n" % self.wire_mode
        return xml

class VirtualCharUdpDevice(VirtualCharDevice):
    _char_type = VirtualCharDevice.CHAR_UDP

    source_host = property(VirtualCharDevice.get_source_host,
                           VirtualCharDevice.set_source_host,
                           doc=_("Address to connect/listen to."))
    source_port = property(VirtualCharDevice.get_source_port,
                           VirtualCharDevice.set_source_port,
                           doc=_("Port on target host to connect/listen to."))
    connect_host = property(VirtualCharDevice.get_connect_host,
                            VirtualCharDevice.set_connect_host,
                            doc=_("Host address to send output to."))
    connect_port = property(VirtualCharDevice.get_connect_port,
                            VirtualCharDevice.set_connect_port,
                            doc=_("Host port to send output to."))

    # XXX: UDP: Only source _connect_ port required?
    def _char_xml(self):
        if not self.connect_port:
            raise ValueError(_("A connection port must be specified."))

        xml = ""
        source_xml = ""
        source_host_xml = ""
        source_port_xml = ""
        connect_host_xml = ""

        if self.source_host:
            source_host_xml = " host='%s'" % self.source_host
        if self.source_port:
            source_port_xml = " service='%s'" % self.source_port
        if self.connect_host:
            connect_host_xml = " host='%s'" % self.connect_host

        if self.source_host or self.source_port:
            source_xml = ("      <source mode='bind'%s%s/>\n" %
                          (source_host_xml, source_port_xml))

        xml += source_xml
        xml += ("      <source mode='connect'%s service='%s'/>\n" %
                (connect_host_xml, self.connect_port))
        return xml
