# -*- coding: utf-8 -*-
"""
Loads, parses and classifies the text from manuscripts.
Notes:
* The first ms you load becomes your base text.
* I'm not currently doing anything with the book's title, e.g. κατα ιωαννην
* I'm not handling gap tags very smartly
"""

import os
import urllib2
import string
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('XmlMss')
import xml.etree.ElementTree as ET
from collections import OrderedDict

base_url = "http://www.iohannes.com/XML/"
idents = string.lowercase


class Verse(object):
    """
    Takes an ElementTree element representing a verse and parses it.
    """
    # {(chapter, verse_num): {'text': 'A', 'text2': 'B', ...}}
    ident_map = {}
    ident_tracker = {}

    def __init__(self, element, chapter):
        self.element = element
        self.chapter = chapter

        # This is the verse tag - extract the verse number
        self.num = self.element.attrib['n']

        # Note - we can have multiple different texts and idents if
        # correctors have been at work
        self.hands = []
        self.texts = []
        self.idents = []

        self._find_hands()
        if not self.hands:
            # Only one scribe at work here
            self.hands = [None]

        for hand in self.hands:
            text = self._parse(self.element, hand)
            text = self._post_process(text)
            self.texts.append(text)
            self.idents.append(self._calculate_ident(text))

    def show_all(self):
        """
        Show this verse's ident, hands, text etc.
        """
        if self.hands[0] != None:
            print "Verse %s" % (self.num, )
            for i, hand in enumerate(self.hands):
                print "\t%s (%s) : %s" % (self.idents[i],
                                          hand,
                                          self.texts[i])
        else:
            print "Verse %s : %s : %s" % (self.num,
                                          self.idents[0],
                                          self.texts[0])

    def _get_ident_id(self, hand):
        """
        Find the index in our arrays of this hand - or None if this
        hand isn't present.
        """
        if hand in self.hands:
            return self.hands.index(hand)
        elif hand == 'firsthand':
            if len(self.hands) == 1:
                return 0
            else:
                raise ValueError("Too many hands and firsthand not found")
        else:
            return None

    def get_ident(self, hand):
        """
        Return the ident for the particular scribe
        """
        i = self._get_ident_id(hand)
        if i is not None:
            # Found this hand
            return self.idents[i]
        else:
            # We don't have this hand - return empty
            return ' '

    def _rdg_hand(self, el):
        """
        Return the designator for the scribe
        """
        hand = el.attrib.get('hand')
        if not hand:
            hand = el.attrib.get('auto-%s'
                                 % (el.attrib['n'], ))
        return hand
                
    def _find_hands(self):
        """
        Work out what different hands have been at work,
        e.g. firsthand, correctors etc.
        """
        for i in self.element.iter():
            if i.tag.endswith('rdg'):
                hand = self._rdg_hand(i)
                if hand not in self.hands:
                    self.hands.append(hand)

    def _calculate_ident(self, text):
        """
        Calculate the unique text ident
        @param text: the text to identify
        @returns: the ident for this text
        """
        if not text:
            ident = "-"

        else:
            key = (self.chapter, self.num)
            v_map = self.ident_map.get(key, {})
            self.ident_map[key] = v_map

            ident = v_map.get(text)
            if not ident:
                i = self.ident_tracker.get(key, 0)
                ident = idents[i]
                i += 1
                self.ident_tracker[key] = i
                v_map[text] = ident

        return ident

    def _post_process(self, text):
        """
        Take some text and process it - e.g. rationalise out upper
        case letters, final nu, nomina sacra etc.
        """
        # Case
        ret = text.lower()

        # Final nu
        ret = ret.replace(u'¯', u'ν')

        # Nomia sacra
        # FIXME

        return ret
                
    def _parse(self, element, hand=None):
        """
        Go through the element's children and extract the text for
        this verse

        @param hand: the hand to look for in rdg tags (None implies no
        rdg tags will be found)
        
        @returns: the text for this scribe
        """
        contents = []
        for i in element.getchildren():
            tag = i.tag.split('}')[1]
            if tag in ignore_tags:
                continue

            parser = getattr(self, '_parse_%s' % (tag, ), None)
            if not parser:
                print i, i.attrib, i.text
                raise NameError("Don't know how to deal with %s tags"
                                % (tag, ))
                continue

            x = parser(i, hand)
            if x is not None:
                contents.append(x.strip())

        return ' '.join(contents)

    def _parse_w(self, el, hand):
        # Word - just want the text - of this and children, in the
        # right order
        ret = []
        for t in el.itertext():
            ret.append(t.strip())

        # Just check that we've only got known tags...
        for el in el.iter():
            tag = el.tag.split('}')[1]
            if tag not in word_tags:
                print el, el.attrib, el.text
                raise ValueError("Can't cope with %s tags in words"
                                 % (tag, ))

        return ''.join(ret)

    def _parse_app(self, el, hand):
        # This bit has been corrected - there will be more than one
        # version. Look for the specified hand.
        for ch in el.getchildren():
            tag = ch.tag.split('}')[1]
            if tag in ignore_tags:
                continue
            if not ch.tag.endswith("}rdg"):
                print ch, ch.attrib, ch.text
                raise ValueError("I only want rdg tags in an app")
            if self._rdg_hand(ch) == hand:
                # This is the bit we want
                return self._parse(ch, None)


class Chapter(object):
    """
    Takes an ElementTree element representing a chapter and provides
    useful methods for interrogating it.
    """

    verse_class = Verse

    # A mapping of the highest verse num for each chapter
    max_verses = {}

    def __init__(self, element, num):
        self.verses = {}
        self.num = num
        v = None
        for i in element.getchildren():
            if i.tag == "{http://www.tei-c.org/ns/1.0}ab":
                # This is a verse
                v = int(i.attrib['n'])
                if v in self.verses:
                    raise ValueError("Duplicate verse found")
                self.verses[v] = self.verse_class(i, self.num)

        if v and self.max_verses.get(num, 0) < v:
            self.max_verses[num] = v

    def get_stripes(self, space=' '):
        """
        @param space: what character to use for a space?

        Get the stripe(s) for this chapter. Multiple stripes will be
        returned if there are multiple hands.
        @returns: a list of stripe strings.
        """
        all_hands = set()
        for v in self.verses.values():
            [all_hands.add(h) for h in v.hands]
            
        # firsthand == None: tidy up and sort
        if None in all_hands:
            all_hands.remove(None)
        if 'firsthand' in all_hands:
            all_hands.remove('firsthand')
        all_hands = list(all_hands)
        all_hands.sort()
        all_hands = ['firsthand'] + all_hands
            
        ret = Stripe()
        for hand in all_hands:
            stripe = []
            # We need a char for each verse, present or otherwise
            for v in range(1, self.max_verses[self.num] + 1):
                my_v = self.verses.get(v)
                if my_v:
                    stripe.append(my_v.get_ident(hand))
                else:
                    stripe.append(space)
            
            # Rename the only hand to 'firsthand'
            if not hand:
                hand = 'firsthand'

            stripe_text = ''.join(stripe)

            ret.add_hand(hand, stripe_text)

        return ret


class Manuscript(object):
    """
    Fetches a manuscript from www.iohannes.com/XML/?.xml (or uses a
    local copy if present) and parses it.
    """
    chapter_class = Chapter

    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mss")
    
    def __init__(self, name):
        self.name = name
        self.filename = "%s.xml" % (self.name, )
        self.tree = None
        self.chapters = {}

        self._load_xml()
        self._parse_tree()

    def _load_xml(self):
        """
        Check the cache directory exists, look in it and the load from
        the Internet if necessary.
        """
        if not os.path.exists(self.cache):
            os.mkdir(self.cache)
        if not os.path.isdir(self.cache):
            raise IOError("%s isn't a directory"
                          % (self.cache, ))
        cf = os.path.join(self.cache, self.filename)

        if not os.path.exists(cf):
            logger.info("Downloading %s%s" % (base_url, self.filename))
            data = urllib2.urlopen(base_url + self.filename).read()
            with open(cf, 'w') as fh:
                fh.write(data)

        logger.info("Parsing %s" % (self.filename, ))
        self.tree = ET.parse(cf)

    def _parse_tree(self):
        """
        Parse the ElementTree looking for chapters, and put their
        contents into Chapter objects in self.chapters.
        """
        root = self.tree.getroot()
        for child in root.iter("{http://www.tei-c.org/ns/1.0}div"):
            if child.attrib.get('type') == 'chapter':
                my_ch = child.attrib['n']
                logger.debug("Found chapter %s" % (my_ch, ))
                if my_ch in self.chapters:
                    raise ValueError("Duplicate chapter found")
                self.chapters[my_ch] = self.chapter_class(child, my_ch)

        logger.debug("Finished loading %s" % (self.filename, ))
    

class Stripe(object):
    """
    A class representing a stripe
    """
    def __init__(self):
        self.hands = OrderedDict()

    def add_hand(self, name, text):
        self.hands[name] = text

    def __repr__(self):
        ret = []
        for hand in self.hands:
            ret.append("%15s : %s" % (hand, self.hands[hand]))
        return '\n        '.join(ret)

# What tags do we just ignore?
ignore_tags = ['lb',    # Line break
               'cb',    # Column break
               'pb',    # Page break
               'fw',    # Other text, e.g. running titles
               'pc',    # Punctuation
               'space', # White space
               'gap',   # Lacuna, illegible etc.
               ]

# What tags are ok inside words?
word_tags = ['supplied',
             'unclear',
             'abbr',
             'hi',
             'w',
             ] + ignore_tags



if __name__ == "__main__":
    mss = [Manuscript("07"),
           Manuscript("04"),
           ]
    for i in range(1,2):
        print "John %d" % (i, )
        for m in mss:
            ch = m.chapters.get(str(i))
            if ch:
                print "%5s : " % (m.name, ) + repr(ch.get_stripes())

    m = Manuscript("01")
    ch1 = m.chapters.get("1")
    v15 = ch1.verses.get(15)
    print v15.show_all()
    
    
#    for m in mss:
#        print m.name
#        ch = m.chapters.get(str(i))
#        if ch and 1 in ch.verses:
#            ch.verses[1].show_all()
