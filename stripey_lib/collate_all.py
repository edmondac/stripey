#!/usr/bin/python

import os
import sys

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

from stripey_app.models import Book, Chapter, Verse, Hand, get_all_verses

import logging
logger = logging.getLogger('collate_all.py')

from stripey_lib import collatex as _mod
os.environ['COLLATE_JAR_PATH'] = os.path.dirname(_mod.__file__)
logger.debug(os.environ['COLLATE_JAR_PATH'])
from stripey_lib.collatex import collatex

def collate_verse(v, mss):
    logger.debug("..verse {}".format(v))
    collation = collatex.Collation()
    for ms in mss:
        for hand, greek in ms[1]:
            collation.add_witness('{}:{}'.format(ms[0].ms_ref, hand), greek)
    rows = collation.get_alignment_table().rows
    
    print (v, [(row.sigil,
           [unicode(i.token) for i in row.cells])
            for row in rows])

    # TODO: put that collation into the database


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
