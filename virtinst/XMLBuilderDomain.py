#
# Base class for all VM devices
#
# Copyright 2008  Red Hat, Inc.
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

import libvirt
import libxml2

import CapabilitiesParser
import _util
from virtinst import _virtinst as _

def _sanitize_libxml_xml(xml):
    # Strip starting <?...> line
    if xml.startswith("<?"):
        ignore, xml = xml.split("\n", 1)
    return xml

class XMLBuilderDomain(object):
    """
    Base for all classes which build or parse domain XML
    """

    def __init__(self, conn=None, parsexml=None):
        """
        Initialize state

        @param conn: libvirt connection to validate device against
        @type conn: virConnect
        @param parsexml: Optional XML string to parse
        @type parsexml: C{str}
        """
        if conn:
            if not isinstance(conn, libvirt.virConnect):
                raise ValueError, _("'conn' must be a virConnect instance")
        self._conn = conn

        self.__caps = None
        self.__remote = None
        self._xml_doc = None
        self._xml_ctx = None

        if self.conn:
            self.__remote = _util.is_uri_remote(self.conn.getURI())

        if parsexml:
            self._parsexml(parsexml)

    def get_conn(self):
        return self._conn
    def set_conn(self, val):
        if not isinstance(val, libvirt.virConnect):
            raise ValueError(_("'conn' must be a virConnect instance."))
        self._conn = val
    conn = property(get_conn, set_conn)

    def _get_caps(self):
        if not self.__caps and self.conn:
            self.__caps = CapabilitiesParser.parse(self.conn.getCapabilities())
        return self.__caps

    def _is_remote(self):
        return bool(self.__remote)

    def _get_uri(self):
        if self.conn:
            return self.conn.getURI()
        return None

    def _check_bool(self, val, name):
        if val not in [True, False]:
            raise ValueError, _("'%s' must be True or False" % name)

    def _check_str(self, val, name):
        if type(val) is not str:
            raise ValueError, _("'%s' must be a string, not '%s'." %
                                (name, type(val)))

    def _parsexml(self, xml):
        doc = libxml2.parseDoc(xml)
        ctx = doc.xpathNewContext()

        self._xml_doc = doc
        self._xml_ctx = ctx

    def _get_xml_config(self):
        """
        Internal XML building function. Must be overwritten by subclass
        """
        raise NotImplementedError()

    def get_xml_config(self, *args, **kwargs):
        """
        Construct and return object xml

        @return: object xml representation as a string
        @rtype: str
        """
        if self._xml_doc:
            return _sanitize_libxml_xml(self._xml_doc.serialize())

        return self._get_xml_config(*args, **kwargs)

