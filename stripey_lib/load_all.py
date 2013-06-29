#!/usr/bin/python

import os
import sys

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

from stripey_app.models import Book, Chapter, Verse, Hand, ManuscriptTranscription
from django.db.utils import IntegrityError

import logging
logger = logging.getLogger('load_all.py')


def load_all(folder):
    """
    Load all the XML files in a folder into the database
    """
    logger.info("Loading everything in {}".format(folder))
    failures = []
    for f in [x for x in os.listdir(folder) if x.endswith('.xml')]:
        name = f.rsplit('.', 1)[0]       
        m = ManuscriptTranscription()
        m.ms_ref = name
        m.xml_filename = os.path.join(folder, f)
        try:
            m.save()
        except IntegrityError:
            # Already got this one
            logger.warning("{} is not unique - presuming it's already loaded".format(name))        
            continue
        try:
            m.load()
        except Exception as e:
            logger.error("{} failed to load: {}".format(name, e))
            m.delete()
            failures.append("{} ({})".format(name, e))
            raise

    if failures:
        logger.error("Load failed for: \n{}".format('\n\t'.join(failures)))
    
if __name__ == "__main__":
    load_all(os.path.abspath(sys.argv[1]))
