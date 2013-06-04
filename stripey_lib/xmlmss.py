# -*- coding: utf-8 -*-
"""
Loads, parses and classifies the text from manuscripts.
Notes:
* The first ms you load becomes your base text.
* I'm not currently doing anything with the book's title, e.g. κατα ιωαννην
* I'm not handling gap tags very smartly
"""

import os
import hashlib
import urllib2
import string
import logging
logger = logging.getLogger('XmlMss')
import xml.etree.ElementTree as ET
from collections import OrderedDict

idents = string.lowercase

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


class Verse(object):
    """
    Takes an ElementTree element representing a verse and parses it.
    """
    def __init__(self, element, chapter):
        self.element = element
        self.chapter = chapter

        # This is the verse tag - extract the verse number
        self.num = self.element.attrib['n']

        # Note - we can have multiple different texts and idents if
        # correctors have been at work
        self.hands = []
        self.texts = []

        self._find_hands()
        if not self.hands:
            # Only one scribe at work here
            self.hands = [None]

        for hand in self.hands:
            text = self._parse(self.element, hand)
            text = self._post_process(text)
            self.texts.append(text)

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
                self.verses[v] = Verse(i, self.num)


class Manuscript(object):
    """
    Fetches a manuscript from www.iohannes.com/XML/?.xml (or uses a
    local copy if present) and parses it.
    """
    cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".mss")
    
    def __init__(self, name, url):
        self.name = name
        self.url = url
        self.tree = None
        self.chapters = {}
        self.book = None

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
                          
        cache_key = hashlib.sha224(self.url).hexdigest()
        cf = os.path.join(self.cache, cache_key)

        if not os.path.exists(cf):
            logger.info("Downloading {}".format(self.url))
            try:
                data = urllib2.urlopen(self.url).read()
                with open(cf, 'w') as fh:
                    fh.write(data)
            except Exception as e:
                raise IOError("Error downloading XML file: {}".format(str(e)))

        logger.info("Parsing {}".format(self.url))
        self.tree = ET.parse(cf)

    def _parse_tree(self):
        """
        Parse the ElementTree looking for chapters, and put their
        contents into Chapter objects in self.chapters.
        """
        root = self.tree.getroot()
        for title in root.iter('{http://www.tei-c.org/ns/1.0}title'):
            if title.attrib.get('type') == 'short':
                # This is the book name
                self.book = title.text
                logger.info("Detected book: {}".format(self.book))
                break
        
        for child in root.iter("{http://www.tei-c.org/ns/1.0}div"):
            if child.attrib.get('type') == 'chapter':
                my_ch = child.attrib['n']
                logger.debug("Found chapter %s" % (my_ch, ))
                if my_ch in self.chapters:
                    raise ValueError("Duplicate chapter found")
                self.chapters[my_ch] = Chapter(child, my_ch)

        logger.debug("Finished parsing %s" % (self.name, ))
    

