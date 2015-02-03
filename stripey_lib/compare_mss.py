#!/usr/bin/python
"""
Compare the text of two (or more) manuscripts in stripey
"""

import os
import sys

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

from stripey_app.models import Book, Chapter, MsVerse, Verse
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction


def compare(book, chapter, witnesses, hide_identical):
    print "Comparison of {} in book {}, chapter {}".format(', '.join(witnesses), book, chapter)

    try:
        book_obj = Book.objects.get(num=book)
    except ObjectDoesNotExist:
        print "Can't find book {}".format(book)
    try:
        chapter_obj = Chapter.objects.get(num=chapter, book=book_obj)
    except ObjectDoesNotExist:
        print "Can't find chapter {}".format(chapter)

    #~ for verse in MsVerse.objects.filter(verse__chapter=chapter_obj).filter(hand__manuscript__ga=:
        #~ print verse

    n = 0
    for verse in Verse.objects.filter(chapter=chapter_obj).order_by('num'):
        texts = {}
        output = u"{}\n".format(verse)
        for wit in witnesses:
            readings = MsVerse.objects.filter(verse=verse).filter(hand__manuscript__ga=wit)
            for reading in readings:
                if reading.hand.name == 'firsthand':
                    ref = wit
                else:
                    ref = '{} ({})'.format(ref, reading.hand.name)
                my_text = reading.raw_text.strip()
                if my_text in texts:
                    output += u"  > {} is identical to {}\n".format(ref, texts[my_text])
                else:
                    texts[my_text] = ref
                    output += u"  > {: <25}:{}\n".format(ref, my_text)

        if hide_identical and len(texts) == 1:
            continue

        n += 1
        print output

    print "Showing {} differences".format(n)






if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Populate sqlite database")
    parser.add_argument('-b', '--book',
                        required=True, help='Book to display')
    parser.add_argument('-c', '--chapter',
                        required=True, help='Chapter to display')
    parser.add_argument('-i', '--hide-identical-readings', action="store_true",
                        default=False, help='Hide verses where all readings are identical (default False)')
    parser.add_argument('witness', nargs='+',
                        help='Witnesses to compare')

    args = parser.parse_args()
    compare(args.book, args.chapter, args.witness, args.hide_identical_readings)
