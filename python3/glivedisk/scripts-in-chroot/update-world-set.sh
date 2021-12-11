#!/bin/bash

source ./chroot-functions.sh

emerge -s non-exist-package > /dev/null
eselect news read all > /dev/null

emerge --autounmask-only -uDN @world > /dev/null

run_merge -uDN @world

echo "perl-cleaner --all"
perl-cleaner --all
