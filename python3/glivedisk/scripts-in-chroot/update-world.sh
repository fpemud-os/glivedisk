#!/bin/bash

source ./chroot-functions.sh

emerge -s non-exist-package > /dev/null
eselect news read all > /dev/null

export CFGPROTECT = "CONFIG_PROTECT=\"-* /.glivedisk\""    # the latter is for eliminating "!!! CONFIG_PROTECT is empty" message

emerge --autounmask-only -uDN @world > /dev/null

echo "emerge --keep-going -uDN @world"
emerge --keep-going -uDN @world

echo "perl-cleaner --all"
perl-cleaner --all
