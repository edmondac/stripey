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

class Snippet(object):
    """
    An object representing a text snippet, either a verse or a sub-part of
    a verse. This will contain the text and associated hand name/type
    for all hands active in this snippet.
    """
    def __init__(self):
        self._readings = []
        self._snippets = []
        self._flat = False

    def add_reading(self, text, hand_name=None, hand_type=None):
        assert self._flat is False, self
        assert not self._snippets, self
        if [x for x in self._readings
            if (x[1], x[2]) == (hand_name, hand_type)]:
            hand_type += ":dup"
            if [x for x in self._readings
                if (x[1], x[2]) == (hand_name, hand_type)]:
                raise ValueError("Need more dupes")
        self._readings.append((text, hand_name, hand_type))

    def add_snippet(self, snippet):
        assert self._flat is False, self
        assert not self._readings, self
        self._snippets.append(snippet)

    def _post_process(self, text):
        """
        Take some text and process it - e.g. rationalise out final nu.
        TODO: should this do anything else? Nomina sacra for example?

        XXX: Is this a good idea at all? It's standard...
        """
        # Final nu
        ret = text.replace(u'¯', u'ν')
        return ret

    def _flatten(self):
        """
        Flatten any snippets into readings.
        """
        if self._flat is True:
            # Already done it
            return

        if not self._snippets:
            # Nothing to do
            return

        assert self._readings == [], self

        bits = []
        all_hands = {}  # We don't care about the values, just the keys here
        for s in self._snippets:
            r = {(h, t):s.get_text(h, t) for (h, t) in s.get_hands()}
            bits.append(r)
            all_hands.update(r)

        for (n, t) in all_hands:
            r = []
            for bit in bits:
                if (n, t) in bit:
                    # Specific reading for this hand exists
                    r.append(bit[(n, t)])
                else:
                    r.append(bit.get((None, None), ''))
            self._readings.append((' '.join([a for a in r if a]), n, t))

        #self._post_process(
        self._flat = True

    def get_hands(self):
        """
        Return a list of (name, type) tuples of hands
        """
        self._flatten()
        return [(x[1], x[2]) for x in self._readings]

    def get_text(self, hand_name=None, hand_type=None):
        """
        Return the text of a particular hand
        """
        self._flatten()
        if not self._readings:
            # Empty snippet - return empty string
            return ""

        wanted = [x[0] for x in self._readings
                  if (x[1], x[2]) == (hand_name, hand_type)]
        assert len(wanted) == 1, self
        return wanted[0]

    def __repr__(self):
        return "<Snippet: {} | {}>".format(self._snippets, self._readings)

    def is_empty(self):
        return True if (self._readings or self._snippets) else False


word_ignore_tags = ['note', 'pc', 'seg']
class Verse(object):  # flake8: noqa
    """
    Takes an ElementTree element representing a verse and parses it.
    """
    def __init__(self, element, number, chapter):
        self.element = element
        self.chapter = chapter
        self.num = number

        # Note - we can have multiple different texts if correctors have been at
        # work.
        self.snippet = self._parse(self.element)

    def get_texts(self):
        """
        Return the texts in a list of (text, hand)
        """
        ret = []
        for n, t in self.snippet.get_hands():
            if n == 'firsthand':
                if t == 'orig':
                    hand = n
                else:
                    hand = "firsthand({})".format(t)
            elif n == t == None:
                hand = "firsthand"
            else:
                hand = n
            assert hand
            ret.append((self.snippet.get_text(n, t), hand))
        return ret

    def _parse(self, element):
        """
        Parse this element, and recursively call myself on its children.

        @returns: a Snippet object
        """
        tag = element.tag.split('}')[1]
        if tag in ignore_tags:
            return Snippet()

        parser = getattr(self, '_parse_%s' % (tag, ), None)
        if parser:
            #print "Using parser:", parser
            my_snippet = parser(element)
        else:
            #print element, element.attrib, element.text
            #print "Don't know how to deal with %s tags - will recurse" % (tag, )
            my_snippet = Snippet()
            for i in element.getchildren():
                my_snippet.add_snippet(self._parse(i))

        #~ if my_snippet.is_empty():
            #~ print "EMPTY", element.attrib, element.getchildren(), element.text

        return my_snippet

    def _word_reader(self, el, top=False):
        """
        This calls itself recursively to extract the text from a word element
        in the right order.

        @param el: the element in question
        @param top: (bool) is this the top <w> tag?

        @returns: a Snippet object or None
        """
        ret = Snippet()
        tag = el.tag.split('}')[1]
        if tag == 'w' and not top:
            # nested word tags without numbers should be ignored
            if el.attrib.get('n'):
                print "WARNING: nested <w> tags at {}:{}".format(self.chapter, self.num)
            return ret

        if tag not in word_ignore_tags:
            if el.text is not None:
                t = el.text.strip().lower()
                s = Snippet()
                if t != 'om':
                    s.add_reading(t)
                else:
                    s.add_reading('')
                ret.add_snippet(s)

            if tag == 'gap':
                # Gap tags matter - put in a space for now
                gap = Snippet()
                gap.add_reading(" ")
                ret.add_snippet(gap)

            for c in el._children:
                ret.add_snippet(self._word_reader(c))

        # We always want the tail, because of the way elementtree puts it on
        # the end of a closing tag, rather than in the containing tag...
        if el.tail is not None:
            s = Snippet()
            s.add_reading(el.tail.strip().lower())
            ret.add_snippet(s)

        #print "Word parser got:", ret
        return ret

    def _parse_w(self, el):
        """
        Parse a <w> tag
        """
        ret = self._word_reader(el, top=True)
        if el.tail and el.tail.strip():
            print "WARNING: Word {} ({}:{}) has a tail".format(el.attrib.get('n'), self.chapter, self.num)

        return ret

    def _parse_app(self, el):
        """
        This bit has been corrected - there will be more than one
        reading.
        """
        ret = Snippet()
        for ch in el.getchildren():
            tag = ch.tag.split('}')[1]
            if tag in ignore_tags:
                continue
            if not ch.tag.endswith("}rdg"):
                print ch, ch.attrib, ch.text
                raise ValueError("I only want rdg tags in an app")

            # Now parse the rdg tag to get its text
            ch_snippet = self._parse(ch)
            ret.add_reading(ch_snippet.get_text(),
                            ch.attrib.get('hand'),
                            ch.attrib.get('type'))
        return ret


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
