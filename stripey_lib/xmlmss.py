# -*- coding: utf-8 -*-
"""
Loads, parses and classifies the text from manuscripts.
Notes:
* The first ms you load becomes your base text.
* I'm not currently doing anything with the book's title, e.g. κατα ιωαννην
* I'm not handling gap tags very smartly
"""

import logging
logger = logging.getLogger('XmlMss')
import xml.etree.ElementTree as ET

# What tags do we just ignore?
ignore_tags = ['lb',     # Line break
               'cb',     # Column break
               'pb',     # Page break
               'fw',     # Other text, e.g. running titles
               'pc',     # Punctuation
               'space',  # White space
               'gap',    # Lacuna, illegible etc.
               'seg',    # Marginal text
               'note',   # Notes
               'num',    # (Mostly) paratextual numbners
               'unclear',  # TODO - should these be ignored?
               'supplied',  # for supplied tags outside words...
               ]

#~ # What tags are ok inside words?
#~ word_tags = ['supplied',
             #~ 'unclear',
             #~ 'abbr',
             #~ 'hi',
             #~ 'w',
             #~ 'ex',
             #~ 'lb',
             #~ ]

word_ignore_tags = ['note', 'pc']


class Verse(object):
    """
    Takes an ElementTree element representing a verse and parses it.
    """
    def __init__(self, element, number, chapter):
        self.element = element
        self.chapter = chapter
        self.num = number

        # Note - we can have multiple different texts if
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
        Take some text and process it - e.g. rationalise out final nu.
        TODO: should this do anything else? Nomina sacra for example?
        """
        # Final nu
        ret = text.replace(u'¯', u'ν')
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

    def _word_reader(self, el, top=False):
        """
        This calls itself recursively to extract the text from a word element
        in the right order.

        @param el: the element in question
        @param top: (bool) is this the top <w> tag?
        """
        ret = u''
        tag = el.tag.split('}')[1]
        if tag == 'w' and not top:
            print "WARNING: nested <w> tags at {}:{}".format(self.chapter, self.num)
        if tag in word_ignore_tags:
            print "Ignoring tag {}".format(tag)
        else:
            if el.text is not None:
                ret = el.text.strip().lower()
                if ret == 'om':
                    ret = u''

            for c in el._children:
                ret += self._word_reader(c)

        # We always want the tail, because of the way elementtree puts it on
        # the end of a closing tag, rather than in the containing tag...
        if el.tail is not None:
            ret += el.tail.strip().lower()

        return ret
#~
            #~ ret2 = []
        #~ # Just check that we've only got known tags...
        #~ for l in el.iter():
            #~ tag = l.tag.split('}')[1]
            #~ print tag, l.text, l.tail
            #~ bit = u''
            #~ if tag in word_tags and l.text:
                #~ # Only want text from specific tags
                #~ bit = l.text.strip().lower()
                #~ if bit == 'om':
                    #~ bit = u''
            #~ if l.tail:
                #~ # The tail can be set on a subelement, when it should be on the
                #~ # word tag. So we need it whatever... (elementtree at fault)
                #~ bit += l.tail.strip().lower()
            #~ if bit:
                #~ ret2.append(bit)
#~
            #~ #if tag not in word_tags:
            #~ #    print l, l.attrib, l.text, l.tail
            #~ #    raise ValueError("Can't cope with %s tags in words"
            #~ #                     % (tag, ))
        #~ if el.tail:
            #~ print "TAIL2", el.tail
            #~ ret2.append(el.tail.strip())
        #~ ret2_s = u''.join([a for a in ret2 if a])

    def _parse_w(self, el, hand):
        # Word - just want the text - of this and children, in the
        # right order
        ret = []
        for t in el.itertext():
            t = t.strip().lower()
            if t in ('om', 'omm'):
                # Ignore 'om' and leave it blank
                continue
            ret.append(t)

        ret2_s = self._word_reader(el, top=True)
        if el.tail and el.tail.strip():
            print "WARNING: Word {} ({}:{}) has a tail".format(el.attrib.get('n'), self.chapter, self.num)

        ret_s = u''.join([a for a in ret if a])

        for c in (u'umlaut', u'>', u'†'):
            ret_s = ret_s.replace(c, u'')
        import re
        re_ms306 = re.compile('current folio [0-9]+[a-z][a-z]?\.')

        ret_s = re_ms306.sub(u'', ret_s)

        if ret_s != ret2_s:
            if ret_s not in (u'αυdefect in parchmentτον',
                             u'εμα↓ (jn 19,1-7)στιγωσε',
                             u'εφαγεcommcommται',
                             u'κα',
                             u'εgathering pϊωαννηνχων',
                             u'οcurrent folio 117av.τι',
                             u'καιροςρος',
                             u'first fragment (jn 15:25-16:2)των',
                             u'εγενε‾‾το',
                             u'ουst. petersburgχ',
                             u'επισfourth page, ↓ (jn 11:45-52)ρθτευσαν',
                             u'αcurrent folio 117r.νος',
                             u'αυcurrent folio 118v.του',
                             u'εγεννηcurrent folio 117ar.θης',
                             u'αναβαιcurrent folio 115ar.νων'):
                print "REF", self.chapter, self.num
                print el.attrib, el.text, el.__dict__, dir(el), el._children
                print u"'{}'\n'{}'".format(ret_s, ret2_s)
                raise ValueError

        return ret2_s

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
        self.parse_element(element)

    def parse_element(self, element):
        """
        Parse the XML element and children to get the verses.
        This function can be called multiple times, for example in
        commentary mss where a chapter turns up more than once.
        """
        for i in element.getchildren():
            if i.tag == "{http://www.tei-c.org/ns/1.0}ab":
                # This is a verse
                v = i.attrib['n']
                if v.startswith('B'):
                    # e.g. B04K12V17
                    v = v.split('V')[-1]
                v = int(v)
                v_obj = Verse(i, v, self.num)
                already = self.verses.get(v, [])
                already.append(v_obj)
                self.verses[v] = already


class Manuscript(object):
    """
    Fetches a manuscript from a file and parses it.
    """
    def __init__(self, name, filepath):
        self.name = name
        self.filepath = filepath
        self.tree = None
        self.chapters = {}
        self.ms_desc = {}

        # Book identification - FIXME, am I limited to one book per ms?
        self.book = None
        self.num = None

        self._load_xml()
        self._parse_tree()

    def _load_xml(self):
        """
        Load the file from disk.
        """
        logger.info("Parsing {}".format(self.filepath))
        self.tree = ET.parse(self.filepath)

    def _parse_tree(self):
        """
        Parse the ElementTree looking for chapters, and put their
        contents into Chapter objects in self.chapters.
        """
        root = self.tree.getroot()
        # MS information
        for n in root.iter('{http://www.tei-c.org/ns/1.0}msName'):
            self.ms_desc['ms_name'] = n.text
            break
        for alt in root.iter('{http://www.tei-c.org/ns/1.0}altIdentifier'):
            self.ms_desc[alt.attrib['type']] = alt.find('{http://www.tei-c.org/ns/1.0}idno').text

        # Book information
        for title in root.iter('{http://www.tei-c.org/ns/1.0}title'):
            if title.attrib.get('type') == 'short':
                # This is the book name
                self.book = title.text
                logger.info("Detected book: {}".format(self.book))
            elif title.attrib.get('type') == 'work':
                # This is the book number
                self.num = title.attrib.get('n')

        for child in root.iter("{http://www.tei-c.org/ns/1.0}div"):
            if child.attrib.get('type') == 'chapter':
                my_ch = child.attrib['n']
                if my_ch.startswith('B'):
                    # e.g. B04K12
                    my_ch = my_ch.split('K')[-1]
                logger.debug("Found chapter %s" % (my_ch, ))
                if my_ch in self.chapters:
                    logger.debug("Duplicate chapter - adding verses")
                    self.chapters[my_ch].parse_element(child)
                else:
                    self.chapters[my_ch] = Chapter(child, my_ch)

        logger.debug("Finished parsing %s" % (self.name, ))
