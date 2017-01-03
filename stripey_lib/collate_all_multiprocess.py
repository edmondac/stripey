#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import sys
import subprocess
import signal
import socket
import json
import urllib.request
import urllib.error
import urllib.parse
import multiprocessing
import logging
from contextlib import contextmanager

# Collatex settings:
COLLATEX_JAR = "collatex-tools-1.7.1.jar"
# How many colatex errors before we restart the service?
MAX_COLLATEX_ERRORS = 20
SUPPORTED_ALGORITHMS = ('dekker', 'needleman-wunsch', 'medite')
# levenstein distance: the edit distance threshold for optional fuzzy matching
#                      of tokens; the default is exact matching
FUZZY_EDIT_DISTANCE = 3

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

import django  # NOQA
django.setup()

from stripey_app.models import (Chapter, Verse, MsVerse, Book,
                                get_all_verses, Variant, Reading,
                                Stripe, MsStripe, Algorithm)  # NOQA
from django.db import transaction, reset_queries, connections  # NOQA
from django.core.exceptions import ObjectDoesNotExist  # NOQA

logger = logging.getLogger(__name__)


class Collator(object):
    def __init__(self, algo, *, port=7369, nworkers=3, timeout=900):
        self.algo = algo
        self.port = port
        self.workers = []
        self.queue = multiprocessing.Queue()
        self._collatex_errors = multiprocessing.Value('i')
        self._successful_collations = multiprocessing.Value('i')
        self.cx = CollateXService(port, timeout, max_parallel=nworkers * 2)
        self.cx.start()

        # We need to close the database connections before forking new procecsses.
        # This way each process will create a new connection when it needs one.
        connections.close_all()
        for i in range(nworkers):
            logger.debug("Starting worker {}".format(i + 1))
            t = multiprocessing.Process(target=self.worker)
            t.daemon = True
            t.start()
            self.workers.append(t)

    def quit(self):
        # Tell the workers to quit
        for i in self.workers:
            self.queue.put(None)

        logger.debug("Joining workers")
        for t in self.workers:
            t.join()

        # Tell collatex to quit
        self.cx.quit()

        logger.debug("Done")

    def worker(self):
        while True:
            args = self.queue.get()
            if args is None:
                logger.debug("Worker quitting...")
                return

            self.collate_verse(*args)

    def collate_book(self, book_obj, chapter_ref=None):
        """
        Collate a particular book

        @param book_obj: db book object
        @chapter_ref: (int) chapter number to collate (or None for all)
        """
        logger.info("Collating book {}:{}".format(book_obj.num, book_obj.name))
        for chapter_obj in Chapter.objects.filter(book=book_obj).order_by('num'):
            if chapter_ref is None or chapter_ref == chapter_obj.num:
                logger.info("Collating chapter {} {}".format(book_obj.name, chapter_obj.num))
                all_verses = get_all_verses(book_obj, chapter_obj)
                for v, mss in all_verses:
                    verse_obj = Verse.objects.get(chapter=chapter_obj, num=v)
                    # 1. check we've not already done this one
                    if Variant.objects.filter(verse=verse_obj, algorithm=self.algo):
                        logger.debug("Skipping {} ({}) as it's already done".format(v, self.algo))
                        continue
                    # 2. queue up the new collation
                    mss_refs = []
                    for ms, msverses in mss:
                        mss_refs.append((ms.id, [x.id for x in msverses]))

                    self.queue.put((book_obj, chapter_obj, verse_obj, mss))
                    # 3. tidy up django's query list, to free up some memory
                    reset_queries()

    @transaction.atomic
    def collate_verse(self, book_obj, chapter_obj, verse_obj, mss):
        """
        We take simple integers for the book, chapter and verse so that
        we can operate in a separate process safely.
        """
        logger.debug("Collating verse {}:{}:{} ({})".format(chapter_obj.book.name,
                                                            chapter_obj.num,
                                                            verse_obj.num,
                                                            self.algo.name))
        start = time.time()
        witnesses = []
        for ms, verses in mss:
            for verse in verses:
                if verse.text:
                    witnesses.append({'id': str(verse.id),
                                      'content': verse.text})

        try:
            # Get the apparatus from collatex - this is the clever bit...
            collation = self.cx.query(witnesses, self.algo.name)
        except Exception as e:
            # Collate failed
            with self._collatex_errors.get_lock():
                logger.error("Collate has failed us: {} (count={})".format(e, self._collatex_errors.value))
                self._collatex_errors.value += 1
                if self._collatex_errors.value > MAX_COLLATEX_ERRORS:
                    self.cx.restart()
                    self._collatex_errors.value = 0
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
            variant.algorithm = self.algo
            variant.save()
            sys.stdout.write('v')

            for j, sigil in enumerate(collation['witnesses']):
                # sigil = a witness = a verse object's id
                ms_verse = MsVerse.objects.get(id=int(sigil))
                text = str(' '.join([x.strip() for x in entry[j]]))

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
        for readings in set([tuple(a) for a in list(mv_readings.values())]):
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
                stripe.algorithm = self.algo
                stripe.save()
                stripe.readings = readings
                stripe.save()
                sys.stdout.write('s')
                sys.stdout.flush()

            stripe_mapping[readings] = stripe

        for ms_verse, readings in list(mv_readings.items()):
            # Save our hand-stripe
            hs = MsStripe()
            hs.stripe = stripe_mapping[tuple(readings)]
            hs.ms_verse = ms_verse
            hs.save()

        t = time.time() - start
        sys.stdout.write('\n')
        logger.debug("  .. added {} manuscript stripes".format(len(mv_readings)))
        logger.debug("  .. added {} entries in {} secs".format(count, round(t, 3)))

        with self._successful_collations.get_lock():
            self._successful_collations.value += 1
            logger.debug("SUCCESSFUL COLLATIONS: {}".format(self._successful_collations.value))

        with self._collatex_errors.get_lock():
            logger.debug("CURRENT COLLATEX ERROR COUNT: {}".format(self._collatex_errors.value))


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

    logger.warning(" > Deleting {} objects".format(len(to_del)))
    print()
    for i, x in enumerate(to_del):
        x.delete()
        sys.stdout.write("\r > {} ({}%)   ".format(i + 1, i * 100.0 / len(to_del)))
    print()

    logger.warning("Done")


def collate_all(algo, *, chapter_ref=None, port=7369, timeout=900, workers=3):
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

    coll = Collator(algo_obj, port=port, timeout=timeout, nworkers=workers)
    for book in Book.objects.all():
        if mubook is None or book.num == mubook:
            coll.collate_book(book, muchapter)

    coll.quit()


def tests():
    """
    Collate everything using the collatex service
    """
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

    dek_resp = {'witnesses': ['1', '2', '3', '4', '5'], 'table': [[['This ', 'is '], ['This ', 'is '], ['This ', 'is '], ['These ', 'are '], ['This ', 'is ']], [['a '], [], ['a '], [], ['a ']], [[], [], ['testimony'], [], ['a ']], [['test'], ['test'], [], ['tests'], ['test']]]}
    nw_resp = {'witnesses': ['1', '2', '3', '4', '5'], 'table': [[[], [], [], [], ['This ']], [['This '], [], ['This '], [], ['is ']], [['is ', 'a '], ['This ', 'is '], ['is ', 'a '], ['These ', 'are '], ['a ', 'a ']], [['test'], ['test'], ['testimony'], ['tests'], ['test']]]}
    med_resp = {'witnesses': ['1', '2', '3', '4', '5'], 'table': [[[], [], [], [], ['This ']], [['This '], [], ['This '], ['These '], ['is ']], [['is '], ['This '], ['is '], ['are '], ['a ']], [['a '], ['is '], ['a '], [], ['a ']], [['test'], ['test'], ['testimony'], ['tests'], ['test']]]}

    cx = CollateXService(port=12345)
    cx.start()

    try:
        resp = cx.query(witnesses, 'dekker')
        assert resp == dek_resp, resp
        resp = cx.query(witnesses, 'needleman-wunsch')
        assert resp == nw_resp, resp
        resp = cx.query(witnesses, 'medite')
        assert resp == med_resp, resp
        logger.info("All tests passed")
    finally:
        cx.quit()


class TimeoutException(Exception):
    pass


class CollateXService(object):
    """
    Manage and query collatex
    """
    _popen = None

    def __init__(self, port, timeout=900, max_parallel=10):
        self._port = port
        self._timeout = timeout
        self._max_parallel = max_parallel
        self.lock = multiprocessing.RLock()
        # Is Collatex OK and usable?
        self._collatex_ok = multiprocessing.Event()
        # How many queries are currently in collatex?
        self._collatex_active = multiprocessing.Value('i')

    def _start_service(self):
        """
        Actually start the java web service for collatex
        """
        # Give it 10 goes to let the port become available
        for i in range(10):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.connect(('localhost', self._port))
                except ConnectionRefusedError:
                    break
                else:
                    logger.warning("Something is already listening on port {}".format(self._port))
                    time.sleep(1)
        else:
            raise RuntimeError("Something is already listening on port {}".format(self._port))

        logger.info("Starting CollateX service on port {}".format(self._port))
        cmd = ["java", "-jar", COLLATEX_JAR, "--http",
               "--max-parallel-collations", str(self._max_parallel),
               "-p", str(self._port)]
        logger.debug("Launching collatex: {}".format(' '.join(cmd)))
        self.__class__._popen = subprocess.Popen(cmd)
        time.sleep(5)
        if self.__class__._popen.poll() is None:
            logger.debug("Collatex process is running")
        else:
            logger.critical("Collatex process has quit - so shall we")
            raise IOError("Collatex has quit")

    def _stop_service(self):
        logger.info("Terminating CollateX service immediately ({})"
                    .format(self.__class__._popen.pid))
        while self.__class__._popen.poll() is None:
            logger.info("Terminate...")
            self._popen.terminate()
            self.__class__._popen.communicate()
            time.sleep(1)

        try:
            os.kill(self.__class__._popen.pid, 0)
        except OSError:
            pass
        else:
            # It's still alive... kill it the old fashioned way
            logger.info("Kill...")
            os.kill(self.__class__._popen.pid, 9)
            time.sleep(1)

        self.__class__._popen = None
        logger.debug("Collatex stopped")
        time.sleep(5)

    def restart(self):
        logger.debug("Restart requested, waiting for an opportunity...")
        self._collatex_ok.clear()
        while True:
            with self._collatex_active.get_lock():
                logger.debug("Active count is {}".format(self._collatex_active.value))
                if self._collatex_active.value == 0:
                    break
                time.sleep(1)

        logger.info("Restarting...")
        self._stop_service()
        return self.start()

    def start(self):
        """
        Does a test and starts the service if it fails.
        """
        with self.lock:
            if self.__class__._popen is None:
                self._start_service()

            if not self._test():
                logger.warning("CollateX service failed the test - restarting it")
                self.restart()
                if not self._test():
                    raise IOError("Even after restarting CollateX failed the test - aborting")

            self._collatex_ok.set()

    def quit(self):
        logger.info("Quitting...")
        self._stop_service()
        self._collatex_ok.clear()

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
            self.query(witnesses, 'dekker', force=True)
        except Exception:
            logger.debug("Test failure: ", exc_info=True)
            return False
        else:
            return True

    def query(self, witnesses, algorithm="dekker", quiet=False, force=False):
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

        @param witnesses: Se above
        @param algorithm: One of the supported algorithms
        @param quiet: don't chat too much
        @param force: do the query even if we don't know that collatex is ready
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
        url = "http://localhost:{}/collate".format(self._port)
        headers = {'Content-Type': 'application/json',
                   'Accept': 'application/json'}

        if force is False:
            # Wait until we can use the collatex service
            self._collatex_ok.wait()

        # Say we're using it
        with self._collatex_active.get_lock():
            self._collatex_active.value += 1

        try:
            if not quiet:
                logger.debug("Start time {}".format(time.ctime()))
            start = time.time()
            with timeout(self._timeout):
                req = urllib.request.Request(url, data.encode('utf-8'), headers)
                # print req.get_method(), data
                resp = urllib.request.urlopen(req)
                # print(resp.info())
                ret = json.loads(resp.read().decode('utf-8'))
                end = time.time()
                if not quiet:
                    logger.info("[{}] {} ({}) - {} secs"
                                .format(resp.getcode(), url, algorithm, end - start))
            return ret
        finally:
            with self._collatex_active.get_lock():
                self._collatex_active.value -= 1


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
    val = input("{}: ".format(question)).strip()
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
    parser.add_argument('--test', help="Just run tests and exit", default=False, action='store_true')
    parser.add_argument('-c', '--clean', help="Clean out old colation before adding new",
                        default=False, action='store_true')
    parser.add_argument('-f', '--force', help="Don't ask any questions - just do it!",
                        default=False, action='store_true')
    parser.add_argument('-t', '--timeout', help="How long until we shoot collatex? (default 900 seconds)",
                        default=900, type=int)
    parser.add_argument('-j', '--workers', help="How many parallel workers to use? (default 3)",
                        default=3, type=int)
    parser.add_argument('-p', '--collatex-port', help="What port on which to run the collatex server",
                        default=7369, type=int)
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
                print("Aborting")
                sys.exit(1)
            for a in algos:
                drop_all(a, args.chapter)

        for a in algos:
            collate_all(a, chapter_ref=args.chapter, port=args.collatex_port,
                        timeout=args.timeout, workers=args.workers)

        print("\n** Don't forget to delete the old picklify data")
