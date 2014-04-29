#!/bin/bash

function fatal () {
    echo ${1}
    exit 1
}

echo "Commit locally and deploy to openshift? [Y/n]"
read ok
[[ ${ok} == 'n' ]] && fatal "Aborting"

set -x
set -e

hg commit -m "Deploying to openshift"

TEMPDIR="/tmp/deploy_to_openshift_tempdir"

[[ -e ${TEMPDIR} ]] && fatal "${TEMPDIR} exists - aborting"

mkdir ${TEMPDIR}



rm -rf ${TEMPDIR}
