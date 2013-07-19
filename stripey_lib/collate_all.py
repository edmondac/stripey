#!/usr/bin/python

import os
import time
import sys
import subprocess
import json
import urllib2

COLLATEX_SERVICE = "collatex-tools-1.3/bin/collatex-server"
COLLATEX_PORT = 7369

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

from stripey_app.models import (Chapter, Verse, MsVerse, Book,
                                get_all_verses, Variant, Reading,
                                Stripe, MsStripe)
from django.db import transaction, connection
from django.core.exceptions import ObjectDoesNotExist

import logging
logger = logging.getLogger('collate_all.py')

#~ from stripey_lib import collatex as _mod
#~ os.environ['COLLATE_JAR_PATH'] = os.path.dirname(_mod.__file__)
#~ logger.debug(os.environ['COLLATE_JAR_PATH'])
#~ from stripey_lib.collatex import collatex


@transaction.commit_on_success
def collate_verse(chapter_obj, verse_obj, mss):
    logger.debug("Collating verse {}:{}:{}".format(chapter_obj.book.name,
                                                   chapter_obj.num,
                                                   verse_obj.num))
    start = time.time()
    witnesses = []
    for ms, verses in mss:
        for verse in verses:
            if verse.text:
                witnesses.append({'id':str(verse.id), 'content':verse.text})

    # Get the apparatus from collatex - this is the clever bit...
    collation = query(witnesses)
    logger.debug(" .. collatex produced {} entries for {} witnesses".format(
                 len(collation['table']),
                 len(collation['witnesses'])))

    count = 0

    # Store the readings per ms_verse for later
    mv_readings = {}

    for i, entry in enumerate(collation['table']):
        # entry = appararus entry = a variant unit
        variant = Variant()
        variant.chapter = chapter_obj
        variant.verse = verse_obj
        variant.variant_num = i
        variant.save()
        sys.stdout.write('v')

        for j, sigil in enumerate(collation['witnesses']):
            # sigil = a witness = a verse object's id
            ms_verse = MsVerse.objects.get(id=int(sigil))
            text = unicode(' '.join([x.strip() for x in entry[j]]))

            # Get the reading object, or make a new one
            try:
                reading = Reading.objects.get(text=text,
                                              variant=variant)
            except ObjectDoesNotExist:
                reading = Reading()
                reading.variant = variant
                reading.text = text
                reading.save()
                sys.stdout.write('r')

            # Store this reading against the correct hand
            if ms_verse not in mv_readings:
                mv_readings[ms_verse] = []
            mv_readings[ms_verse].append(reading)

            count += 1
            sys.stdout.write("+")
            sys.stdout.flush()

    # Now sort out the stripes
    stripe_mapping = {}
    for readings in set([tuple(a) for a in mv_readings.values()]):
        # Get the stripe object, or make a new one, for each unique
        # tuple of readings.
        try:
            stripe = None
            for poss in Stripe.objects.filter(readings__in=readings):
                if poss.readings == readings:
                    stripe = poss
                    break
            if not stripe:
                raise ValueError("Can't find one")
        except (ObjectDoesNotExist, ValueError):
            stripe = Stripe()
            stripe.verse = verse_obj
            stripe.save()
            stripe.readings = readings
            stripe.save()
            sys.stdout.write('s')
            sys.stdout.flush()

        stripe_mapping[readings] = stripe

    for ms_verse, readings in mv_readings.items():
        # Save our hand-stripe
        hs = MsStripe()
        hs.stripe = stripe_mapping[tuple(readings)]
        hs.ms_verse = ms_verse
        hs.save()

    t = time.time() - start
    sys.stdout.write('\n')
    logger.debug("  .. added {} manuscript stripes".format(len(mv_readings)))
    logger.debug("  .. added {} entries in {} secs".format(count, round(t, 3)))


def collate_book(book_obj):
    logger.info("Collating book {}:{}".format(book_obj.num, book_obj.name))
    for chapter_obj in Chapter.objects.filter(book=book_obj).order_by('num'):
        logger.info("Collating chapter {} {}".format(book_obj.name, chapter_obj.num))
        all_verses = get_all_verses(book_obj, chapter_obj)
        for v, mss in all_verses:
            verse_obj = Verse.objects.get(chapter=chapter_obj, num=v)
            # 1. check we've not already done this one
            if Variant.objects.filter(verse=verse_obj):
                continue
            # 2. make the new collation
            collate_verse(chapter_obj, verse_obj, mss)


def drop_all():
    """
    Clear out all collation data from the db
    """
    print "Clearing out old data"
    for tab in [MsStripe, Stripe, Reading, Variant]:
        cursor = connection.cursor()
        cursor.execute('DELETE FROM "{0}"'.format(tab._meta.db_table))
    print "Done"


def collate_all():
    """
    Launch the collatex service. We'll then connect to it
    to collate everything, then stop the service at the end.
    """
    p = subprocess.Popen([COLLATEX_SERVICE, '-p', str(COLLATEX_PORT)])
    try:
        time.sleep(5)
        for book in Book.objects.all():
            collate_book(book)
    finally:
        print "Closing server"
        p.terminate()


def query(witnesses, algorithm="dekker"):
    """
    Query the collatex service. Witnesses muyst be a list, as such:
    "witnesses" : [
        {
            "id" : "A",
            "content" : "A black cat in a black basket"
        },
        {
            "id" : "B",
            "content" : "A black cat in a black basket"
        },
    ]

    See http://collatex.net/doc/
    """
    data = json.dumps(dict(witnesses=witnesses,
                           algorithm=algorithm))
    url = "http://localhost:{}/collate".format(COLLATEX_PORT)
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json'}
    req = urllib2.Request(url, data, headers)
    #print req.get_method(), data
    resp = urllib2.urlopen(req)
    print "[{}] {}".format(resp.getcode(), url)
    #print resp.info()
    return json.loads(resp.read())

if __name__ == "__main__":
    logger.info("Collating everything...")
    if 'drop' in sys.argv:
        drop_all()
    collate_all()
