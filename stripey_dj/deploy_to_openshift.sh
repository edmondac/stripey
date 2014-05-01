#!/bin/bash

function fatal () {
    echo ${1}
    exit 1
}

echo "Commit locally and deploy to openshift? [Y/n]"
read ok
[[ ${ok} == 'n' ]] && fatal "Aborting"

set -x

hg commit -m "Deploying to openshift" || echo "Continuing..."

msg="$(hg summary | head -1)"

OPENSHIFT_REPO="/home/ed/openshift/django/wsgi/openshift/"
#(cd ${OPENSHIFT_REPO} && git rm stripey_app)
cp -r stripey_app ${OPENSHIFT_REPO}
cd ${OPENSHIFT_REPO}
find stripey_app -name "*.pyc" -exec rm {} ';'
git add stripey_app
git commit -a -m "Auto-deploy from hg (${msg})"
git push
