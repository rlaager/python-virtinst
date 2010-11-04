#
# Copyright 2006-2009  Red Hat, Inc.
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

import re
import os

import _util
import VirtualDevice
import support
from XMLBuilderDomain import _xml_property
from virtinst import _virtinst as _

class VirtualGraphics(VirtualDevice.VirtualDevice):

    _virtual_device_type = VirtualDevice.VirtualDevice.VIRTUAL_DEV_GRAPHICS

    TYPE_SDL = "sdl"
    TYPE_VNC = "vnc"
    TYPE_RDP = "rdp"
    types = [TYPE_VNC, TYPE_SDL, TYPE_RDP]

    KEYMAP_LOCAL = "local"
    KEYMAP_DEFAULT = "default"
    _special_keymaps = [KEYMAP_LOCAL, KEYMAP_DEFAULT]

    def __init__(self, type=TYPE_VNC, port=-1, listen=None, passwd=None,
                 keymap=KEYMAP_DEFAULT, conn=None, parsexml=None,
                 parsexmlnode=None):

        VirtualDevice.VirtualDevice.__init__(self, conn,
                                             parsexml, parsexmlnode)

        self._type   = None
        self._port   = None
        self._listen = None
        self._passwd = None
        self._keymap = None

        if self._is_parse():
            return

        self.type = type
        self.port = port
        self.keymap = keymap
        self.listen = listen
        self.passwd = passwd

    def _default_keymap(self):
        if (self.conn and
            support.check_conn_support(self.conn,
                                support.SUPPORT_CONN_KEYMAP_AUTODETECT)):
            return None

        return _util.default_keymap()

    def get_type(self):
        return self._type
    def set_type(self, val):
        if val not in self.types:
            raise ValueError(_("Unknown graphics type"))

        self._type = val
    type = _xml_property(get_type, set_type,
                         xpath="./@type")

    def get_keymap(self):
        if self._keymap == self.KEYMAP_DEFAULT:
            return self._default_keymap()
        if self._keymap == self.KEYMAP_LOCAL:
            return _util.default_keymap()
        return self._keymap
    def set_keymap(self, val):
        # At this point, 'None' is a valid value
        if val == None:
            self._keymap = None
            return

        if val in self._special_keymaps:
            self._keymap = val
            return

        if type(val) is not str:
            raise ValueError, _("Keymap must be a string")
        if val.lower() == self.KEYMAP_LOCAL:
            val = _util.default_keymap()
        elif len(val) > 16:
            raise ValueError(_("Keymap must be less than 16 characters"))
        elif re.match("^[a-zA-Z0-9_-]*$", val) == None:
            raise ValueError(_("Keymap can only contain alphanumeric, "
                               "'_', or '-' characters"))

        self._keymap = val
    keymap = _xml_property(get_keymap, set_keymap,
                           xpath="./@keymap")

    def get_port(self):
        return self._port
    def set_port(self, val):
        if val is None:
            val = -1

        try:
            val = int(val)
        except:
            pass

        if (type(val) is not int or
            (val != -1 and (val < 5900 or val > 65535))):
            raise ValueError(_("VNC port must be a number between "
                               "5900 and 65535, or -1 for auto allocation"))
        self._port = val
    port = _xml_property(get_port, set_port,
                         get_converter=int,
                         xpath="./@port")

    def get_listen(self):
        return self._listen
    def set_listen(self, val):
        self._listen = val
    listen = _xml_property(get_listen, set_listen,
                           xpath="./@listen")

    def get_passwd(self):
        return self._passwd
    def set_passwd(self, val):
        self._passwd = val
    passwd = _xml_property(get_passwd, set_passwd,
                           xpath="./@passwd")

    def valid_keymaps(self):
        """
        Return a list of valid keymap values.
        """
        import keytable

        orig_list = keytable.keytable.values()
        sort_list = []

        orig_list.sort()
        for k in orig_list:
            if k not in sort_list:
                sort_list.append(k)

        return sort_list

    def _sdl_config(self):
        if not os.environ.has_key("DISPLAY"):
            raise RuntimeError("No DISPLAY environment variable set.")

        disp  = os.environ["DISPLAY"]
        xauth = os.path.expanduser("~/.Xauthority")

        return """    <graphics type='sdl' display='%s' xauth='%s'/>""" % \
               (disp, xauth)

    def _get_xml_config(self):
        if self._type == self.TYPE_SDL:
            return self._sdl_config()
        keymapxml = ""
        listenxml = ""
        passwdxml = ""
        if self.keymap:
            keymapxml = " keymap='%s'" % self.keymap
        if self.listen:
            listenxml = " listen='%s'" % self._listen
        if self.passwd:
            passwdxml = " passwd='%s'" % self._passwd
        xml = "    <graphics type='vnc' " + \
                   "port='%(port)d'" % { "port" : self._port } + \
                   "%(keymapxml)s"   % { "keymapxml" : keymapxml } + \
                   "%(listenxml)s"   % { "listenxml" : listenxml } + \
                   "%(passwdxml)s"   % { "passwdxml" : passwdxml } + \
                   "/>"
        return xml
