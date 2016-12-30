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
    def __init__(self, word_sep=True):
        self._readings = {}  # {('hand_name', 'hand_type'): text, ...}
        self._snippets = []
        self._word_sep = word_sep

    def add_reading(self, text, hand_name='firsthand', hand_type='orig'):
        #print u"Adding reading {} for {}.{}".format(text, hand_name, hand_type)
        assert not self._snippets, self
        if hand_name is None:
            if hand_type == 'orig':
                print "WARNING: Assuming hand None:orig is firsthand"
                hand_name = 'firsthand'
            elif hand_type == 'corr':
                print "WARNING: Assuming hand None:corr is corrector"
                hand_name = 'corrector'

        assert hand_name, (text, hand_name, hand_type)
        assert hand_type, (text, hand_name, hand_type)

        key = (hand_name, hand_type)
        if key in self._readings:
            # Duplicate hand discovered - recurse
            return self.add_reading(text, hand_name, "{}:dup".format(hand_type))

        self._readings[key] = text

    def add_snippet(self, snippet):
        assert not self._readings, self
        self._snippets.append(snippet)

    def _post_process(self, text):
        """
        Take some text and process it - e.g. rationalise out final nu.

        Get rid of any double spaces.

        TODO: should this do anything else? Nomina sacra for example?

        XXX: Is this a good idea at all? It's standard...
        """
        # Final nu
        text = text.replace(u'¯', u'ν')
        while '  ' in text:
            #~ print "Stripping double space"
            text = text.replace('  ', ' ')

        return text

    #~ def flatten(self):
        #~ """
        #~ Flatten any snippets into readings.
        #~ """
        #~ if self._flat is True:
            #~ # Already done it
            #~ return
#~
        #~ if not self._snippets:
            #~ # Nothing to do
            #~ return
#~
        #~ assert self._readings == [], self
#~
        #~ bits = []
        #~ all_hands = self.get_hands()
        #~ for s in self._snippets:
            #~ # First flatten the sub-snippet (and so on, recursively)
            #~ s.flatten()
            #~ r = {(h, t):s.get_text(h, t) for (h, t) in s.get_hands()}
            #~ bits.append(r)
            #~ all_hands.add(r)
#~
        #~ for (n, t) in all_hands:
            #~ r = []
            #~ for bit in bits:
                #~ print bit
                #~ if (n, t) in bit:
                    #~ # Specific reading for this hand exists
                    #~ r.append(bit[(n, t)])
                #~ else:
                    #~ r.append(bit.get((None, None), ''))
            #~ self._readings.append((''.join([a for a in r if a]), n, t))
#~
        #~ #self._post_process(
        #~ self._flat = True

    def get_hands(self):
        """
        Return a list of (name, type) tuples of all hands found recursively
        """
        all_hands = set()
        for s in self._snippets:
            all_hands.update(s.get_hands())
        for (hand_name, hand_type) in self._readings.keys():
            all_hands.add((hand_name, hand_type))
        return all_hands

    #~ def has_hand(self, hand_name, hand_type):
        #~ """
        #~ Does this snippet contain a reading in the specified hand?
        #~ """
        #~ return (hand_name, hand_type) in self.get_hands()

    def get_text(self, hand_name='firsthand', hand_type='orig', order_of_hands=['firsthand']):
        """
        Return the text of a particular hand. If the hand isn't present in this
        place, then we search backwards from that hand in order_of_hands to find
        a hand that is present, and return that text.
        """
        assert hand_name in order_of_hands, (hand_name, hand_type, order_of_hands)
        #~ print "Get text: {}, {}, {}".format(hand_name, hand_type, order_of_hands)

        if self._snippets:
            # Find our text recursively
            ret = []
            for s in self._snippets:
                ret.append(s.get_text(hand_name, hand_type, order_of_hands))
            return self._post_process(''.join(ret))

        elif not self._readings:
            # Empty snippet - return empty string
            return ""

        else:
            # Return the required reading's text
            key = (hand_name, hand_type)
            if key in self._readings:
                # This hand exists here
                ret = self._readings[key]
            else:
                #~ print "Looking for earlier readings than {}:{}".format(hand_name, hand_type)
                # Special case for firsthand corrections...
                if hand_name == 'firsthand':
                    if hand_type == 'alt':
                        return self.get_text(hand_name, 'corr', order_of_hands)
                    elif hand_type == 'corr':
                        return self.get_text(hand_name, 'orig', order_of_hands)

                hand_idx = order_of_hands.index(hand_name)
                # Find hand names that exist here... Note, order_of_hands doesn't
                # have the hand_type, so we can't use that right now...
                present_hands_keys = self._readings.keys()
                present_hands = [x[0] for x in present_hands_keys]
                hands_to_try = list(reversed(order_of_hands[:hand_idx]))
                if not hands_to_try:
                    hands_to_try = ['firsthand']
                for hand in hands_to_try:
                    if hand in present_hands:
                        if hand == 'firsthand':
                            # look for firsthand_corr first...
                            key = ('firsthand', 'corr')
                            if key not in present_hands_keys:
                                key = ('firsthand', 'orig')
                        else:
                            key = present_hands_keys[present_hands.index(hand)]

                        ret = self._readings[key]
                        break
                else:
                    import pdb
                    pdb.set_trace()
                    print "NO BREAK"

            # Run any required post processing on the text
            ret = self._post_process(ret)

            if self._word_sep is True:
                # If this is a new word, then add a space
                ret = u" " + ret

            # Trim out double spaces
            #~ while '  ' in ret:
                #~ ret = ret.replace('  ', ' ')
            #print u"Returning reading for {}:{}: {}".format(hand_name, hand_type, ret)
            return ret

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
        hands = self.snippet.get_hands()
        for n, t in hands:
            if n == 'firsthand':
                if t == 'orig':
                    hand = n
                else:
                    hand = "firsthand({})".format(t)
            else:
                hand = n
            assert hand
            reading = self.snippet.get_text(n, t, self.chapter.manuscript.order_of_hands).strip()
            if reading:
                ret.append((reading, hand))

        #~ if len(ret) > 1:
            #~ #print self.snippet
            #~ for t, h in ret:
                #~ print u"{}: {}".format(h, t)
            #~ raise ValueError
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
        in the right order. We don't want any spaces in here, so we will
        pass word_sep=False into snippets.

        @param el: the element in question
        @param top: (bool) is this the top <w> tag?

        @returns: a Snippet object or None
        """
        ret = Snippet(word_sep=top)
        tag = el.tag.split('}')[1]
        if tag == 'w' and not top:
            # nested word tags without numbers should be ignored
            if el.attrib.get('n'):
                logger.warning("Nested <w> tags at {}:{}".format(
                    self.chapter.num, self.num))
            return ret

        if tag not in word_ignore_tags:
            if el.text is not None:
                t = el.text.strip().lower()
                s = Snippet(word_sep=False)
                if t == 'om':
                    s.add_reading('')
                else:
                    s.add_reading(t)
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
            s = Snippet(word_sep=False)
            s.add_reading(el.tail.strip().lower())
            ret.add_snippet(s)

        if top is True:
            # Add a space after every word
            space = Snippet()
            space.add_reading(" ")
            ret.add_snippet(space)

        #print "Word parser got:", ret
        return ret

    def _parse_w(self, el):
        """
        Parse a <w> tag
        """
        ret = self._word_reader(el, top=True)
        if el.tail and el.tail.strip():
            print "WARNING: Word {} ({}:{}) has a tail".format(el.attrib.get('n'), self.chapter.num, self.num)

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
            hand = ch.attrib.get('hand')
            if hand == '*':
                # Occasionally firsthand is named '*' in the XML
                hand = 'firsthand'
            typ = ch.attrib.get('type')
            text = ch_snippet.get_text(order_of_hands = self.chapter.manuscript.order_of_hands)
            if text == "" and hand == typ == None:
                print "WARNING: Empty rdg tag"
            else:
                #print u"Adding reading {} for {}:{}".format(text, hand, typ)
                ret.add_reading(text, hand, typ)

        return ret


class Chapter(object):
    """
    Takes an ElementTree element representing a chapter and provides
    useful methods for interrogating it.
    """

    def __init__(self, element, num, manuscript):
        self.verses = {}
        self.num = num
        self.manuscript = manuscript
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
                if 'n' not in i.attrib:
                    import pdb; pdb.set_trace()
                v = i.attrib['n']
                if v.startswith('B'):
                    # e.g. B04K12V17
                    v = v.split('V')[-1]
                v = int(v)
                v_obj = Verse(i, v, self)
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
        self.order_of_hands = []

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

        # Correctors information
        for listwit in root.iter('{http://www.tei-c.org/ns/1.0}listWit'):
            for witness in listwit.findall('{http://www.tei-c.org/ns/1.0}witness'):
                self.order_of_hands.append(witness.attrib['{http://www.w3.org/XML/1998/namespace}id'])

        if self.order_of_hands == []:
            self.order_of_hands = ['firsthand']
        print "{} hands defined: {}".format(len(self.order_of_hands), ', '.join(self.order_of_hands))

        # Text
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
                    self.chapters[my_ch] = Chapter(child, my_ch, self)

        logger.debug("Finished parsing %s" % (self.name, ))

if __name__ == "__main__":
    import sys
    m = Manuscript("Test", sys.argv[1])
    print m.book, m.num
    for ch in m.chapters.values():
        for vl in ch.verses.values():
            for vs in vl:
                print "> {}:{}".format(ch.num, vs.num)
                for t, h in vs.get_texts():
                    print h + '\t' + t
