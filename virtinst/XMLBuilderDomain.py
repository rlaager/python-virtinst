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
    if not xml.endswith("\n") and xml.count("\n"):
        xml += "\n"
    return xml

def _get_xpath_node(ctx, xpath, is_multi=False):
    node = ctx.xpathEval(xpath)
    if not is_multi:
        return (node and node[0] or None)
    return node

def _build_xpath_node(ctx, xpath, addnode=None):
    """
    Build all nodes required to set an xpath. If we have XML <foo/>, and want
    to set xpath /foo/bar/baz@booyeah, we create node 'bar' and 'baz'
    returning the last node created.
    """
    parentpath = ""
    parentnode = None

    def make_node(parentnode, newnode):
        # Add the needed parent node, try to preserve whitespace by
        # looking for a starting TEXT node, and copying it
        sib = parentnode.get_last()
        if sib and sib.type == "text" and not sib.content.count("<"):
            content = sib.content
            sib = sib.addNextSibling(libxml2.newText("  "))
            txt = libxml2.newText(content)
        else:
            sib = libxml2.newText("")
            txt = libxml2.newText("\n")
            parentnode.addChild(sib)

        sib.addNextSibling(newnode)
        newnode.addNextSibling(txt)
        return newnode

    for nodename in xpath.split("/"):
        if not nodename:
            continue

        if nodename.startswith("@"):
            nodename = nodename.strip("@")
            parentnode = parentnode.setProp(nodename, "")
            continue

        if not parentpath:
            parentpath = nodename
        else:
            parentpath += "/%s" % nodename

        node = _get_xpath_node(ctx, parentpath)
        if node:
            parentnode = node
            continue

        if not parentnode:
            raise RuntimeError("Could not find XML root node")

        if nodename.count("["):
            nodename = nodename[:nodename.index("[")]

        newnode = libxml2.newNode(nodename)
        parentnode = make_node(parentnode, newnode)

    if addnode:
        parentnode = make_node(parentnode, addnode)

    return parentnode

def _remove_xpath_node(ctx, xpath, dofree=True):
    """
    Remove an XML node tree if it has no content
    """
    curxpath = xpath

    while curxpath:
        is_orig = (curxpath == xpath)
        node = _get_xpath_node(ctx, curxpath)
        if curxpath.count("/"):
            curxpath, ignore = curxpath.rsplit("/", 1)
        else:
            curxpath = None

        if not node:
            continue
        
        if node.type not in ["attribute", "element"]:
            continue

        if node.type == "element" and (node.children or node.properties):
            # Only do a deep unlink if it was the original requested path
            if not is_orig:
                continue

        # Look for preceding whitespace and remove it
        white = node.get_prev()
        if white and white.type == "text" and not white.content.count("<"):
            white.unlinkNode()
            white.freeNode()

        node.unlinkNode()
        if dofree:
            node.freeNode()


def _xml_property(fget=None, fset=None, fdel=None, doc=None,
                  xpath=None, get_converter=None, set_converter=None,
                  xml_get_xpath=None, xml_set_xpath=None,
                  xml_set_list=None, is_bool=False, is_multi=False):
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
    @param xml_get_xpath:
    @param xml_set_xpath: Not all props map cleanly to a static xpath.
        This allows passing functions which generate an xpath for getting
        or setting.
    @param xml_set_list: Return a list of xpaths to set for each value
                         in the val list
    @param is_bool: Whether this is a boolean property in the XML
    @param is_multi: Whether data is coming multiple or a single node
    """
    def new_getter(self, *args, **kwargs):
        val = None
        getval = fget(self, *args, **kwargs)
        if not self._xml_node:
            return getval

        usexpath = xpath
        if xml_get_xpath:
            usexpath = xml_get_xpath(self)

        if usexpath is None:
            return getval
    
        nodes = _util.listify(_get_xpath_node(self._xml_ctx,
                                              usexpath, is_multi))
        if nodes:
            ret = []
            for node in nodes:
                val = node.content
                if get_converter:
                    val = get_converter(val)
                elif is_bool:
                    val = True

                if not is_multi:
                    return val
                # If user is querying multiple nodes, return a list of results
                ret.append(val)
            return ret

        elif is_bool:
            return False

        return getval

    def new_setter(self, val, *args, **kwargs):
        # Do this regardless, for validation purposes
        fset(self, val, *args, **kwargs)

        if not self._xml_node:
            return

        # Convert from API value to XML value
        val = fget(self)
        if set_converter:
            val = set_converter(val)

        nodexpath = xpath
        if xml_set_xpath:
            nodexpath = xml_set_xpath(self)

        if nodexpath is None:
            return

        nodes = _util.listify(_get_xpath_node(self._xml_ctx,
                                              nodexpath, is_multi))

        xpath_list = nodexpath
        if xml_set_list:
            xpath_list = xml_set_list(self) 
            
        node_map = map(lambda x, y, z: (x, y, z),
                       _util.listify(nodes),
                       _util.listify(val),
                       _util.listify(xpath_list))

        for node, val, usexpath in node_map:
            if node:
                usexpath = node.nodePath()

            if val not in [None, False]:
                if not node:
                    node = _build_xpath_node(self._xml_node, usexpath)

                if val is True:
                    # Boolean property, creating the node is enough
                    pass
                else:
                    node.setContent(str(val))
            else:
                _remove_xpath_node(self._xml_node, usexpath)


    if fdel:
        # Not tested
        raise RuntimeError("XML deleter not yet supported.")

    return property(fget=new_getter, fset=new_setter, doc=doc)

class XMLBuilderDomain(object):
    """
    Base for all classes which build or parse domain XML
    """

    def __init__(self, conn=None, parsexml=None, parsexmlnode=None):
        """
        Initialize state

        @param conn: libvirt connection to validate device against
        @type conn: virConnect
        @param parsexml: Optional XML string to parse
        @type parsexml: C{str}
        @param parsexmlnode: Option xpathNode to use
        """
        if conn:
            if not isinstance(conn, libvirt.virConnect):
                raise ValueError, _("'conn' must be a virConnect instance")
        self._conn = conn

        self.__caps = None
        self.__remote = None
        self._xml_node = None
        self._xml_ctx = None

        if self.conn:
            self.__remote = _util.is_uri_remote(self.conn.getURI())

        if parsexml or parsexmlnode:
            self._parsexml(parsexml, parsexmlnode)

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

    def _is_parse(self):
        return bool(self._xml_node or self._xml_ctx)

    def set_xml_node(self, node):
        self._parsexml(None, node)

    def get_xml_node_path(self):
        if self._xml_node:
            return self._xml_node.nodePath()
        return None

    def _add_child_node(self, parent_xpath, newnode):
        ret = _build_xpath_node(self._xml_ctx, parent_xpath, newnode)
        return ret

    def _remove_child_xpath(self, xpath):
        _remove_xpath_node(self._xml_ctx, xpath, dofree=False)
        self._set_xml_context()

    def _set_xml_context(self):
        doc = self._xml_node.doc
        ctx = doc.xpathNewContext()
        ctx.setContextNode(self._xml_node)
        self._xml_ctx = ctx

    def _parsexml(self, xml, node):
        if xml:
            self._xml_node = libxml2.parseDoc(xml).children
        else:
            self._xml_node = node

        self._set_xml_context()

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
        if self._xml_node:
            return _sanitize_libxml_xml(self._xml_node.serialize())

        return self._get_xml_config(*args, **kwargs)

