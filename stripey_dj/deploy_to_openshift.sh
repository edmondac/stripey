#!/bin/bash

echo "Commit locally and deploy to openshift? [Y/n]"
read ok
if [[ ${ok} == 'n' ]]; then
    echo "Aborting"
    exit 1
fi

hg commit -m "Deploying to openshift"

ls
