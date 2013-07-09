#!/usr/bin/python

import os
import sys

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

from stripey_app.models import ManuscriptTranscription
from django.db.utils import IntegrityError
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

import logging
logger = logging.getLogger('load_all.py')


@transaction.commit_on_success
def load_ms(folder, f):
    """
    Load a single XML file
    """
    name = f.rsplit('.', 1)[0]
    try:
        ManuscriptTranscription.objects.get(ms_ref=name)
    except ObjectDoesNotExist:
        pass
    else:
        # Already got this one
        logger.warning("{} is not unique - presuming it's already loaded".format(name))
        return

    m = ManuscriptTranscription()
    m.ms_ref = name
    m.xml_filename = os.path.join(folder, f)
    m.load()


def load_all(folder):
    """
    Load all the XML files in a folder into the database
    """
    logger.info("Loading everything in {}".format(folder))
    failures = []
    for f in [x for x in os.listdir(folder) if x.endswith('.xml')]:
        try:
            load_ms(folder, f)
        except Exception as e:
            logger.error("{} failed to load: {}".format(f, e))
            failures.append("{} ({})".format(f, e))

    if failures:
        logger.error("Load failed for: \n{}".format('\n\t'.join(failures)))

if __name__ == "__main__":
    load_all(os.path.abspath(sys.argv[1]))
