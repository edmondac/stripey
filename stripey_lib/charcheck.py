#!/usr/bin/python


import os
import sys
import unicodedata

sys.path.append('../stripey_dj/')
from stripey_lib import xmlmss

def check_chars(uni):
    #print uni
    s = None
    for char in unicodedata.normalize('NFD', uni):
        name = unicodedata.name(char)
        if name.split()[0] not in ('GREEK', 'SPACE', 'COMBINING', 'APOSTROPHE'):
            s = u"Char error in str '{}' - char '{}' ({})".format(uni, char, name)
        #            if (not unicodedata.combining(c) and
        #                c not in IGNORE_CHARS)])
    #~ if inp != out:
        #~ logger.debug(u"Normalised greek input:\ninp: \t{}\nout: \t{}".format(inp, out))
    return s

def check(folder):
    files = [x for x in os.listdir(folder) if x.endswith('.xml')]
    for i, f in enumerate(files):
        print "{}/{} : {}".format(i+1, len(files), f)
        path = os.path.join(folder, f)
        try:
            obj = xmlmss.Manuscript(f, path)
        except Exception:
            print "ERROR parsing: ", path
            raise
        for ch in obj.chapters.values():
            for verse_list in ch.verses.values():
                for vs in verse_list:
                    for i, hand in enumerate(vs.hands):

                        stat = check_chars(vs.texts[i])

                        if stat:
                            print obj.ms_desc['Liste'], ch.num, vs.num, hand
                            print stat


if __name__ == "__main__":
    check(sys.argv[1])
