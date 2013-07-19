#!/usr/bin/python

import os
import time
import sys

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

from stripey_app.models import (Book, Chapter, Verse, MsVerse,
                                get_all_verses, Variant, Reading,
                                Stripe, MsStripe)
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

import logging
logger = logging.getLogger('collate_all.py')

from stripey_lib import collatex as _mod
os.environ['COLLATE_JAR_PATH'] = os.path.dirname(_mod.__file__)
logger.debug(os.environ['COLLATE_JAR_PATH'])
from stripey_lib.collatex import collatex


@transaction.commit_on_success
def collate_verse(chapter_obj, verse_obj, mss):
    logger.debug("Collating verse {}:{}:{}".format(chapter_obj.book.name,
                                                   chapter_obj.num,
                                                   verse_obj.num))
    start = time.time()
    collation = collatex.Collation()
    assert not collation.get_apparatus().entries
    for ms, verses in mss:
        for verse in verses:
            collation.add_witness(str(verse.id), verse.text)

    # Get the apparatus from collatex - this is the clever bit...
    ap = collation.get_apparatus()
    logger.debug(" .. collatex produced {} entries for {} sigli".format(
                 len(ap.entries),
                 len(ap.sigli)))

    count = 0

    # Store the readings per ms_verse for later
    mv_readings = {}

    for i, entry in enumerate(ap.entries):
        # entry = appararus entry = a variant unit
        variant = Variant()
        variant.chapter = chapter_obj
        variant.verse = verse_obj
        variant.variant_num = i
        variant.save()
        sys.stdout.write('v')

        for sigil in ap.sigli:
            # sigil = a witness = a verse object's id
            ms_verse = MsVerse.objects.get(id=int(sigil))

            try:
                text = unicode(entry.get_phrase(sigil))
            except Exception as e:
                if "This ngram is empty!" in str(e):
                    text = ""
                else:
                    logger.error("Error getting phrase for {}".format(ms_verse))
                    raise

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
            # 1. delete the old (will cascade)
            variants = Variant.objects.filter(verse=verse_obj)
            variants.delete()
            stripes = Stripe.objects.filter(verse=verse_obj)
            stripes.delete()
            # 2. make the new collation
            collate_verse(chapter_obj, verse_obj, mss)


def collate_all():
    for book in Book.objects.all():
        collate_book(book)


if __name__ == "__main__":
    logger.info("Collating everything...")
    collate_all()
