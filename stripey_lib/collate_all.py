#!/usr/bin/python

import os
import time
import sys
#~ from django.utils.encoding import smart_unicode

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

from stripey_app.models import (Book, Chapter, Verse, Hand,
                                get_all_verses, CollatedVerse, Variant,
                                Reading)
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

import logging
logger = logging.getLogger('collate_all.py')

from stripey_lib import collatex as _mod
os.environ['COLLATE_JAR_PATH'] = os.path.dirname(_mod.__file__)
logger.debug(os.environ['COLLATE_JAR_PATH'])
from stripey_lib.collatex import collatex

@transaction.commit_on_success
def collate_verse(chapter_obj, v, mss):
    logger.debug("Collating verse {}:{}:{}".format(chapter_obj.book.name, chapter_obj.num, v))
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
    for i, entry in enumerate(ap.entries):
        # entry = appararus entry = a variant unit
        variant = Variant()
        variant.chapter = chapter_obj
        variant.verse_num = v
        variant.variant_num = i
        variant.save()
        sys.stdout.write('v')

        for sigil in ap.sigli:
            # sigil = a witness = a verse object's id
            verse = Verse.objects.get(id=int(sigil))

            try:
                text = unicode(entry.get_phrase(sigil))
            except Exception as e:
                if "This ngram is empty!" in str(e):
                    text = ""
                else:
                    logger.error("Error getting phrase for {}".format(verse))
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

            # Save our collated verse
            cv = CollatedVerse()
            cv.verse = verse
            cv.reading = reading
            cv.save()

            count += 1
            sys.stdout.write("+")
            sys.stdout.flush()

    t = time.time() - start
    sys.stdout.write('\n')
    logger.debug("   .. added {} entries in {} secs".format(count, t))


def collate_book(book_obj):
    logger.info("Collating book {}:{}".format(book_obj.num, book_obj.name))
    for chapter_obj in Chapter.objects.filter(book=book_obj).order_by('num'):
        logger.info("Collating chapter {} {}".format(book_obj.name, chapter_obj.num))
        all_verses = get_all_verses(book_obj, chapter_obj)
        for v, mss in all_verses:
            # 1. delete the old (will cascade)
            variants = Variant.objects.filter(chapter=chapter_obj, verse_num=v)
            variants.delete()
            collate_verse(chapter_obj, v, mss)
        raise SystemExit
                
def collate_all():
    for book in Book.objects.all():
        collate_book(book)
    
if __name__ == "__main__":
    logger.info("Collating everything...")
    collate_all()
