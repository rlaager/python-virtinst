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

import os
import sys
import glob

from distutils.core import setup, Command
from distutils.command.sdist import sdist
from distutils.command.build import build
from unittest import TextTestRunner, TestLoader

scripts = ["virt-install", "virt-clone", "virt-image", "virt-convert"]
packages = ['virtinst', 'virtconv', 'virtconv.parsers']
config_files = ["virtinst/_config.py", "virtconv/_config.py"]
datafiles = [('share/man/man1', ['man/en/virt-install.1',
                                 'man/en/virt-clone.1',
                                 'man/en/virt-image.1',
                                 'man/en/virt-convert.1']),
             ('share/man/man5', ['man/en/virt-image.5'])]

VERSION = "0.500.6"

config_template = """
__version__ = "%(VERSION)s"
__version_info__ = tuple([ int(num) for num in __version__.split('.')])
"""

config_data = config_template % { "VERSION" : VERSION }

class TestBaseCommand(Command):

    user_options = [('debug', 'd', 'Show debug output')]
    boolean_options = ['debug']

    def initialize_options(self):
        self.debug = 0
        self._testfiles = []
        self._dir = os.getcwd()

    def finalize_options(self):
        if self.debug and "DEBUG_TESTS" not in os.environ:
            os.environ["DEBUG_TESTS"] = "1"

    def run(self):
        try:
            import coverage
            use_coverage = True
        except:
            # Use system 'coverage' if available
            use_coverage = False

        tests = TestLoader().loadTestsFromNames(self._testfiles)
        t = TextTestRunner(verbosity=1)

        if use_coverage:
            coverage.erase()
            coverage.start()

        result = t.run(tests)

        if use_coverage:
            coverage.stop()

        if len(result.failures) > 0 or len(result.errors) > 0:
            sys.exit(1)
        else:
            sys.exit(0)

class TestCommand(TestBaseCommand):

    description = "Runs a quick unit test suite"
    user_options = TestBaseCommand.user_options + \
                   [("testfile=", None, "Specific test file to run (e.g "
                                        "validation, storage, ...)")]

    def initialize_options(self):
        TestBaseCommand.initialize_options(self)
        self.testfile = None

    def finalize_options(self):
        TestBaseCommand.finalize_options(self)

    def run(self):
        '''
        Finds all the tests modules in tests/, and runs them.
        '''
        testfiles = []
        for t in glob.glob(os.path.join(self._dir, 'tests', '*.py')):
            if (t.endswith('__init__.py') or
                t.endswith("urltest.py") or
                t.endswith("clitest.py")):
                continue

            base = os.path.basename(t)
            if self.testfile:
                check = os.path.basename(self.testfile)
                if base != check and base != (check + ".py"):
                    continue

            testfiles.append('.'.join(['tests', os.path.splitext(base)[0]]))

        if not testfiles:
            raise RuntimeError("--testfile didn't catch anything")

        self._testfiles = testfiles
        TestBaseCommand.run(self)

class TestCLI(TestBaseCommand):

    description = "Test various CLI invocations"

    user_options = (TestBaseCommand.user_options +
                    [("prompt", None, "Run interactive CLI invocations."),
                    ("app=", None, "Only run tests for requested app"),
                    ("category=", None, "Only run tests for the requested "
                                       "category (install, storage, etc.)")])

    def initialize_options(self):
        TestBaseCommand.initialize_options(self)
        self.prompt = 0
        self.app = None
        self.category = None

    def run(self):
        cmd = "python tests/clitest.py"
        if self.debug:
            cmd += " debug"
        if self.prompt:
            cmd += " prompt"
        if self.app:
            cmd += " --app %s" % self.app
        if self.category:
            cmd += " --category %s" % self.category
        os.system(cmd)

class TestURLFetch(TestBaseCommand):

    description = "Test fetching kernels and isos from various distro trees"

    user_options = TestBaseCommand.user_options + \
                   [("match=", None, "Regular expression of dist names to "
                                     "match [default: '.*']"),
                    ("path=", None, "Paths to local iso or directory or check"
                                    " for installable distro. Comma separated")]

    def initialize_options(self):
        TestBaseCommand.initialize_options(self)
        self.match = None
        self.path = ""

    def finalize_options(self):
        TestBaseCommand.finalize_options(self)
        if self.match is None:
            self.match = ".*"

        origpath = str(self.path)
        if not origpath:
            self.path = []
        else:
            self.path = origpath.split(",")

    def run(self):
        import tests
        self._testfiles = ["tests.urltest"]
        tests.urltest.MATCH_FILTER = self.match
        if self.path:
            for p in self.path:
                tests.urltest.LOCAL_MEDIA.append(p)
        TestBaseCommand.run(self)

class CheckPylint(Command):
    user_options = []
    description = "Run static analysis script against codebase."

    def initialize_options(self):
        pass
    def finalize_options(self):
        pass

    def run(self):
        os.system("tests/pylint-virtinst.sh")

class myrpm(Command):

    user_options = []

    description = "Build a non-binary rpm."

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        """
        Run sdist, then 'rpmbuild' the tar.gz
        """
        self.run_command('sdist')
        os.system('rpmbuild -ta dist/virtinst-%s.tar.gz' % VERSION)

class refresh_translations(Command):

    user_options = []

    description = "Regenerate POT file and merge with current translations."

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):

        # Generate POT file
        files = ["virtinst/*.py", "virtconv/*.py", "virtconv/parsers/*.py",
                  "virt-*"]
        pot_cmd = "xgettext --language=Python -o po/virtinst.pot"
        for f in files:
            pot_cmd += " %s " % f
        os.system(pot_cmd)

        # Merge new template with existing translations.
        for po in glob.glob(os.path.join(os.getcwd(), 'po', '*.po')):
            os.system("msgmerge -U po/%s po/virtinst.pot" %
                      os.path.basename(po))

class mysdist(sdist):
    """ custom sdist command, to prep virtinst.spec file for inclusion """

    def run(self):
        cmd = (""" sed -e "s/::VERSION::/%s/g" < python-virtinst.spec.in """ %
               VERSION) + " > python-virtinst.spec"
        os.system(cmd)

        # Update and generate man pages
        self._update_manpages()

        sdist.run(self)

    def _update_manpages(self):
        # Update virt-install.1 with latest os type/variant values
        import virtinst.osdict as osdict

        output = ""
        output += "=over 4\n\n"
        for t in osdict.sort_helper(osdict.OS_TYPES):
            output += "=item %s\n\n" % t

            output += "=over 4\n\n"
            for v in osdict.sort_helper(osdict.OS_TYPES[t]["variants"]):
                output += "=item %s\n\n" % v
                output += osdict.OS_TYPES[t]["variants"][v]["label"] + "\n\n"

            output += "=back\n\n"

        # Add special 'none' value
        output += "=item none\n\n"
        output += "No OS version specified (disables autodetect)\n\n"
        output += "=back\n\n"

        infile = "man/en/virt-install.pod.in"
        outfile = "man/en/virt-install.pod"

        infd  = open(infile, "r")
        outfd = open(outfile, "w")

        inp = infd.read()
        infd.close()

        outp = inp.replace("::VARIANT VALUES::", output)
        outfd.write(outp)
        outfd.close()

        # Generate new manpages
        if os.system("make -C man/en"):
            raise RuntimeError("Couldn't generate man pages.")

class mybuild(build):
    """ custom build command to compile i18n files"""

    def run(self):
        for f in config_files:
            print "Generating %s" % f
            fd = open(f, "w")
            fd.write(config_data)
            fd.close()

        for filename in glob.glob(os.path.join(os.getcwd(), 'po', '*.po')):
            filename = os.path.basename(filename)
            lang = os.path.basename(filename)[0:len(filename) - 3]
            langdir = os.path.join("build", "mo", lang, "LC_MESSAGES")
            if not os.path.exists(langdir):
                os.makedirs(langdir)

            newname = os.path.join(langdir, "virtinst.mo")
            print "Formatting %s to %s" % (filename, newname)
            os.system("msgfmt po/%s -o %s" % (filename, newname))

            targetpath = os.path.join("share", "locale", lang, "LC_MESSAGES")
            self.distribution.data_files.append((targetpath, (newname,)))

        build.run(self)

setup(
    name='virtinst',
    version=VERSION,
    description='Virtual machine installation',
    author='Jeremy Katz, Daniel Berrange, Cole Robinson',
    author_email='crobinso@redhat.com',
    license='GPL',
    url='http://virt-manager.org',
    package_dir={'virtinst': 'virtinst'},
    scripts=["virt-install", "virt-clone", "virt-image", "virt-convert"],
    packages=packages,
    data_files=datafiles,
    cmdclass={
        'test': TestCommand,
        'test_urls' : TestURLFetch,
        'test_cli' : TestCLI,
        'pylint': CheckPylint,

        'rpm' : myrpm,
        'sdist': mysdist,
        'refresh_translations': refresh_translations,

        'build': mybuild,
    }
)
