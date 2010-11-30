#!/bin/sh

set -v
set -e

if [ -z "$AUTOBUILD_INSTALL_ROOT" ] ; then
    echo "This script is only meant to be used with an autobuild server."
    echo "Please see INSTALL for build instructions."
    exit 1
fi

rm -rf build dist python-virtinst.spec MANIFEST

python setup.py build
python setup.py test
python setup.py install --prefix=$AUTOBUILD_INSTALL_ROOT

VERSION=`python setup.py --version`
cat python-virtinst.spec.in | sed -e "s/::VERSION::/$VERSION/" > python-virtinst.spec
python setup.py sdist

if [ -f /usr/bin/rpmbuild ]; then
  if [ -n "$AUTOBUILD_COUNTER" ]; then
    EXTRA_RELEASE=".auto$AUTOBUILD_COUNTER"
  else
    NOW=`date +"%s"`
    EXTRA_RELEASE=".$USER$NOW"
  fi
  rpmbuild --define "extra_release $EXTRA_RELEASE" \
           --define "_sourcedir `pwd`/dist" \
           -ba --clean python-virtinst.spec
fi
