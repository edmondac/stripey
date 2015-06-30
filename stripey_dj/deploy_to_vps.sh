#!/bin/bash

function fatal {
    echo ${1}
    exit 1
}

echo "Commit locally and deploy to VPS? [Y/n]"
read ok
[[ ${ok} == 'n' ]] && fatal "Aborting"

hg commit -m "Deploying to VPS" || echo "Continuing..."

msg="$(hg summary | head -1)"

scp -r stripey_app django@***REMOVED***:***REMOVED***/.

echo "Copy postgres database to VPS? [y/N]"
read ok
[[ ${ok} != 'n' ]] && fatal "Aborting"

dumpfile="django_$(date +%s).sql"

# Dump all stripey_app* tables:
echo "Please enter postgres user django's password:"
pg_dump -U django -W -p 5434 -d django -t stripey_app* > /tmp/${dumpfile}

scp /tmp/${dumpfile} django@***REMOVED***:

cat > import.sh << EOF
# Import script for ${dumpfile}
set -x
set -e
echo "Finding stripey_app* tables"
psql django -c "SELECT table_name FROM information_schema.tables WHERE table_name ILIKE 'stripey_app%';" | grep stripey > stripey_app.tables

echo "Dropping stripey_app* tables"
psql django -c "DROP TABLE \$(perl -pe 's/\n/\$1,/' stripey_app.tables))"

echo "Importing new data"
psql django < ${dumpfile}
EOF

scp import.sh django@***REMOVED***:
rm import.sh
ssh django@***REMOVED*** "bash import.sh"

