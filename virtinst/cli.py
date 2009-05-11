#
# Utility functions for the command line drivers
#
# Copyright 2006-2007  Red Hat, Inc.
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

import os, sys
import logging
import logging.handlers
import locale
from optparse import OptionValueError, OptionParser

import libvirt
import _util
import virtinst
from virtinst import CapabilitiesParser, VirtualNetworkInterface, \
                     VirtualGraphics, VirtualAudio, User
from virtinst import _virtinst as _

MIN_RAM = 64
force = False
doprompt = True

class VirtOptionParser(OptionParser):
    '''Subclass to get print_help to work properly with non-ascii text'''

    def _get_encoding(self, f):
        encoding = getattr(f, "encoding", None)
        if not encoding:
            (dummy, encoding) = locale.getlocale()
        return encoding

    def print_help(self, file=None):
        if file is None:
            file = sys.stdout
        encoding = self._get_encoding(file)
        file.write(self.format_help().encode(encoding, "replace"))

#
# Setup helpers
#

def setupLogging(appname, debug=False):
    # set up logging
    vi_dir = os.path.expanduser("~/.virtinst")
    if not os.access(vi_dir,os.W_OK):
        try:
            os.mkdir(vi_dir)
        except IOError, e:
            raise RuntimeError, "Could not create %d directory: " % vi_dir, e

    dateFormat = "%a, %d %b %Y %H:%M:%S"
    fileFormat = "[%(asctime)s " + appname + " %(process)d] %(levelname)s (%(module)s:%(lineno)d) %(message)s"
    streamDebugFormat = "%(asctime)s %(levelname)-8s %(message)s"
    streamErrorFormat = "%(levelname)-8s %(message)s"
    filename = os.path.join(vi_dir, appname + ".log")

    rootLogger = logging.getLogger()
    rootLogger.setLevel(logging.DEBUG)
    fileHandler = logging.handlers.RotatingFileHandler(filename, "a",
                                                       1024*1024, 5)

    fileHandler.setFormatter(logging.Formatter(fileFormat,
                                               dateFormat))
    rootLogger.addHandler(fileHandler)

    streamHandler = logging.StreamHandler(sys.stderr)
    if debug:
        streamHandler.setLevel(logging.DEBUG)
        streamHandler.setFormatter(logging.Formatter(streamDebugFormat,
                                                     dateFormat))
    else:
        streamHandler.setLevel(logging.ERROR)
        streamHandler.setFormatter(logging.Formatter(streamErrorFormat))
    rootLogger.addHandler(streamHandler)

    # Register libvirt handler
    def libvirt_callback(ignore, err):
        if err[3] != libvirt.VIR_ERR_ERROR:
            # Don't log libvirt errors: global error handler will do that
            logging.warn("Non-error from libvirt: '%s'" % err[2])
    libvirt.registerErrorHandler(f=libvirt_callback, ctx=None)

    # Register python error handler to log exceptions
    def exception_log(type, val, tb):
        import traceback
        s = traceback.format_exception(type, val, tb)
        logging.exception("".join(s))
        sys.__excepthook__(type, val, tb)
    sys.excepthook = exception_log

    # Log the app command string
    logging.debug("Launched with command line:\n%s" % " ".join(sys.argv))

def fail(msg):
    """Convenience function when failing in cli app"""
    logging.error(msg)
    _util.log_exception()
    _fail_exit()

def _fail_exit():
    sys.exit(1)

def nice_exit():
    print _("Exiting at user request.")
    sys.exit(0)

def getConnection(connect):
    if not User.current().has_priv(User.PRIV_CREATE_DOMAIN, connect):
        fail(_("Must be root to create Xen guests"))
    if connect is None:
        fail(_("Could not find usable default libvirt connection."))

    logging.debug("Using libvirt URI '%s'" % connect)
    return libvirt.open(connect)

#
# Prompting
#

def set_force(val=True):
    global force
    force = val

def set_prompt(prompt=True):
    # Set whether we allow prompts, or fail if a prompt pops up
    global doprompt
    doprompt = prompt

def is_prompt():
    return doprompt

def prompt_for_input(noprompt_err, prompt = "", val = None, failed=False):
    if val is not None:
        return val

    if force or not is_prompt():
        if failed:
            # We already failed validation in a previous function, just exit
            _fail_exit()

        msg = noprompt_err
        if not force and not msg.count("--prompt"):
            # msg wasn't already appended to from yes_or_no
            msg = noprompt_err + " " + _("(use --prompt to run interactively)")
        fail(msg)

    print prompt + " ",
    return sys.stdin.readline().strip()

def yes_or_no(s):
    s = s.lower()
    if s in ("y", "yes", "1", "true", "t"):
        return True
    elif s in ("n", "no", "0", "false", "f"):
        return False
    raise ValueError, "A yes or no response is required"

def prompt_for_yes_or_no(warning, question):
    """catches yes_or_no errors and ensures a valid bool return"""
    if force:
        logging.debug("Forcing return value of True to prompt '%s'")
        return True

    errmsg = warning + _(" (Use --prompt or --force to override)")

    while 1:
        inp = prompt_for_input(errmsg, warning + question, None)
        try:
            res = yes_or_no(inp)
            break
        except ValueError, e:
            logging.error(e)
            continue
    return res

# Prompt the user with 'prompt_txt' for a value. Set 'obj'.'param_name'
# to the entered value. If it errors, use 'err_txt' to print a error
# message, and then re prompt.
def prompt_loop(prompt_txt, noprompt_err, passed_val, obj, param_name,
                err_txt="%s", func=None):
    failed = False
    while True:
        passed_val = prompt_for_input(noprompt_err, prompt_txt, passed_val,
                                      failed)
        try:
            if func:
                return func(passed_val)
            setattr(obj, param_name, passed_val)
            break
        except (ValueError, RuntimeError), e:
            logging.error(err_txt % e)
            passed_val = None
            failed = True

# Register vnc + sdl options for virt-install and virt-image
def graphics_option_group(parser):
    from optparse import OptionGroup

    vncg = OptionGroup(parser, _("Graphics Configuration"))
    vncg.add_option("", "--vnc", action="store_true", dest="vnc",
                    help=_("Use VNC for graphics support"))
    vncg.add_option("", "--vncport", type="int", dest="vncport",
                    help=_("Port to use for VNC"))
    vncg.add_option("", "--vnclisten", type="string", dest="vnclisten",
                    help=_("Address to listen on for VNC connections."))
    vncg.add_option("-k", "--keymap", type="string", dest="keymap",
                    action="callback", callback=check_before_store,
                    help=_("set up keymap for the VNC console"))
    vncg.add_option("", "--sdl", action="store_true", dest="sdl",
                    help=_("Use SDL for graphics support"))
    vncg.add_option("", "--nographics", action="store_true",
                    help=_("Don't set up a graphical console for the guest."))
    return vncg

# Specific function for disk prompting. Returns a validated VirtualDisk
# device.
#
def disk_prompt(prompt_txt, arg_dict, warn_overwrite=False, prompt_size=True):

    retry_path = True
    conn = arg_dict.get("conn")
    passed_path = arg_dict.get("path")
    size = arg_dict.get("size")

    no_path_needed = (bool(arg_dict.get("volInstall")) or
                      bool(arg_dict.get("volName")))

    while 1:
        if not retry_path:
            passed_path = None
            size = None
        retry_path = False

        msg = None
        patherr = _("A disk path must be specified.")
        if not prompt_txt:
            msg = _("What would you like to use as the disk (file path)?")
            if not size is None:
                msg = _("Please enter the path to the file you would like to "
                        "use for storage. It will have size %sGB.") %(size,)

        if not no_path_needed:
            path = prompt_for_input(patherr, prompt_txt or msg, passed_path)
        else:
            path = None
        arg_dict["path"] = path

        sizeerr = _("A size must be specified for non-existent disks.")
        if path and not size and prompt_size:
            size_prompt = _("How large would you like the disk (%s) to "
                            "be (in gigabytes)?") % path

            try:
                if not _util.disk_exists(conn, path):
                    size = prompt_loop(size_prompt, sizeerr, size, None, None,
                                       func=float)
            except Exception, e:
                # Path is probably bogus, raise the error
                logging.error(str(e))
                continue
        arg_dict["size"] = size

        # Build disk object for validation
        try:
            dev = virtinst.VirtualDisk(**arg_dict)
        except ValueError, e:
            if is_prompt():
                logging.error(e)
                continue
            else:
                fail(_("Error with storage parameters: %s" % str(e)))

        askmsg = _("Do you really want to use this disk (yes or no)")

        # Prompt if disk file already exists and preserve mode is not used
        if warn_overwrite and os.path.exists(dev.path):
            msg = (_("This will overwrite the existing path '%s'!\n" %
                   dev.path))
            if not prompt_for_yes_or_no(msg, askmsg):
                continue

        # Check disk conflicts
        if dev.is_conflict_disk(conn) is True:
            msg = (_("Disk %s is already in use by another guest!\n" %
                   dev.path))
            if not prompt_for_yes_or_no(msg, askmsg):
                continue

        isfatal, errmsg = dev.is_size_conflict()
        if isfatal:
            fail(errmsg)
        elif errmsg:
            if not prompt_for_yes_or_no(errmsg, askmsg):
                continue

        # Passed all validation, return path
        return dev
#
# Ask for attributes
#

def get_name(name, guest):
    prompt_txt = _("What is the name of your virtual machine?")
    err_txt = _("A name is required for the virtual machine.")
    prompt_loop(prompt_txt, err_txt, name, guest, "name")

def get_memory(memory, guest):
    prompt_txt = _("How much RAM should be allocated (in megabytes)?")
    err_txt = _("Memory amount is required for the virtual machine.")
    def check_memory(mem):
        mem = int(mem)
        if mem < MIN_RAM:
            raise ValueError(_("Installs currently require %d megs "
                               "of RAM.") % MIN_RAM)
        guest.memory = mem
    prompt_loop(prompt_txt, err_txt, memory, guest, "memory",
                func=check_memory)

def get_uuid(uuid, guest):
    if uuid:
        try:
            guest.uuid = uuid
        except ValueError, e:
            fail(e)

def get_vcpus(vcpus, check_cpu, guest, conn):

    if check_cpu:
        hostinfo = conn.getInfo()
        cpu_num = hostinfo[4] * hostinfo[5] * hostinfo[6] * hostinfo[7]
        if not vcpus <= cpu_num:
            msg = _("You have asked for more virtual CPUs (%d) than there "
                    "are physical CPUs (%d) on the host. This will work, "
                    "but performance will be poor. ") % (vcpus, cpu_num)
            askmsg = _("Are you sure? (yes or no)")

            if not prompt_for_yes_or_no(msg, askmsg):
                nice_exit()

    if vcpus is not None:
        try:
            guest.vcpus = vcpus
        except ValueError, e:
            fail(e)

def get_cpuset(cpuset, mem, guest, conn):
    if cpuset and cpuset != "auto":
        guest.cpuset = cpuset
    elif cpuset == "auto":
        caps = CapabilitiesParser.parse(conn.getCapabilities())
        if caps.host.topology is None:
            logging.debug("No topology section in caps xml. Skipping cpuset")
            return

        cells = caps.host.topology.cells
        if len(cells) <= 1:
            logging.debug("Capabilities only show <= 1 cell. Not NUMA capable")
            return

        cell_mem = conn.getCellsFreeMemory(0, len(cells))
        cell_id = -1
        mem = mem * 1024
        for i in range(len(cells)):
            if cell_mem[i] > mem and len(cells[i].cpus) != 0:
                # Find smallest cell that fits
                if cell_id < 0 or cell_mem[i] < cell_mem[cell_id]:
                    cell_id = i
        if cell_id < 0:
            logging.debug("Could not find any usable NUMA cell/cpu combinations. Not setting cpuset.")
            return

        # Build cpuset
        cpustr = ""
        for cpu in cells[cell_id].cpus:
            if cpustr != "":
                cpustr += ","
            cpustr += str(cpu.id)
        logging.debug("Auto cpuset is: %s" % cpustr)
        guest.cpuset = cpustr
    return

def get_network(mac, network, guest, model=None):
    if mac == "RANDOM":
        mac = None
    if network == "user":
        n = VirtualNetworkInterface(mac, type="user",
                                    conn=guest.conn, model=model)
    elif network[0:6] == "bridge":
        n = VirtualNetworkInterface(mac, type="bridge", bridge=network[7:],
                                    conn=guest.conn, model=model)
    elif network[0:7] == "network":
        n = VirtualNetworkInterface(mac, type="network", network=network[8:],
                                    conn=guest.conn, model=model)
    else:
        fail(_("Unknown network type ") + network)
    guest.nics.append(n)

def parse_network_opts(networks):
    nets = []
    models = []

    for network in networks:
        opts = { 'model': None }
        args = network.split(",")
        nets.append(args[0])

        for opt in args[1:]:
            opt_type = None
            opt_val = None
            if opt.count("="):
                opt_type, opt_val = opt.split("=", 1)
                opts[opt_type.lower()] = opt_val.lower()

        for opt_type in opts:
            if opt_type == "model":
                models.append(opts[opt_type])
            else:
                fail(_("Unknown '%s' value '%s'") % (opt_type, opt_val))

    return (nets, models)

def digest_networks(conn, macs, bridges, networks, nics = 0):
    def listify(l):
        if l is None:
            return []
        elif type(l) != list:
            return [ l ]
        else:
            return l

    macs     = listify(macs)
    bridges  = listify(bridges)
    networks = listify(networks)

    if bridges and networks:
        fail(_("Cannot mix both --bridge and --network arguments"))

    if bridges:
        networks = map(lambda b: "bridge:" + b, bridges)

    (networks, models) = parse_network_opts(networks)

    # With just one mac, create a default network if one is not
    # specified.
    if len(macs) == 1 and len(networks) == 0:
        if User.current().has_priv(User.PRIV_CREATE_NETWORK, conn.getURI()):
            net = _util.default_network(conn)
            networks.append(net[0] + ":" + net[1])
        else:
            networks.append("user")

    # ensure we have less macs then networks. Auto fill in the remaining
    # macs
    if len(macs) > len(networks):
        fail(_("Need to pass equal numbers of networks & mac addresses"))
    else:
        for dummy in range (len(macs),len(networks)):
            macs.append(None)


    # Create extra networks up to the number of nics requested
    if len(macs) < nics:
        for dummy in range(len(macs),nics):
            if User.current().has_priv(User.PRIV_CREATE_NETWORK, conn.getURI()):
                net = _util.default_network(conn)
                networks.append(net[0] + ":" + net[1])
            else:
                networks.append("user")
            macs.append(None)

    return (macs, networks, models)

def get_graphics(vnc, vncport, vnclisten, nographics, sdl, keymap, guest):
    if (vnc and nographics) or \
       (vnc and sdl) or \
       (sdl and nographics):
        raise ValueError, _("Can't specify more than one of VNC, SDL, "
                            "or --nographics")

    if not (vnc or nographics or sdl):
        if "DISPLAY" in os.environ.keys():
            logging.debug("DISPLAY is set: graphics defaulting to VNC.")
            vnc = True
        else:
            logging.debug("DISPLAY is not set: defaulting to nographics.")
            nographics = True

    if nographics is not None:
        guest.graphics_dev = None
        return
    if sdl is not None:
        guest.graphics_dev = VirtualGraphics(type=VirtualGraphics.TYPE_SDL)
        return
    if vnc is not None:
        guest.graphics_dev = VirtualGraphics(type=VirtualGraphics.TYPE_VNC)
        if vncport:
            guest.graphics_dev.port = vncport
        if vnclisten:
            guest.graphics_dev.listen = vnclisten
    if keymap:
        checked_keymap = _util.check_keytable(keymap)
        if checked_keymap:
            guest.graphics_dev.keymap = checked_keymap
        else:
            raise ValueError, _("Didn't match keymap '%s' in keytable!" % keymap)

def get_sound(sound, guest):

    # Sound is just a boolean value, so just specify a default of 'es1370'
    # model since this should provide audio out of the box for most modern
    # distros
    if sound:
        guest.sound_devs.append(VirtualAudio(model="es1370"))

def get_hostdevs(hostdevs, guest):
    if not hostdevs:
        return

    for devname in hostdevs:
        dev = virtinst.VirtualHostDevice.device_from_node(conn=guest.conn,
                                                          name=devname)
        guest.hostdevs.append(dev)

### Option parsing
def check_before_store(option, opt_str, value, parser):
    if len(value) == 0:
        raise OptionValueError, _("%s option requires an argument") %opt_str
    setattr(parser.values, option.dest, value)

def check_before_append(option, opt_str, value, parser):
    if len(value) == 0:
        raise OptionValueError, _("%s option requires an argument") %opt_str
    parser.values.ensure_value(option.dest, []).append(value)

