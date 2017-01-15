#!/bin/bash

function fatal {
    echo ${1}
    exit 1
}

echo "Update software on VPS (make sure you've committed and pushed first)? [Y/n]"
read ok
if [[ ${ok} != 'n' ]]; then
    echo "Updating remote git clone..."
    ssh -t django@***REMOVED*** "cd django/stripey.git && git pull && cd .. && source venv_stripey/bin/activate && python manage.py collectstatic"
fi

echo "Copy postgres database to VPS? [y/N]"
read ok
if [[ ${ok} == 'y' ]]; then
    dumpfile="django_$(date +%s).sql"
    # Dump all stripey_app* tables:
    echo "Please enter local postgres user django's password if prompted:"
    pg_dump -U django -W -p 5434 -d django -t 'stripey_app_*' > /tmp/${dumpfile}

    scp /tmp/${dumpfile} django@***REMOVED***:

    cat > import.py << EOF
# Import script for ${dumpfile}
import subprocess
print("Finding stripey_app* tables")
sqltables = subprocess.check_output("psql django -c \"SELECT table_name FROM information_schema.tables WHERE table_name ILIKE 'stripey_app%';\"", shell=True, universal_newlines=True)
tables = [x.strip() for x in sqltables.splitlines() if x.strip().startswith('stripey_app')]
print("Found tables: {}".format(tables))

if tables:
    print("Dropping stripey_app* tables")
    subprocess.check_call('psql django -c "DROP TABLE {}"'.format(', '.join(tables)), shell=True)

print("Vacuuming...")
subprocess.check_call('psql django -c "VACUUM FULL"', shell=True)

print("Importing new data")
subprocess.check_call('psql django < ${dumpfile}', shell=True)

print("Analyzing...")
subprocess.check_call('psql django -c "VACUUM ANALYZE"', shell=True)
EOF

    scp import.py django@***REMOVED***:
    rm import.py
    ssh django@***REMOVED*** "source venv_stripey/bin/activate && python import.py 2>&1"
fi

echo "Remove server picklify data? [y/N]"
read ok
if [[ ${ok} == 'y' ]]; then
    ssh www-data@***REMOVED*** "find .picklify -type f -delete 2>&1"
fi

    
