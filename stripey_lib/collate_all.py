#!/usr/bin/python

import os
import sys

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

from stripey_app.models import Book, Chapter, Verse, Hand, get_all_verses, CollatedVerse

import logging
logger = logging.getLogger('collate_all.py')

from stripey_lib import collatex as _mod
os.environ['COLLATE_JAR_PATH'] = os.path.dirname(_mod.__file__)
logger.debug(os.environ['COLLATE_JAR_PATH'])
from stripey_lib.collatex import collatex

def collate_verse(v, mss):
    logger.debug("..verse {}".format(v))
    collation = collatex.Collation()
    for ms, verses in mss:
        for verse in verses:
            collation.add_witness(str(verse.id), verse.text)
    rows = collation.get_alignment_table().rows
    
    #print (v, [(row.sigil,
    #       [unicode(i.token) for i in row.cells])
    #        for row in rows])

    # Replace the existing collation for this verse
    # 1. delete the old
    old = CollatedVerse.objects.filter(verse=v)
    for cv in old:
        cv.delete()
    # 2. add the new
    count = 0
    for row in rows:
        verse = Verse.objects.get(id=int(row.sigil))
        for i, cell in enumerate(row.cells):
            cv = CollatedVerse()
            cv.verse = verse
            cv.variant = i
            cv.text = unicode(cell.token)
            cv.save()
            count += 1
            sys.stdout.write(".")
            sys.stdout.flush()
    logger.debug("   .. added {} entries".format(count))


def collate_book(book_obj):
    logger.info("Collating book {}:{}".format(book_obj.num, book_obj.name))
    for chapter_obj in Chapter.objects.filter(book=book_obj).order_by('num'):
        logger.info("Collating chapter {} {}".format(book_obj.name, chapter_obj.num))
        all_verses = get_all_verses(book_obj, chapter_obj)
        for v, mss in all_verses:
            collate_verse(v, mss)
                
def collate_all():
    for book in Book.objects.all():
        collate_book(book)
    
if __name__ == "__main__":
    logger.info("Collating everything...")
    collate_all()
