#!/bin/bash

export EMERGE_WARNING_DELAY=0
export CLEAN_DELAY=0
export EBEEP_IGNORE=0
export EPAUSE_IGNORE=0
[[ $CONFIG_PROTECT != "-*"* ]] && export CONFIG_PROTECT="-* .x"

echo "emerge --depclean" || exit 1
emerge --depclean