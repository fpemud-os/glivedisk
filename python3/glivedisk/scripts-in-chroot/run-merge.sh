#!/bin/bash

export EMERGE_WARNING_DELAY=0
export CLEAN_DELAY=0
export EBEEP_IGNORE=0
export EPAUSE_IGNORE=0
[[ $CONFIG_PROTECT != "-*"* ]] && export CONFIG_PROTECT="-* .@@MY_NAME@@"

# using grep to only show:
#   >>> Emergeing ...
#   >>> Installing ...
echo "emerge $@" || exit 1
emerge --color=y $@ | tee /var/log/run-merge.log | grep -E --color=never "^>>>.*\\(.*[0-9]+.*of.*[0-9]+.*\\)" || exit 1
