#!/bin/bash

export EMERGE_WARNING_DELAY=0
export CLEAN_DELAY=0
export EBEEP_IGNORE=0
export EPAUSE_IGNORE=0
[[ $CONFIG_PROTECT != "-*"* ]] && export CONFIG_PROTECT="-* .x"

# using grep to only show:
#   >>> Emergeing ...
#   >>> Installing ...
#   >>> Uninstalling ...
#   >>> No outdated packages were found on your system.
echo "emerge -uDN --with-bdeps=y $@" || exit 1
emerge --color=y -uDN --with-bdeps=y $@ 2>&1 | tee /var/log/portage/run-update.log | grep -E --color=never "^>>> (.*\\(.*[0-9]+.*of.*[0-9]+.*\\)|No outdated packages .*)"
test ${PIPESTATUS[0]} -eq 0 || exit 1
