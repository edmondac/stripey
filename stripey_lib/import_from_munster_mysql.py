# -*- coding: utf-8 -*-
#!/usr/bin/python

import os
import sys
import re
import MySQLdb
from collections import defaultdict
from functools import partial
import unicodedata

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

#~ from stripey_app.models import ManuscriptTranscription, MsBook
#~ from django.core.exceptions import ObjectDoesNotExist
#~ from django.db import transaction

from stripey_lib import xmlmss

import logging
logger = logging.getLogger('import_from_munster_mysql.py')

DEFAULT_BASE_TEXT = "/home/ed/itsee_coding/itsee_git_repos/data/transcriptions/ITSEE/NT/GRC/editions/NA28/04_NA28.xml"

ms_re = re.compile("([0-9]+)_([LPNATRS0-9]+)\.xml")


#~ class UnexpectedFilename(Exception):
    #~ pass
#~
#~ @transaction.commit_on_success
#~ def load_ms(folder, f):
    #~ """
    #~ Load a single XML file
    #~ """
    #~ # We expect the files to be called, e.g. 23_424.xml, or 04_NA27.xml
    #~ # == book 23 (1 John), ms 424.
    #~ match = ms_re.match(f)
    #~ if not match:
        #~ raise UnexpectedFilename("Unexpected filename {}".format(f))
    #~ book_num = int(match.group(1))
    #~ name = match.group(2)
    #~ try:
        #~ m = ManuscriptTranscription.objects.get(ms_ref=name)
    #~ except ObjectDoesNotExist:
        #~ m = ManuscriptTranscription()
        #~ m.ms_ref = name
    #~ else:
        #~ gotit = MsBook.objects.filter(manuscript=m, book__num=book_num).count()
        #~ if gotit:
            #~ logger.debug("Already loaded book {} for ms {} - skipping".format(book_num, name))
            #~ return
#~
    #~ m.load_xml(os.path.join(folder, f))
#~
#~
#~ def load_all(folder):
    #~ """
    #~ Load all the XML files in a folder (and subfolders) into the database
    #~ """
    #~ logger.info("Loading everything in {}".format(folder))
    #~ failures = []
    #~ for path, dirs, files in os.walk(folder):
        #~ for f in [x for x in files if x.endswith('.xml')]:
            #~ try:
                #~ load_ms(path, f)
            #~ except UnexpectedFilename as e:
                #~ logger.warning("{} failed to load: {}".format(f, e))
                #~ failures.append("{} ({})".format(f, e))
            #~ except Exception as e:
                #~ logger.exception("{} failed to load: {}".format(f, e))
                #~ failures.append("{} ({})".format(f, e))
                #~ #raise
#~
    #~ if failures:
        #~ logger.error("Load failed for: \n{}".format('\n\t'.join(failures)))


class Translator(object):
    def __init__(self):
        self.uni_from = u'.[] abgdezhqiklmnxoprs~tufcyw'
        self.uni_to = u'___ αβγδεζηθικλμνξοπρσςτυφχψω'
        self.translate_table = {ord(frm): self.uni_to[i]
                                for i, frm in enumerate(self.uni_from)}

    def __call__(self, unicode_in):
        for x in unicode_in:
            if x not in self.uni_from:
                print x
                print unicode_in
                raise ValueError((x, unicode_in))
        ret = unicode_in.translate(self.translate_table)
        ret = ret.replace(u'_', u'')
        return ret

translate = Translator()


class Witness(object):
    def __init__(self, name):
        self.name = name
        self.chapters = defaultdict(partial(defaultdict, dict))

    def add_word(self, chapter, verse, word, greek):
        vs = self.chapters[int(chapter)][int(verse)]
        if int(word) in vs:
            # Already got this word - check it's the same
            if greek != vs[int(word)]:
                #~ # OK - if we're just one word out then accept it...
                #~ if (greek == vs.get(int(word) + 2) or
                        #~ greek == vs.get(int(word) - 2)):
                    #~ print "Off by one for word - accepting"
                    #~ return
#~
                #~ if ((greek[-1] == u'ν' and
                        #~ greek[:-1] == vs[int(word)]) or
                    #~ (vs[int(word)][-1] == u'ν' and
                        #~ greek == vs[int(word)][:-1])):
                    #~ print "Difference in final nu - accepting"
                    #~ return

                print "ERROR - already got this word but it's different:"
                print " >> {}:{}/{}".format(chapter, verse, word)
                print u" >> old: {}".format(vs[int(word)])
                print u" >> new: {}".format(greek)
                raise ValueError
            return

        vs[int(word)] = greek


class BaseText(object):
    chapters = {}
    base_text = None  # set me somewhere...

    def __init__(self):
        cls = self.__class__
        if not cls.chapters:
            cls._load_xml()

    @classmethod
    def _load_xml(cls):
        """
        Load the NA28 text from the supplied filename
        """
        obj = xmlmss.Manuscript("BASE", cls.base_text)
        for ch in obj.chapters.values():
            chapter = {}
            cls.chapters[int(ch.num)] = chapter
            for verse_list in ch.verses.values():
                for vs in verse_list:
                    verse = {}
                    chapter[int(vs.num)] = verse
                    texts = vs.get_texts()
                    if not texts:
                        # No text in this verse (e.g. John 5:4)
                        continue

                    assert len(texts) == 1, (ch.num, vs.num, texts)
                    text = texts[0][0]
                    for i, word in enumerate(text.split()):
                        verse[(i + 1) * 2] = cls._unaccent(word)

    @classmethod
    def _unaccent(cls, s):
        """
        Remove accents (and some other chars) from greek text
        """
        ret = u''.join(c for c in unicodedata.normalize('NFD', s)
                       if unicodedata.category(c) != 'Mn')
        ret = ret.replace(u'’', u'')
        return ret

    @classmethod
    def get_text(cls, ch, vs, start, end=None):
        """
        Return the greek text from the specified word or range
        """
        verse = cls.chapters[ch][vs]
        if end != start:
            words = []
            for i in range(start, end):
                if i in verse:
                    words.append(verse[i])
            return ' '.join(words)

        return verse.get(start, '')


def load_witness(witness, cur):
    """
    Load a particular witness from the db
    """
    witness_obj = Witness(witness)
    base_text = BaseText()

    # We trust that the rows come out in the order they went in...
    cur.execute("SELECT * FROM Ch18Att WHERE HS = %s", (witness, ))
    field_names = [i[0] for i in cur.description]

    while True:
        row = cur.fetchone()
        if row is None:
            print "All done"
            break

        obj = {field_names[i]: val for i, val in enumerate(row)}
        assert obj['BCH'] == obj['ECH'], obj
        assert obj['B'] == 4, obj
        assert obj['BCH'] == 18, obj

        #~ if obj['RNR'] == -1:
            #~ # Nestle agrees with Majorty text in this variant unit
            #~ continue

        rdg = obj['RDG'].strip()

        # Square brackets...
        rdg = rdg.decode('latin1').encode('utf8')
        rdg = rdg.replace(r'»', '[')
        rdg = rdg.replace(r'¼', ']')

        if ':' in rdg:
            print "Found verse def: {}".format(rdg), obj
            continue
        if '(' in rdg:
            print "Found bracket: {}".format(rdg), obj
            continue

        if obj['BV'] != obj['EV']:
            print "Reading bridges verse boundary: {}".format(rdg), obj
            continue
        if obj['RDG'] == '\x88 \xbb2\xbca\r':
            print "Wierd: {}".format(obj['RDG'])
            continue
        if obj['SUFF'] == '*':
            # Original firsthand reading (before he corrected it)
            continue

        assert obj['SUFF'].strip() == '', obj
        assert obj['BV'] == obj['EV'], obj

        # Text not there...
        if rdg == 'DEF':
            greek = base_text.get_text(obj['BCH'], obj['BV'], obj['BW'], obj['EW'])

        elif rdg.lower() != rdg:
            print "Found upper case letters: {}".format(rdg), obj
            continue

        else:
            # Remove numerical ranges
            rdg = re.sub('[0-9]+\-[0-9]+', '', rdg)

            # Translate to unicode greek
            greek = translate(unicode(rdg))

        print witness, obj['BV'], obj['BW'], obj['EW'], greek

        if obj['BW'] == obj['EW']:
            # simple case
            witness_obj.add_word(obj['BCH'], obj['BV'], obj['BW'], greek)

        else:
            range_length = 1 + (obj['EW'] - obj['BW']) / 2

            if range_length == len(greek.split()):
                word = obj['BW']
                for gw in greek.split():
                    witness_obj.add_word(obj['BCH'], obj['BV'], word, gw)
                    word += 2




        #~ if current_verse != obj['BV']:
            #~ if current_verse is not None:
                #~ # finish the last verse
                #~ print witness, current_verse, ' '.join(verse_text)
#~
            #~ current_verse = obj['BV']
#~
        #~ if current_word is not None:
            #~ assert obj['BW'] > current_word, (current_word, obj)
#~
        #~ current_word = obj['EW']
#~
        #~ verse_text.append(greek)


def load_all(host, db, user, password):
    """
    Connect to the mysql db and loop through what we find
    """
    # Phase 1: load readings
    # TODO: Phase 2: load variant units

    db = MySQLdb.connect(host=host, user=user, passwd=password, db=db)
    cur = db.cursor()
    cur.execute("SELECT DISTINCT HS FROM Ch18Att")

    witnesses = set()
    for row in cur.fetchall():
        witnesses.add(row[0])

    for wit in witnesses:
        wit = 'P66'  #FIXME
        load_witness(wit, cur)
        raise SystemExit


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--mysql-user', required=True, help='User to connect to mysql with')
    parser.add_argument('-p', '--mysql-password', required=True, help='User to connect to mysql with')
    parser.add_argument('-s', '--mysql-host', required=True, help='User to connect to mysql with')
    parser.add_argument('-d', '--mysql-db', required=True, help='User to connect to mysql with')
    parser.add_argument('-b', '--base-text', default=DEFAULT_BASE_TEXT,
                        help='XML filename of base text (default {})'.format(DEFAULT_BASE_TEXT))
    parser.add_argument('-t', '--test', help="Just run tests and exit", default=False, action='store_true')
    args = parser.parse_args()

    BaseText.base_text = args.base_text

    load_all(args.mysql_host,
             args.mysql_db,
             args.mysql_user,
             args.mysql_password)


if __name__ == "__main__":
    main()
