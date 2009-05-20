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
from virtinst import _virtinst as _

class VirtualGraphics(VirtualDevice.VirtualDevice):

    _virtual_device_type = VirtualDevice.VirtualDevice.VIRTUAL_DEV_GRAPHICS

    TYPE_SDL = "sdl"
    TYPE_VNC = "vnc"

    def __init__(self, type=TYPE_VNC, port=-1, listen=None, passwd=None,
                 keymap=None, conn=None):

        VirtualDevice.VirtualDevice.__init__(self, conn=conn)

        if type != self.TYPE_VNC and type != self.TYPE_SDL:
            raise ValueError(_("Unknown graphics type"))

        self._type   = type
        self._port = None
        self._listen = None
        self._passwd = None
        self._keymap = None

        self.set_port(port)
        self.set_keymap(keymap)
        self.set_listen(listen)
        self.set_passwd(passwd)

    def get_type(self):
        return self._type
    type = property(get_type)

    def get_keymap(self):
        return self._keymap
    def set_keymap(self, val):
        if not val:
            val = _util.default_keymap()
        if not val or type(val) != type("string"):
            raise ValueError, _("Keymap must be a string")
        if len(val) > 16:
            raise ValueError, _("Keymap must be less than 16 characters")
        if re.match("^[a-zA-Z0-9_-]*$", val) == None:
            raise ValueError, _("Keymap can only contain alphanumeric, '_', or '-' characters")
        self._keymap = val
    keymap = property(get_keymap, set_keymap)

    def get_port(self):
        return self._port
    def set_port(self, val):
        if val is None:
            val = -1
        elif type(val) is not int \
             or (val != -1 and (val < 5900 or val > 65535)):
            raise ValueError, _("VNC port must be a number between 5900 and 65535, or -1 for auto allocation")
        self._port = val
    port = property(get_port, set_port)

    def get_listen(self):
        return self._listen
    def set_listen(self, val):
        self._listen = val
    listen = property(get_listen, set_listen)

    def get_passwd(self):
        return self._passwd
    def set_passwd(self, val):
        self._passwd = val
    passwd = property(get_passwd, set_passwd)

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

    def get_xml_config(self):
        if self._type == self.TYPE_SDL:
            return self._sdl_config()
        keymapxml = ""
        listenxml = ""
        passwdxml = ""
        if self.keymap:
            keymapxml = " keymap='%s'" % self._keymap
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
