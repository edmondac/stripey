#!/usr/bin/python


import os
import sys
import unicodedata
import codecs

sys.stdout = codecs.open('output', 'w', encoding='utf-8')

sys.path.append('../stripey_dj/')
from stripey_lib import xmlmss

def check_chars(uni):
    #print uni
    s = None
    for i, char in enumerate(unicodedata.normalize('NFD', uni)):
        name = unicodedata.name(char)
        if name.split()[0] not in ('GREEK', 'SPACE', 'COMBINING', 'APOSTROPHE'):
            s = u"Bad character at loc {} of '{}' - {}".format(i+1, uni, name)

    return s

def check(folder):
    files = [x for x in os.listdir(folder) if x.endswith('.xml')]
    for i, f in enumerate(files):
        print "-- Checking {}/{} : {}".format(i+1, len(files), f)
        path = os.path.join(folder, f)
        obj = xmlmss.Manuscript(f, path)

        for ch in obj.chapters.values():
            for verse_list in ch.verses.values():
                for vs in verse_list:
                    for i, hand in enumerate(vs.hands):
                        stat = check_chars(vs.texts[i])
                        if stat:
                            print u"ERROR: {} : {}:{}: {}".format(f, ch.num, vs.num, stat)


if __name__ == "__main__":
    check(sys.argv[1])
