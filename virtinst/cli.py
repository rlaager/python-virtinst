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
import gettext, locale
import optparse
from optparse import OptionValueError, OptionParser

import libvirt
import _util
import virtinst
from virtinst import VirtualNetworkInterface, VirtualVideoDevice, Guest, \
                     VirtualGraphics, VirtualAudio, VirtualDisk, User
from virtinst import _virtinst as _

MIN_RAM = 64
force = False
doprompt = True

def check_if_test_uri_remote(uri):
    magic = "__virtinst_test_remote__"
    if uri and uri.startswith(magic):
        uri = uri.replace(magic, "")
        _util.is_uri_remote = lambda uri_: True
    return uri

class VirtStreamHandler(logging.StreamHandler):

    def emit(self, record):
        """
        Based on the StreamHandler code from python 2.6: ripping out all
        the unicode handling and just uncoditionally logging seems to fix
        logging backtraces with unicode locales (for me at least).

        No doubt this is atrocious, but it WORKSFORME!
        """
        try:
            msg = self.format(record)
            stream = self.stream
            fs = "%s\n"

            stream.write(fs % msg)

            self.flush()
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.handleError(record)

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
        helpstr = self.format_help()
        try:
            encodedhelp = helpstr.encode(encoding, "replace")
        except UnicodeError:
            # I don't know why the above fails hard, unicode makes my head
            # spin. Just printing the format_help() output seems to work
            # quite fine, with the occasional character ?.
            encodedhelp = helpstr

        file.write(encodedhelp)

class VirtHelpFormatter(optparse.IndentedHelpFormatter):
    """
    Subclass the default help formatter to allow printing newline characters
    in --help output. The way we do this is a huge hack :(

    Inspiration: http://groups.google.com/group/comp.lang.python/browse_thread/thread/6df6e6b541a15bc2/09f28e26af0699b1
    """
    oldwrap = None

    def format_option(self, option):
        self.oldwrap = optparse.textwrap.wrap
        ret = []
        try:
            optparse.textwrap.wrap = self._textwrap_wrapper
            ret = optparse.IndentedHelpFormatter.format_option(self, option)
        finally:
            optparse.textwrap.wrap = self.oldwrap
        return ret

    def _textwrap_wrapper(self, text, width):
        ret = []
        for line in text.split("\n"):
            ret.extend(self.oldwrap(line, width))
        return ret
#
# Setup helpers
#

def setupParser(usage=None):
    parse_class = VirtOptionParser

    parser = parse_class(usage=usage,
                         formatter=VirtHelpFormatter(),
                         version=virtinst.__version__)
    return parser

def setupGettext():
    locale.setlocale(locale.LC_ALL, '')
    gettext.bindtextdomain(virtinst.gettext_app, virtinst.gettext_dir)
    gettext.install(virtinst.gettext_app, virtinst.gettext_dir)

def setupLogging(appname, debug=False):
    # set up logging
    vi_dir = os.path.expanduser("~/.virtinst")
    if not os.access(vi_dir, os.W_OK):
        if os.path.exists(vi_dir):
            raise RuntimeError("No write access to directory %s" % vi_dir)

        try:
            os.mkdir(vi_dir, 0751)
        except IOError, e:
            raise RuntimeError("Could not create directory %s: %s" %
                               (vi_dir, e))


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

    streamHandler = VirtStreamHandler(sys.stderr)
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

# Connection opening helper functions
def getConnection(connect):
    if (connect and
        not User.current().has_priv(User.PRIV_CREATE_DOMAIN, connect)):
        fail(_("Must be root to create Xen guests"))

    # Hack to facilitate remote unit testing
    connect = check_if_test_uri_remote(connect)

    logging.debug("Requesting libvirt URI %s" % (connect or "default"))
    conn = open_connection(connect)
    logging.debug("Received libvirt URI %s" % conn.getURI())

    return conn


def open_connection(uri):
    open_flags = 0
    valid_auth_options = [libvirt.VIR_CRED_AUTHNAME,
                          libvirt.VIR_CRED_PASSPHRASE,
                          libvirt.VIR_CRED_EXTERNAL]
    authcb = do_creds
    authcb_data = None

    return libvirt.openAuth(uri, [valid_auth_options, authcb, authcb_data],
                            open_flags)

def do_creds(creds, cbdata):
    try:
        return _do_creds(creds, cbdata)
    except:
        _util.log_exception("Error in creds callback.")
        raise

def _do_creds(creds, cbdata_ignore):

    if (len(creds) == 1 and
        creds[0][0] == libvirt.VIR_CRED_EXTERNAL and
        creds[0][2] == "PolicyKit"):
        return _do_creds_polkit(creds[0][1])

    for cred in creds:
        if cred[0] == libvirt.VIR_CRED_EXTERNAL:
            return -1

    return _do_creds_authname(creds)

# PolicyKit auth
def _do_creds_polkit(action):
    if os.getuid() == 0:
        logging.debug("Skipping policykit check as root")
        return 0 # Success
    logging.debug("Doing policykit for %s" % action)

    import subprocess
    import commands

    bin_path = "/usr/bin/polkit-auth"

    if not os.path.exists(bin_path):
        logging.debug("%s not present, skipping polkit auth." % bin_path)
        return 0

    cmdstr = "%s %s" % (bin_path, "--explicit")
    output = commands.getstatusoutput(cmdstr)
    if output[1].count(action):
        logging.debug("User already authorized for %s." % action)
        # Hide spurious output from polkit-auth
        popen_stdout = subprocess.PIPE
        popen_stderr = subprocess.PIPE
    else:
        popen_stdout = None
        popen_stderr = None

    # Force polkit prompting to be text mode. Not strictly required, but
    # launching a dialog is overkill.
    env = os.environ.copy()
    env["POLKIT_AUTH_FORCE_TEXT"] = "set"

    cmd = [bin_path, "--obtain", action]
    proc = subprocess.Popen(cmd, env=env, stdout=popen_stdout,
                            stderr=popen_stderr)
    out, err = proc.communicate()

    if out and popen_stdout:
        logging.debug("polkit-auth stdout: %s" % out)
    if err and popen_stderr:
        logging.debug("polkit-auth stderr: %s" % err)

    return 0

# SASL username/pass auth
def _do_creds_authname(creds):
    retindex = 4

    for cred in creds:
        credtype, prompt, ignore, ignore, ignore = cred
        prompt += ": "

        res = cred[retindex]
        if credtype == libvirt.VIR_CRED_AUTHNAME:
            res = raw_input(prompt)
        elif credtype == libvirt.VIR_CRED_PASSPHRASE:
            import getpass
            res = getpass.getpass(prompt)
        else:
            logging.debug("Unknown auth type in creds callback: %d" %
                          credtype)
            return -1

        cred[retindex] = res

    return 0

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
        msg = warning
        if question:
            msg += ("\n" + question)

        inp = prompt_for_input(errmsg, msg, None)
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
def disk_prompt(prompt_txt, arg_dict, warn_overwrite=False, prompt_size=True,
                path_to_clone=None):

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
        if path_to_clone:
            patherr = (_("A disk path must be specified to clone '%s'.") %
                       path_to_clone)

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
                if not VirtualDisk.path_exists(conn, path):
                    size = prompt_loop(size_prompt, sizeerr, size, None, None,
                                       func=float)
            except Exception, e:
                # Path is probably bogus, raise the error
                logging.error(str(e))
                continue
        arg_dict["size"] = size

        # Build disk object for validation
        try:
            dev = VirtualDisk(**arg_dict)
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

def listify(l):
    if l is None:
        return []
    elif type(l) != list:
        return [ l ]
    else:
        return l

def get_name(name, guest, image_name=None):
    prompt_txt = _("What is the name of your virtual machine?")
    err_txt = _("A name is required for the virtual machine.")

    if name is None:
        name = image_name
    prompt_loop(prompt_txt, err_txt, name, guest, "name")

def get_memory(memory, guest, image_memory=None):
    prompt_txt = _("How much RAM should be allocated (in megabytes)?")
    err_txt = _("Memory amount is required for the virtual machine.")
    def check_memory(mem):
        mem = int(mem)
        if mem < MIN_RAM:
            raise ValueError(_("Installs currently require %d megs "
                               "of RAM.") % MIN_RAM)
        guest.memory = mem

    if memory is None and image_memory is not None:
        memory = int(image_memory)/1024
    prompt_loop(prompt_txt, err_txt, memory, guest, "memory",
                func=check_memory)

def get_uuid(uuid, guest):
    if uuid:
        try:
            guest.uuid = uuid
        except ValueError, e:
            fail(e)

def get_vcpus(vcpus, check_cpu, guest, conn, image_vcpus=None):
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

    if vcpus is None and image_vcpus is not None:
        vcpus = int(image_vcpus)
    if vcpus is not None:
        try:
            guest.vcpus = vcpus
        except ValueError, e:
            fail(e)

def get_cpuset(cpuset, mem, guest, conn):
    if cpuset and cpuset != "auto":
        guest.cpuset = cpuset

    elif cpuset == "auto":
        tmpset = None
        try:
            tmpset = Guest.generate_cpuset(conn, mem)
        except Exception, e:
            logging.debug("Not setting cpuset", str(e))

        if tmpset:
            logging.debug("Auto cpuset is: %s" % tmpset)
            guest.cpuset = tmpset

    return

def get_network(net_kwargs, guest):
    n = VirtualNetworkInterface(**net_kwargs)
    guest.nics.append(n)

def set_os_variant(guest, distro_type, distro_variant):
    if not distro_type and not distro_variant:
        # Default to distro autodetection
        guest.set_os_autodetect(True)
    else:
        if (distro_type and str(distro_type).lower() != "none"):
            guest.set_os_type(distro_type)

        if (distro_variant and str(distro_variant).lower() != "none"):
            guest.set_os_variant(distro_variant)


def parse_optstr(optstr, basedict=None):
    """
    Helper function for parsing opt strings of the form
    opt1=val1,opt2=val2,...
    'basedict' is a starting dictionary, so the caller can easily set
    default values, etc.

    Returns a dictionary of {'opt1': 'val1', 'opt2': 'val2'}
    """
    optstr = str(optstr or "")
    optdict = basedict or {}

    args = optstr.split(",")
    for opt in args:
        if not opt:
            continue

        opt_type = None
        opt_val = None
        if opt.count("="):
            opt_type, opt_val = opt.split("=", 1)
            optdict[opt_type.lower()] = opt_val.lower()
        else:
            optdict[opt.lower()] = None

    return optdict

def parse_network_opts(conn, mac, network):
    net_type = None
    network_name = None
    bridge_name = None
    model = None
    option_whitelist = ["model", "mac"]

    args = network.split(",")

    # Determine net type and bridge vs. network
    netdata = None
    typestr = args[0]
    del(args[0])

    if typestr.count(":"):
        net_type, netdata = typestr.split(":", 1)
    elif typestr.count("="):
        net_type, netdata = typestr.split("=", 1)
    else:
        net_type = typestr

    if net_type == VirtualNetworkInterface.TYPE_VIRTUAL:
        network_name = netdata
    elif net_type == VirtualNetworkInterface.TYPE_BRIDGE:
        bridge_name = netdata

    # Pass the remaining arg=value pairs
    opts = parse_optstr(",".join(args))
    for opt_type, ignore_val in opts.items():
        if opt_type not in option_whitelist:
            fail(_("Unknown network option '%s'") % opt_type)

    model   = opts.get("model")
    mac     = opts.get("mac") or mac

    # The keys here correspond to parameter names for VirtualNetworkInterface
    # __init__
    if mac == "RANDOM":
        mac = None
    return { "conn" : conn, "type" : net_type, "bridge": bridge_name,
             "network" : network_name, "model" : model , "macaddr" : mac }

def digest_networks(conn, macs, bridges, networks, nics = 0):
    macs     = listify(macs)
    bridges  = listify(bridges)
    networks = listify(networks)

    if bridges and networks:
        fail(_("Cannot mix both --bridge and --network arguments"))

    if bridges:
        networks = map(lambda b: "bridge:" + b, bridges)

    # With just one mac, create a default network if one is not specified.
    if len(macs) == 1 and len(networks) == 0:
        if User.current().has_priv(User.PRIV_CREATE_NETWORK, conn.getURI()):
            net = _util.default_network(conn)
            networks.append(net[0] + ":" + net[1])
        else:
            networks.append(VirtualNetworkInterface.TYPE_USER)

    # ensure we have less macs then networks, otherwise autofill the mac list
    if len(macs) > len(networks):
        fail(_("Cannot pass more mac addresses than networks."))
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
                networks.append(VirtualNetworkInterface.TYPE_USER)
            macs.append(None)

    net_init_dicts = []
    for i in range(0, len(networks)):
        mac = macs[i]
        netstr = networks[i]
        net_init_dicts.append(parse_network_opts(conn, mac, netstr))

    return net_init_dicts

def get_graphics(vnc, vncport, vnclisten, nographics, sdl, keymap,
                 video_models, guest):
    video_models = video_models or []

    if ((vnc and nographics) or
        (vnc and sdl) or
        (sdl and nographics)):
        raise ValueError, _("Can't specify more than one of VNC, SDL, "
                            "or --nographics")

    for model in video_models:
        dev = virtinst.VirtualVideoDevice(guest.conn)
        dev.model_type = model
        guest.add_device(dev)

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

    # After this point, we are using graphics, so add a video device
    # if one wasn't passed
    if not video_models:
        guest.add_device(VirtualVideoDevice(conn=guest.conn))

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
        use_keymap = None

        if keymap.lower() == "local":
            use_keymap = virtinst.VirtualGraphics.KEYMAP_LOCAL

        elif keymap.lower() != "none":
            use_keymap = _util.check_keytable(keymap)
            if not use_keymap:
                raise ValueError(_("Didn't match keymap '%s' in keytable!") %
                                 keymap)

        guest.graphics_dev.keymap = use_keymap

def get_sound(old_sound_bool, sound_opts, guest):
    if not sound_opts:
        if old_sound_bool:
            # Use os default
            guest.sound_devs.append(VirtualAudio(conn=guest.conn))
        return

    for model in listify(sound_opts):
        dev = VirtualAudio(conn=guest.conn)
        dev.model = model
        guest.add_device(dev)


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

