#!/usr/bin/python

import os
import re
import string

verse_re = re.compile("^([0-9]+)(.*)$")
idents = string.uppercase

class Verse(object):
    # {verse_num: {'text': 'A', 'text2': 'B', ...}}
    ident_map = {}
    ident_tracker = {}

    def __init__(self, num, text):
        self.num = num
        self.text = text
        if not text:
            self.ident = "-"
        else:
            v_map = self.ident_map.get(num, {})
            self.ident_map[num] = v_map
            ident = v_map.get(text)
            if not ident:
                i = self.ident_tracker.get(num, 0)
                ident = idents[i]
                i += 1
                self.ident_tracker[num] = i
                v_map[text] = ident
            self.ident = ident

    def __repr__(self):
        return "%s: %s" % (self.num, self.text)

class MS(object):
    def __init__(self, ms_file):
        self.name = ms_file.split(".")[0]
        self.verses = []
        with open(ms_file) as fh:
            for l in fh.readlines():
                m = verse_re.match(l)
                if not m:
                    raise ValueError("Dodgy line: %s" % (l, ))
                v, t = m.groups()
                t = ' '.join(t.split())
                v = int(v)
                self.verses.append(Verse(v, t))

    def __repr__(self):
        return self.name + ": " + "".join([x.ident for x in self.verses])

mss = []
files = os.listdir(".")
files.sort()

for i in files:
    if not i.endswith(".txt"):
        continue
    mss.append(MS(i))
    
print "Loaded %d manuscripts" % (len(mss), )

for m in mss:
    print m

for v in range(6):
    print
    for m in mss:
        print m.name, m.verses[v]
