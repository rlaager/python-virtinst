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

import commands
import os, sys

# Location
xmldir = "tests/cli-test-xml"

# Images that will be created by virt-install/virt-clone, and removed before
# each run
new_images =    [ "cli_new1.img", "cli_new2.img", "cli_new3.img" ]

# Images that are expected to exist before a command is run
exist_images =  [ "cli_exist1.img", "cli_exist2.img" ]

# Images that need to exist ahead of time for virt-image
virtimage_exist = [os.path.join(xmldir, "cli_root.raw")]

# Images created by virt-image
virtimage_new = [os.path.join(xmldir, "cli_scratch.raw")]

exist_files = exist_images + virtimage_exist
new_files   = new_images + virtimage_new
clean_files = new_images + exist_images + virtimage_exist + virtimage_new

test_files = {
    'CLONE_DISK_XML'    : "%s/clone-disk.xml" % xmldir,
    'IMAGE_XML'         : "%s/image.xml" % xmldir,
    'NEWIMG1'           : new_images[0],
    'NEWIMG2'           : new_images[1],
    'NEWIMG3'           : new_images[2],
    'EXISTIMG1'         : exist_images[0],
    'EXISTIMG2'         : exist_images[1],
}

debug = False
testprompt = False

"""
CLI test matrix

Format:

"appname" {
  "global_args" : Arguments to be passed to every app invocation

  "categoryfoo" : { Some descriptive test catagory name (e.g. storage)

    "categoryfoo_args" : Args to be applied to all invocations in category

    "valid" : { # Argument strings that should succeed
      "--option --string --number1" # Some option string to test. The
          resulting cmdstr would be:
          $ appname global_args categoryfoo_args --option --string --number1
    }

    "invalid" : { # Argument strings that should fail
      "--opt1 --opt2",
    }
  } # End categoryfoo

  "prompt" : { # Special category that will launch an interactive command.
               # which is only run if special args are passed to the test
    "--some --prompt --command --string"
  }
}
  "
"""
args_dict = {

  "virt-install" : {
    "global_args" : " --connect test:///default -d --name foobar --ram 64",

    "storage" : {
      "storage_args": "--pxe --nographics --noautoconsole --hvm",

      "valid"  : [
        # Existing file, other opts
        "--file virt-convert --nonsparse --file-size 4",
        # Existing file, no opts
        "--file virt-convert",
        # Multiple existing files
        "--file virt-convert --file virt-image --file virt-clone",
        # Nonexistent file
        "--file %(NEWIMG1)s --file-size .00001 --nonsparse",

        # Existing disk, lots of opts
        "--disk path=virt-convert,perms=ro,size=.0001,cache=writethrough",
        # Existing floppy
        #"--disk path=virt-convert,device=floppy",
        # Existing disk, no extra options
        "--disk path=virt-convert",
      ],

      "invalid": [
        # Nonexisting file, size too big
        "--file %(NEWIMG1)s --file-size 100000 --nonsparse",
        # Huge file, sparse, but no prompting
        "--file %(NEWIMG1)s --file-size 100000",
        # Nonexisting file, no size
        "--file %(NEWIMG1)s",
        # Size, no file
        "--file-size .0001",
      ]
     }, # category "storage"

     "install" : {
      "install_args": "--nographics --noautoconsole --nodisks",

      "valid" : [
        # Simple cdrom install
        "--hvm --cdrom virt-convert",
        # Windows (2 stage) install
        "--hvm --wait 0 --os-variant winxp --cdrom virt-convert",
      ],

      "invalid": [
        # PXE w/ paravirt
        "--paravirt --pxe",
        # Import with no disks
        "--import",
        # LiveCD with no media
        "--livecd",
      ],
     }, # category "install"

     "graphics": {
      "graphics_args": "--noautoconsole --nodisks --pxe",

      "valid": [
        # SDL
        "--sdl",
        # VNC w/ lots of options
        "--vnc --keymap ja --vncport 5950 --vnclisten 1.2.3.4",
      ],

      "invalid": [
        # Invalid keymap
        "--vnc --keymap ZZZ",
        # Invalid port
        "--vnc --vncport -50",
      ],

     }, # category "graphics"

     "misc": {
      "misc_args": "--nographics --noautoconsole",

      "valid": [
        # Specifying cdrom media via --disk
        "--hvm --disk path=virt-install,device=cdrom",
        # FV Import install
        "--hvm --import --disk path=virt-install",
        # PV Import install
        "--paravirt --import --disk path=virt-install",
      ],

      "invalid": [],
     }, # category "misc"


    "prompt" : [ " --connect test:///default --debug --prompt" ]
  },


  "virt-clone": {
    "global_args" : " --connect test:///default -d",

    "general" : {
      "general_args": "-n clonetest",

      "valid"  : [
        # Nodisk guest
        "-o test",
        # Nodisk, but with spurious files passed
        "-o test --file %(NEWIMG1)s --file %(NEWIMG2)s",

        # XML File with 2 disks
        "--original-xml %(CLONE_DISK_XML)s --file %(NEWIMG1)s --file %(NEWIMG2)s",
        # XML w/ disks, overwriting existing files with --preserve
        "--original-xml %(CLONE_DISK_XML)s --file virt-install --file virt-convert --preserve",
        # XML w/ disks, force copy a readonly target
        "--original-xml %(CLONE_DISK_XML)s --file %(NEWIMG1)s --file %(NEWIMG2)s --file %(NEWIMG3)s --force-copy=hdc",
        # XML w/ disks, force copy a target with no media
        "--original-xml %(CLONE_DISK_XML)s --file %(NEWIMG1)s --file %(NEWIMG2)s --force-copy=fda",
      ],

      "invalid": [
        # Non-existent vm name
        "-o idontexist",
        # Colliding new name
        "-o test -n test",
        # XML file with several disks, but non specified
        "--original-xml %(CLONE_DISK_XML)s",
        # XML w/ disks, overwriting existing files with no --preserve
        "--original-xml %(CLONE_DISK_XML)s --file virt-install --file virt-convert",
        # XML w/ disks, force copy but not enough disks passed
        "--original-xml %(CLONE_DISK_XML)s --file %(NEWIMG1)s --file %(NEWIMG2)s --force-copy=hdc",
      ]
     }, # category "general"

    "prompt" : [ " --connect test:///default --debug --prompt",
                 " --connect test:///default --debug --original-xml %(CLONE_DISK_XML)s --prompt" ]
  }, # app 'virt-clone'

  'virt-image': {
    "global_args" : " --connect test:///default -d %(IMAGE_XML)s",

    "general" : {
      "general_args" : "--name test-image",

      "valid": [
        # All default values
        "",
        # Manual boot idx 0
        "--boot 0",
        # Manual boot idx 1
        "--boot 1",
        # Lots of options
        "--name foobar --ram 64 --os-variant winxp",
      ],

      "invalid": [
        # Out of bounds index
        "--boot 10",
      ],
     }, # category 'general'

    "graphics" : {
      "graphics_args" : "--name test-image --boot 0",

      "valid": [
        # SDL
        "--sdl",
        # VNC w/ lots of options
        "--vnc --keymap ja --vncport 5950 --vnclisten 1.2.3.4",
      ],

      "invalid": [],
    },

    "misc": {
     "misc_args" : "",

      "valid" : [],
      "invalid" : [
        # No name specified, and no prompt flag
        "",
      ],

     }, # category 'misc'

    "prompt" : [ " --connect test:///default %(IMAGE_XML)s --debug --prompt" ],

  } # app 'virt-image'
}

def runcomm(comm):
    for i in new_files:
        os.system("rm %s > /dev/null 2>&1" % i)
    ret = commands.getstatusoutput(comm % test_files)
    if debug:
        print comm
        print ret[1]
        print "\n"

    return ret

def run_prompt_comm(comm):
    print comm
    os.system(comm % test_files)

def assertPass(comm):
    ret = runcomm(comm)
    if ret[0] is not 0:
        raise AssertionError("Expected command to pass, but failed.\n" + \
                             "Command was: %s\n" % (comm) + \
                             "Error code : %d\n" % ret[0] + \
                             "Output was:\n%s" % ret[1])

def assertFail(comm):
    ret = runcomm(comm)
    if ret[0] is 0:
        raise AssertionError("Expected command to fail, but passed.\n" + \
                             "Command was: %s\n" % (comm) + \
                             "Error code : %d\n" % ret[0] + \
                             "Output was:\n%s" % ret[1])

# Setup: build cliarg dict, which uses
def run_tests():
    for app in args_dict:
        unique = {}
        prompts = []
        global_args = ""

        # Build default command line dict
        for option in args_dict.get(app):
            if option == "global_args":
                global_args = args_dict[app][option]
                continue
            elif option == "prompt":
                prompts = args_dict[app][option]
                continue

            # Default is a unique cmd string
            unique[option]= args_dict[app][option]

        # Build up prompt cases
        if testprompt:
            for optstr in prompts:
                cmd = "./" + app + " " + optstr
                run_prompt_comm(cmd)
            continue

        # Build up unique command line cases
        for category in unique.keys():
            catdict = unique[category]
            category_args = catdict["%s_args" % category]

            for optstr in catdict["valid"]:
                cmdstr = "./%s %s %s %s" % (app, global_args,
                                            category_args, optstr)
                assertPass(cmdstr)

            for optstr in catdict["invalid"]:
                cmdstr = "./%s %s %s %s" % (app, global_args,
                                            category_args, optstr)
                assertFail(cmdstr)

def main():
    # CLI Args
    global debug
    global testprompt

    if len(sys.argv) > 1:
        for i in range(1, len(sys.argv)):
            if sys.argv[i].count("debug"):
                debug = True
            elif sys.argv[i].count("prompt"):
                testprompt = True

    # Setup needed files
    for i in exist_files:
        if os.path.exists(i):
            raise ValueError("'%s' will be used by testsuite, can not already"
                             " exist." % i)
        os.system("touch %s" % i)

    try:
        run_tests()
    finally:
        # Cleanup files
        for i in clean_files:
            os.system("rm %s > /dev/null 2>&1" % i)

if __name__ == "__main__":
    main()
