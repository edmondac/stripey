#!/usr/bin/python

import os
import time
import sys
import subprocess
import signal
import json
import urllib2
from contextlib import contextmanager

# Collatex settings:
# COLLATEX_SERVICE = ["collatex-tools-1.5/bin/collatex-server"]
COLLATEX_SERVICE = ["java", "-jar", "collatex-tools-1.7.1.jar", "--http"]
COLLATEX_PORT = 7369
SUPPORTED_ALGORITHMS = ('dekker', 'needleman-wunsch', 'medite')
TIMEOUT = 900
# levenstein distance: the edit distance threshold for optional fuzzy matching
#                      of tokens; the default is exact matching
FUZZY_EDIT_DISTANCE = 3

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

import django
django.setup()

from stripey_app.models import (Chapter, Verse, MsVerse, Book,
                                get_all_verses, Variant, Reading,
                                Stripe, MsStripe, Algorithm)
from django.db import transaction, reset_queries
from django.core.exceptions import ObjectDoesNotExist

import logging
logger = logging.getLogger('collate_all.py')


@transaction.atomic
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
    cx = CollateXService()
    try:
        # Get the apparatus from collatex - this is the clever bit...
        collation = cx.query(witnesses, algo.name)
    except Exception as e:
        # Collate failed
        logger.error("Collate has failed us: {}".format(str(e)))
        cx.restart()
        return

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

    cx.quit()


def collate_book(book_obj, algo, chapter_ref=None):
    """
    Collate a particular book using the specified algo

    @param book_obj: db book object
    @param algo: db algorithm object
    @chapter_ref: (int) chapter number to collate (or None for all)
    """
    logger.info("Collating book {}:{}".format(book_obj.num, book_obj.name))
    for chapter_obj in Chapter.objects.filter(book=book_obj).order_by('num'):
        if chapter_ref is None or chapter_ref == chapter_obj.num:
            logger.info("Collating chapter {} {}".format(book_obj.name, chapter_obj.num))
            all_verses = get_all_verses(book_obj, chapter_obj)
            for v, mss in all_verses:
                verse_obj = Verse.objects.get(chapter=chapter_obj, num=v)
                #~ print verse_obj
                #~ print Variant.objects.filter(verse=verse_obj, algorithm=algo)
                #~ print Stripe.objects.filter(verse=verse_obj, algorithm=algo)
                # 1. check we've not already done this one
                if Variant.objects.filter(verse=verse_obj, algorithm=algo):
                    continue
                # 2. make the new collation
                collate_verse(chapter_obj, verse_obj, mss, algo)
                # 3. tidy up django's query list, to free up some memory
                reset_queries()


@transaction.atomic
def drop_all(algo, chapter_ref=None):
    """
    Clear out all collation data from the db

    @param algo: name of an algorithm
    @param chapter_ref: book:chapter, e.g. 04:11, to collate
    """
    logger.warning("Clearing out old data for {}".format(algo))

    to_del = []
    if chapter_ref is None:
        for v in Variant.objects.filter(algorithm__name=algo):
            to_del.append(v)
        for s in Stripe.objects.filter(algorithm__name=algo):
            to_del.append(s)
    else:
        mubook, muchapter = chapter_ref.split(':')
        mubook = int(mubook)
        muchapter = int(muchapter)
        for v in Variant.objects.filter(algorithm__name=algo,
                                        verse__chapter__num=muchapter,
                                        verse__chapter__book__num=mubook):
            to_del.append(v)
        for s in Stripe.objects.filter(algorithm__name=algo,
                                       verse__chapter__num=muchapter,
                                       verse__chapter__book__num=mubook):
            to_del.append(s)

    print " > Deleting {} objects".format(len(to_del))
    for i, x in enumerate(to_del):
        x.delete()
        sys.stdout.write("\r > {} ({}%)   ".format(i + 1, i * 100.0 / len(to_del)))
    print

    logger.warning("Done")


def collate_all(algo, chapter_ref=None):
    """
    Collate everything using the collatex service

    @param algo: name of an algorithm
    @param chapter_ref: book:chapter, e.g. 04:11, to collate
    """
    if chapter_ref:
        mubook, muchapter = chapter_ref.split(':')
        mubook = int(mubook)
        muchapter = int(muchapter)
    else:
        mubook = muchapter = None

    try:
        algo_obj = Algorithm.objects.get(name=algo)
    except ObjectDoesNotExist:
        algo_obj = Algorithm()
        algo_obj.name = algo
        algo_obj.save()

    for book in Book.objects.all():
        if mubook is None or book.num == mubook:
            collate_book(book, algo_obj, muchapter)


def tests():
    """
    Collate everything using the collatex service
    """
    cx = CollateXService()
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
    print cx.query(witnesses, 'dekker')
    print cx.query(witnesses, 'needleman-wunsch')
    print cx.query(witnesses, 'medite')


class TimeoutException(Exception):
    pass


class CollateXService(object):
    """
    Manage and query collatex
    """
    _service = COLLATEX_SERVICE
    _port = COLLATEX_PORT
    _popen = None

    def _start_service(self):
        logger.info("Starting CollateX service on port {}".format(self._port))
        self.__class__._popen = subprocess.Popen(self._service + ['-p', str(self._port)])
        time.sleep(5)

    def _stop_service(self):
        logger.info("Killing CollateX service immediately")
        self.__class__._popen.poll()
        while self.__class__._popen.returncode is None:
            logger.info("Kill...")
            self._popen.kill()
            time.sleep(1)
            self.__class__._popen.poll()

        self.__class__._popen = None

    def restart(self):
        logger.info("Restarting...")
        self._stop_service()
        time.sleep(5)
        self._start_service()

    def quit(self):
        logger.info("Quitting...")
        self._stop_service()

    def _test(self):
        """
        Test the running collatex service.
        Returns True for success and False for failure.
        """
        witnesses = [{'id': '1',
                      'content': 'This is a test'},
                     {'id': '2',
                      'content': 'This is test'}]
        try:
            self._query(witnesses, 'dekker', quiet=True)
        except Exception:
            return False
        else:
            return True

    def query(self, *args):
        """
        Wraps the _query method with a test and starts the service if it fails.
        """
        if self.__class__._popen is None:
            self._start_service()

        if not self._test():
            logger.warning("CollateX service failed the test - restarting it")
            self.restart()
            if not self._test():
                raise IOError("Even after restarting CollateX failed the test - aborting")

        return self._query(*args)

    def _query(self, witnesses, algorithm="dekker", quiet=False):
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

        def timeout_handler(signum, frame):
            raise TimeoutException('Timeout')

        @contextmanager
        def timeout(seconds):
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(seconds)
            try:
                yield
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

        input_d = dict(witnesses=witnesses,
                       algorithm=algorithm)
        if FUZZY_EDIT_DISTANCE:
            input_d['tokenComparator'] = {"type": "levenshtein",
                                          "distance": FUZZY_EDIT_DISTANCE}
        data = json.dumps(input_d)

        url = "http://localhost:{}/collate".format(COLLATEX_PORT)
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json'}
        if not quiet:
            logger.debug("Start time {}".format(time.ctime()))
        start = time.time()
        with timeout(TIMEOUT):
            req = urllib2.Request(url, data, headers)
            #print req.get_method(), data
            resp = urllib2.urlopen(req)
            #print resp.info()
            ret = json.loads(resp.read())
            end = time.time()
            if not quiet:
                logger.info("[{}] {} ({}) - {} secs".format(resp.getcode(), url, algorithm, end - start))
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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-a', '--algorithm', default='dekker',
                        help='Which algorithm to use? Options are: {}, all'.format(SUPPORTED_ALGORITHMS))
    parser.add_argument('-t', '--test', help="Just run tests and exit", default=False, action='store_true')
    parser.add_argument('-c', '--clean', help="Clean out old colation before adding new",
                        default=False, action='store_true')
    parser.add_argument('-f', '--force', help="Don't ask any questions - just do it!",
                        default=False, action='store_true')
    parser.add_argument('--chapter', help="Collate only one specific chapter (04:11 => John 11)",
                        default=None)
    args = parser.parse_args()

    if args.test:
        logger.info("Running tests...")
        tests()
    else:
        if args.algorithm == 'all':
            algos = SUPPORTED_ALGORITHMS
        else:
            algos = [args.algorithm]

        if args.clean:
            ok = (args.force or
                  _arg("Remove old ({}) collation for {} before continuing?"
                      .format(algos, args.chapter if args.chapter else "ALL WORKS"),
                       False))
            if not ok:
                sys.exit(1)
            for a in algos:
                drop_all(a, args.chapter)

        for a in algos:
            collate_all(a, args.chapter)

        print "\n** Don't forget to delete the old picklify data"
