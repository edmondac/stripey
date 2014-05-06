#!/usr/bin/python

import os
import sys
import re

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

from stripey_app.models import ManuscriptTranscription, MsBook
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

import logging
logger = logging.getLogger('load_all.py')

ms_re = re.compile("([0-9]+)_([LPNATRS0-9]+)\.xml")


class UnexpectedFilename(Exception):
    pass

@transaction.commit_on_success
def load_ms(folder, f):
    """
    Load a single XML file
    """
    # We expect the files to be called, e.g. 23_424.xml, or 04_NA27.xml
    # == book 23 (1 John), ms 424.
    match = ms_re.match(f)
    if not match:
        raise UnexpectedFilename("Unexpected filename {}".format(f))
    book_num = int(match.group(1))
    name = match.group(2)
    try:
        m = ManuscriptTranscription.objects.get(ms_ref=name)
    except ObjectDoesNotExist:
        m = ManuscriptTranscription()
        m.ms_ref = name
    else:
        gotit = MsBook.objects.filter(manuscript=m, book__num=book_num).count()
        if gotit:
            logger.debug("Already loaded book {} for ms {} - skipping".format(book_num, name))
            return

    m.load(os.path.join(folder, f))


def load_all(folder):
    """
    Load all the XML files in a folder (and subfolders) into the database
    """
    logger.info("Loading everything in {}".format(folder))
    failures = []
    for path, dirs, files in os.walk(folder):
        for f in [x for x in files if x.endswith('.xml')]:
            try:
                load_ms(path, f)
            except UnexpectedFilename as e:
                logger.warning("{} failed to load: {}".format(f, e))
                failures.append("{} ({})".format(f, e))
            except Exception as e:
                logger.exception("{} failed to load: {}".format(f, e))
                failures.append("{} ({})".format(f, e))
                #raise

    if failures:
        logger.error("Load failed for: \n{}".format('\n\t'.join(failures)))

if __name__ == "__main__":
    load_all(os.path.abspath(sys.argv[1]))
