import gettext

gettext_dir = "::LOCALEDIR::"
gettext_app = "virtinst"

gettext.bindtextdomain(gettext_app, gettext_dir)

def _virtinst(msg):
    return gettext.dgettext(gettext_app, msg)

import util
from Guest import Guest, VirtualDisk, VirtualNetworkInterface, XenGuest, XenDisk, XenNetworkInterface
from FullVirtGuest import FullVirtGuest
from ParaVirtGuest import ParaVirtGuest
from DistroManager import DistroInstaller
from LiveCDInstaller import LiveCDInstaller
from ImageManager import ImageInstaller
