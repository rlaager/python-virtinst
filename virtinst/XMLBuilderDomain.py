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

def _get_xpath_node(ctx, xpath):
    node = ctx.xpathEval(xpath)
    node = (node and node[0] or None)
    return node

def _build_xpath_node(ctx, xpath):
    """
    Build all nodes required to set an xpath. If we have XML <foo/>, and want
    to set xpath /foo/bar/baz@booyeah, we create node 'bar' and 'baz'
    returning the last node created.
    """
    parentpath = ""
    parentnode = None
    retnode = None

    if xpath.count("["):
        raise RuntimeError("Property xpath can not contain conditionals []")

    for nodename in xpath.split("/"):
        if nodename.startswith("@"):
            # No node to create for attributes
            retnode = parentnode
            continue

        parentpath += "/%s" % nodename
        node = _get_xpath_node(ctx, parentpath)
        if node:
            parentnode = node
            continue

        if not parentnode:
            raise RuntimeError("Could not find XML root node")

        retnode = parentnode.newChild(None, nodename, None)

    return retnode


def _xml_property(fget=None, fset=None, fdel=None, doc=None,
                  xpath=None, get_converter=None, set_converter=None):
    """
    Set a XMLBuilder class property that represents a value in the
    <domain> XML. For example

    name = _xml_property(get_name, set_name, xpath="/domain/name")

    When building XML from scratch (virt-install), name is a regular
    class property. When parsing and editting existing guest XML, we
    use the xpath value to map the name property to the underlying XML
    definition.

    @param fget: typical getter function for the property
    @param fset: typical setter function for the property
    @param fdel: typical deleter function for the property
    @param doc: option doc string for the property
    @param xpath: xpath string which maps to the associated property
                  in a typical XML document
    @param get_converter:
    @param set_converter: optional function for converting the property
        value from the virtinst API to the guest XML. For example,
        the Guest.memory API is in MB, but the libvirt domain memory API
        is in KB. So, if xpath is specified, on a 'get' operation we need
        to convert the XML value with int(val) / 1024.
    """
    getter = fget
    setter = fset

    def new_getter(self, *args, **kwargs):
        val = None
        if self._xml_doc:
            if xpath:
                node = _get_xpath_node(self._xml_ctx, xpath)
                if node:
                    val = node.content
                    if val and get_converter:
                        return get_converter(val)

        return fget(self, *args, **kwargs)

    def new_setter(self, val, *args, **kwargs):
        # Do this regardless, for validation purposes
        fset(self, val, *args, **kwargs)

        val = fget(self)
        if set_converter:
            val = set_converter(val)

        attr = None
        if xpath.count("@"):
            ignore, attr = xpath.split("@", 1)

        if self._xml_doc:
            if xpath:
                node = self._xml_ctx.xpathEval(xpath)
                node = (node and node[0] or None)
                if not node:
                    node = _build_xpath_node(self._xml_doc, xpath)

                if attr:
                    node.setProp(attr, str(val))
                else:
                    node.setContent(str(val))


    if fdel:
        # Not tested or supported
        raise RuntimeError("XML deleter not yet supported.")

    if xpath:
        if fget:
            getter = new_getter
        if fset:
            setter = new_setter

    return property(fget=getter, fset=setter, doc=doc)

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

