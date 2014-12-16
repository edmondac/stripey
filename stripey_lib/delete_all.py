import sys
import os
import subprocess

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

from stripey_app import models

mods = [models.MsStripe,
        models.MsVerse,
        models.MsChapter,
        models.MsBook,
        models.Hand,
        models.Stripe,
        models.Reading,
        models.Variant,
        models.Algorithm,
        models.Verse,
        models.Chapter,
        models.Book,
        models.ManuscriptTranscription,
        ]


def delete(model):
    print "Truncating table {}".format(model)
    cmd = "TRUNCATE TABLE {} CASCADE".format(model._meta.db_table)
    subprocess.check_call("psql -p 5433 -U django django -c \"{}\"".format(cmd), shell=True)


def vacuum():
    cmd = "VACUUM FULL"
    subprocess.check_call("psql -p 5433 -U django django -c \"{}\"".format(cmd), shell=True)


print "WARNING: Using hardcoded postgres command line 'psql -p 5433 -U django django'"
print "Really delete everything in the stripey tables? [N/y]"
ok = raw_input()
if ok.strip().lower() == 'y':
    for model in mods:
        delete(model)

    print "Vacuum full? [Y/n]"
    ok = raw_input()
    if ok.strip().lower() != 'n':
        vacuum()

    print "Done"
else:
    print "Aborting"
