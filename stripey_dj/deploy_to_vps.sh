#!/bin/bash

function fatal {
    echo ${1}
    exit 1
}

echo "Commit locally and deploy to VPS? [Y/n]"
read ok
[[ ${ok} == 'n' ]] && fatal "Aborting"

set -x

hg commit -m "Deploying to VPS" || echo "Continuing..."

msg="$(hg summary | head -1)"

scp -r stripey_app django@***REMOVED***:***REMOVED***/.
