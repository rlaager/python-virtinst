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

import logging
import libvirt

import _util
import VirtualDevice
from XMLBuilderDomain import _xml_property
from virtinst import _virtinst as _

def _countMACaddr(vms, searchmac):
    if not searchmac:
        return

    def count_cb(ctx):
        c = 0

        for mac in ctx.xpathEval("/domain/devices/interface/mac"):
            macaddr = mac.xpathEval("attribute::address")[0].content
            if macaddr and _util.compareMAC(searchmac, macaddr) == 0:
                c += 1
        return c

    count = 0
    for vm in vms:
        xml = vm.XMLDesc(0)
        count += _util.get_xml_path(xml, func = count_cb)
    return count

class VirtualNetworkInterface(VirtualDevice.VirtualDevice):

    _virtual_device_type = VirtualDevice.VirtualDevice.VIRTUAL_DEV_NET

    TYPE_BRIDGE     = "bridge"
    TYPE_VIRTUAL    = "network"
    TYPE_USER       = "user"
    TYPE_ETHERNET   = "ethernet"
    network_types = [TYPE_BRIDGE, TYPE_VIRTUAL, TYPE_USER, TYPE_ETHERNET]

    def get_network_type_desc(net_type):
        """
        Return human readable description for passed network type
        """
        desc = net_type.capitalize()

        if net_type == VirtualNetworkInterface.TYPE_BRIDGE:
            desc = _("Shared physical device")
        elif net_type ==  VirtualNetworkInterface.TYPE_VIRTUAL:
            desc = _("Virtual networking")
        elif net_type == VirtualNetworkInterface.TYPE_USER:
            desc = _("Usermode networking")

        return desc
    get_network_type_desc = staticmethod(get_network_type_desc)

    def __init__(self, macaddr=None, type=TYPE_BRIDGE, bridge=None,
                 network=None, model=None, conn=None, parsexml=None,
                 parsexmlnode=None):
        VirtualDevice.VirtualDevice.__init__(self, conn, parsexml,
                                             parsexmlnode)

        self._network = None
        self._bridge = None
        self._macaddr = None
        self._type = None
        self._model = None

        if self._is_parse():
            return

        self.type = type
        self.macaddr = macaddr
        self.bridge = bridge
        self.network = network
        self.model = model

        if self.type == self.TYPE_VIRTUAL:
            if network is None:
                raise ValueError, _("A network name was not provided")

    def get_type(self):
        return self._type
    def set_type(self, val):
        if val not in self.network_types:
            raise ValueError, _("Unknown network type %s") % val
        self._type = val
    type = _xml_property(get_type, set_type,
                         xpath="./@type")

    def get_macaddr(self):
        return self._macaddr
    def set_macaddr(self, val):
        _util.validate_macaddr(val)
        self._macaddr = val
    macaddr = _xml_property(get_macaddr, set_macaddr,
                            xpath="./mac/@address")

    def get_network(self):
        return self._network
    def set_network(self, newnet):
        def _is_net_active(netobj):
            # Apparently the 'info' command was never hooked up for
            # libvirt virNetwork python apis.
            if not self.conn:
                return True
            return self.conn.listNetworks().count(netobj.name())

        if newnet is not None and self.conn:
            try:
                net = self.conn.networkLookupByName(newnet)
            except libvirt.libvirtError, e:
                raise ValueError(_("Virtual network '%s' does not exist: %s") \
                                   % (newnet, str(e)))
            if not _is_net_active(net):
                raise ValueError(_("Virtual network '%s' has not been "
                                   "started.") % newnet)

        self._network = newnet
    network = _xml_property(get_network, set_network,
                            xpath="./source/@network")

    def get_bridge(self):
        return self._bridge
    def set_bridge(self, val):
        self._bridge = val
    bridge = _xml_property(get_bridge, set_bridge,
                           xpath="./source/@bridge")

    def get_model(self):
        return self._model
    def set_model(self, val):
        self._model = val
    model = _xml_property(get_model, set_model,
                          xpath="./model/@type")

    def is_conflict_net(self, conn):
        """
        is_conflict_net: determines if mac conflicts with others in system

        returns a two element tuple:
            first element is True if fatal collision occured
            second element is a string description of the collision.

        Non fatal collisions (mac addr collides with inactive guest) will
        return (False, "description of collision")
        """
        if self.macaddr is None:
            return (False, None)

        # Not supported for remote connections yet
        if self._is_remote():
            return (False, None)

        vms, inactive_vm = _util.fetch_all_guests(conn)

        # get the Host's NIC MACaddress
        hostdevs = _util.get_host_network_devices()

        if _countMACaddr(vms, self.macaddr) > 0:
            return (True, _("The MAC address you entered is already in use "
                            "by another active virtual machine."))

        for dev in hostdevs:
            host_macaddr = dev[4]
            if self.macaddr.upper() == host_macaddr.upper():
                return (True, _("The MAC address you entered conflicts with "
                                "a device on the physical host."))

        if _countMACaddr(inactive_vm, self.macaddr) > 0:
            return (False, _("The MAC address you entered is already in use "
                             "by another inactive virtual machine."))

        return (False, None)

    def setup_dev(self, conn=None, meter=None):
        return self.setup(conn)

    def setup(self, conn=None):
        """
        DEPRECATED: Please use setup_dev instead
        """
        if not conn:
            conn = self.conn

        if self.macaddr is None:
            while 1:
                self.macaddr = _util.randomMAC(type=conn.getType().lower())
                if self.is_conflict_net(conn)[1] is not None:
                    continue
                else:
                    break
        else:
            ret, msg = self.is_conflict_net(conn)
            if msg is not None:
                if ret is False:
                    logging.warning(msg)
                else:
                    raise RuntimeError(msg)

        if not self.bridge and self.type == "bridge":
            self.bridge = _util.default_bridge2(self.conn)

    def _get_xml_config(self):
        src_xml = ""
        model_xml = ""
        if self.type == self.TYPE_BRIDGE:
            src_xml =   "      <source bridge='%s'/>\n" % self.bridge
        elif self.type == self.TYPE_VIRTUAL:
            src_xml =   "      <source network='%s'/>\n" % self.network

        if self.model:
            model_xml = "      <model type='%s'/>\n" % self.model

        return "    <interface type='%s'>\n" % self.type + \
               src_xml + \
               "      <mac address='%s'/>\n" % self.macaddr + \
               model_xml + \
               "    </interface>"

# Back compat class to avoid ABI break
class XenNetworkInterface(VirtualNetworkInterface):
    pass
