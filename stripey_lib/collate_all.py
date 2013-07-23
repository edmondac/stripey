#!/usr/bin/python

import os
import time
import sys
import subprocess
import json
import urllib2
from contextlib import contextmanager

COLLATEX_SERVICE = "collatex-tools-1.3/bin/collatex-server"
COLLATEX_PORT = 7369

SUPPORTED_ALGORITHMS = ('dekker', 'needleman-wunsch', 'medite')

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

from stripey_app.models import (Chapter, Verse, MsVerse, Book,
                                get_all_verses, Variant, Reading,
                                Stripe, MsStripe, Algorithm)
from django.db import transaction, reset_queries
from django.core.exceptions import ObjectDoesNotExist

import logging
logger = logging.getLogger('collate_all.py')


@transaction.commit_on_success
def collate_verse(chapter_obj, verse_obj, mss, algo):
    logger.debug("Collating verse {}:{}:{} ({})".format(chapter_obj.book.name,
                                                        chapter_obj.num,
                                                        verse_obj.num,
                                                        algo))
    start = time.time()
    witnesses = []
    for ms, verses in mss:
        for verse in verses:
            if verse.text:
                witnesses.append({'id': str(verse.id),
                                  'content': verse.text})

    # Get the apparatus from collatex - this is the clever bit...
    collation = query(witnesses, algo.name)
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
        variant.algorithm = algo
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
            stripe.algorithm = algo
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


def collate_book(book_obj, algo):
    logger.info("Collating book {}:{}".format(book_obj.num, book_obj.name))
    for chapter_obj in Chapter.objects.filter(book=book_obj).order_by('num'):
        logger.info("Collating chapter {} {}".format(book_obj.name, chapter_obj.num))
        all_verses = get_all_verses(book_obj, chapter_obj)
        for v, mss in all_verses:
            verse_obj = Verse.objects.get(chapter=chapter_obj, num=v)
            # 1. check we've not already done this one
            if Variant.objects.filter(verse=verse_obj, algorithm=algo):
                continue
            # 2. make the new collation
            collate_verse(chapter_obj, verse_obj, mss, algo)
            # 3. tidy up django's query list, to free up some memory
            reset_queries()


@transaction.commit_on_success
def drop_all(algo):
    """
    Clear out all collation data from the db
    """
    logger.warning("Clearing out old data for {}".format(algo))

    for v in Variant.objects.filter(algorithm__name=algo):
        v.delete()
    for s in Stripe.objects.filter(algorithm__name=algo):
        s.delete()

    logger.warning("Done")


def collate_all(algo):
    """
    Collate everything using the collatex service
    """
    with collatex_service():
        try:
            algo_obj = Algorithm.objects.get(name=algo)
        except ObjectDoesNotExist:
            algo_obj = Algorithm()
            algo_obj.name = algo
            algo_obj.save()

        for book in Book.objects.all():
            collate_book(book, algo_obj)


def tests():
    """
    Collate everything using the collatex service
    """
    with collatex_service():
        witnesses = [{'id': '1',
                      'content': 'This is a test'},
                     {'id': '2',
                      'content': 'This is test'},
                     {'id': '3',
                      'content': 'This is a testimony'},
                     {'id': '4',
                      'content': 'These are tests'},
                     {'id': '5',
                      'content': 'This is a a test'}]
        print query(witnesses, 'dekker')
        print query(witnesses, 'needleman-wunsch')
        print query(witnesses, 'medite')


@contextmanager
def collatex_service():
    """
    Launch the collatex service, then yield to the caller. When we come back
    we'll stop the service again.
    """
    p = subprocess.Popen([COLLATEX_SERVICE, '-p', str(COLLATEX_PORT)])
    time.sleep(5)
    try:
        yield
    finally:
        logger.info("Closing server")
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
    assert algorithm in SUPPORTED_ALGORITHMS

    data = json.dumps(dict(witnesses=witnesses,
                           algorithm=algorithm))
    url = "http://localhost:{}/collate".format(COLLATEX_PORT)
    headers = {'Content-Type': 'application/json',
               'Accept': 'application/json'}
    start = time.time()
    req = urllib2.Request(url, data, headers)
    #print req.get_method(), data
    resp = urllib2.urlopen(req)
    logger.info("[{}] {} ({})".format(resp.getcode(), url, algorithm))
    #print resp.info()
    ret = json.loads(resp.read())
    end = time.time()
    logger.info("[{}] {} ({}) - {} secs".format(resp.getcode(), url, algorithm, end-start))
    return ret

def _arg(question, default=None):
    """
    Ask the question, and return a suitable answer.
    If the default is a bool then return a bool, otherwise
    return the value as entered by the user.
    """
    if default is True:
        question += ' [Y/n]'
    elif default is False:
        question += ' [y/N]'
    val = raw_input("{}: ".format(question)).strip()
    if default is None:
        # No default, just return the value as is
        return val
    elif default is True:
        if val.lower() == 'n':
            return False
        else:
            return True
    else:
        if val.lower() == 'y':
            return True
        else:
            return False


if __name__ == "__main__":
    if 'test' in sys.argv:
        logger.info("Running tests...")
        tests()
    else:
        logger.info("Collating everything...")
        algo = _arg("Enter name for algorithm ({} - or all)".format(', '.join(SUPPORTED_ALGORITHMS)))
        drop = _arg("Remove old collation ({}) before continuing?".format(algo), False)

        if algo == 'all':
            algos = SUPPORTED_ALGORITHMS
        else:
            algos = [algo]

        for a in algos:
            if drop:
                drop_all(a)
            collate_all(a)
