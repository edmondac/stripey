# coding=UTF-8

from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from stripey_lib import xmlmss
from django.db.models import Max
from memoize import memoize

import Levenshtein
import unicodedata
import logging
logger = logging.getLogger('stripey_app.models')


# Show/hide accents (dynamic on ms text but collation is fixed in time)
# can be: 'none', 'all'
SHOW_ACCENTS = 'none'
# If hiding accents, then also hide these characters:
IGNORE_CHARS = u"'†"


def strip_accents(inp):
    """
    Return a normalized version of the inp unicode string with accented
    characters converted to their normal equivalent, and other non-alphabet
    characters removed (e.g. ')
    """
    out = u''.join([c for c in unicodedata.normalize('NFD', inp)
                    if (not unicodedata.combining(c) and
                        c not in IGNORE_CHARS)])
    #~ if inp != out:
        #~ logger.debug(u"Normalised greek input:\ninp: \t{}\nout: \t{}".format(inp, out))
    return out


# Quick test for strip_accents...
test_in = u"οϋκ ην εκεινος το φως αλλ' ϊνα μαρτυρηση περι του φωτος"
test_out = u"ουκ ην εκεινος το φως αλλ ινα μαρτυρηση περι του φωτος"
assert strip_accents(test_in) == test_out, u"ERROR: \n{}\n{}".format(test_in, test_out)


class ManuscriptTranscription(models.Model):
    ms_ref = models.CharField(max_length=10, unique=True)
    xml_filename = models.CharField(max_length=200)
    status = models.CharField(max_length=20,
                              blank=True)
    ms_name = models.CharField(max_length=50, blank=True)
    tischendorf = models.CharField(max_length=5, blank=True)
    ga = models.CharField(max_length=10, blank=True)
    liste_id = models.IntegerField(blank=True)

    def load(self):
        """
        Load the XML, parse it, and create mschapter, chapter,
        verse, msverse and hand objects.
        """
        if self.status == 'loaded':
            logger.debug("MS {} is already loaded - ignoring".format(self))
            return

        logger.info("Loading MS {}".format(self))
        obj = xmlmss.Manuscript(self.ms_ref, self.xml_filename)
        if not obj.book:
            raise ValueError("Couldn't work out the book")

        # Metadata
        self.ms_name = obj.ms_desc.get('ms_name', '')
        self.tischendorf = obj.ms_desc.get('Tischendorf', '')
        self.ga = obj.ms_desc.get('GA', '')
        liste_id = obj.ms_desc.get('Liste', '')
        if liste_id in ('3NA27', '300TR'):
            # Special case "manuscripts"
            self.liste_id = -1
            if not self.ms_name:
                self.ms_name = self.ga
        else:
            self.liste_id = int(liste_id)

        # Save myself so that other objects can reference me
        self.save()
        logger.debug(u"Found info: {}, {}, {}, {}".format(self.ms_name,
                                                          self.tischendorf,
                                                          self.ga,
                                                          self.liste_id))

        db_book = _get_book(obj.book, obj.num)

        for ch in obj.chapters.values():
            db_chapter = _get_chapter(db_book, ch.num)

            # First create the MsChapter
            ms_chapter = MsChapter()
            ms_chapter.chapter = db_chapter
            ms_chapter.manuscript = self
            ms_chapter.save()

            # Now get the verses
            for verse_list in ch.verses.values():
                for j, vs in enumerate(verse_list):
                    db_verse = _get_verse(db_chapter, vs.num)
                    for text, hand in vs.get_texts():
                        db_hand = _get_hand(self, hand)
                        ms_verse = MsVerse()
                        ms_verse.verse = db_verse
                        ms_verse.hand = db_hand
                        ms_verse.item = j
                        ms_verse.raw_text = text
                        ms_verse.save()

        self.status = 'loaded'
        self.save()

    def __unicode__(self):
        return "Manuscript {}".format(self.ga)

    def display_ref(self):
        """
        A combination of the various ids to give a helpful reference.
        """
        ref = []
        if self.ms_name:
            ref.append(self.ms_name)

        if self.tischendorf:
            ref.append(self.tischendorf)

        if self.ga:
            ref.append(u"GA:{}".format(self.ga))

        if not ref:
            ref = [self.ms_ref]

        return u", ".join(ref)

    def display_short(self):
        """
        A short ref to display
        """
        if self.tischendorf:
            return self.tischendorf

        if self.ga:
            return self.ga

        return self.ms_ref

    def get_text(self, book_obj, chapter_obj, verse_num=None):
        """
        Return the text of the relevant book, chapter (db objects)
        in a list of tuples  [(1,[verse obj, verse obj, ...]),
                              (2,[verse obj]),
                              ...]

        @param book_obj: a book object
        @param chapter_obj: a chapter object
        @verse_num: (optional) restrict to a single verse with this number

        Multiple verse_objs are possible where there are multiple hands
        at work and in commentary manuscripts that mention the verse
        more than once.
        """
        v_d = {}
        for hand in Hand.objects.filter(manuscript=self):
            if verse_num is None:
                verses = MsVerse.objects.filter(verse__chapter=chapter_obj,
                                                hand=hand,
                                                ).order_by('verse__num')
            else:
                verses = MsVerse.objects.filter(verse__chapter=chapter_obj,
                                                hand=hand,
                                                verse__num=verse_num)
            for verse in verses:
                me = v_d.get(verse.verse.num)
                if not me:
                    me = []
                    v_d[verse.verse.num] = me
                me.append(verse)

        ret = []
        keys = v_d.keys()
        keys.sort()
        for v in keys:
            ret.append((v, v_d[v]))

        return ret


class Hand(models.Model):
    manuscript = models.ForeignKey(ManuscriptTranscription)
    name = models.CharField(max_length=30)

    def __unicode__(self):
        return u"Hand {} of {}".format(self.name, self.manuscript)


class Book(models.Model):
    name = models.CharField(max_length=20)
    num = models.IntegerField()


class Chapter(models.Model):
    book = models.ForeignKey(Book)
    num = models.IntegerField()


class MsChapter(models.Model):
    chapter = models.ForeignKey(Chapter)
    manuscript = models.ForeignKey(ManuscriptTranscription)


class Verse(models.Model):
    chapter = models.ForeignKey(Chapter)
    num = models.IntegerField()

    def __unicode__(self):
        return "Verse {} {}:{}".format(self.chapter.book.name,
                                       self.chapter.num,
                                       self.num)


class MsVerse(models.Model):
    verse = models.ForeignKey(Verse)
    hand = models.ForeignKey(Hand)
    item = models.IntegerField()  # for "duplicate" verses
    raw_text = models.CharField(max_length=1000)

    @property
    def text(self):
        """
        Convert the raw text into whatever stripped form we want
        """
        if SHOW_ACCENTS == 'none':
            # Strip out anything that isn't a normal character
            return strip_accents(self.raw_text)
        else:
            return self.raw_text

    def __unicode__(self):
        return "MsVerse: ms:{}, hand:{}, verse:{} ({})".format(
            self.hand.manuscript.id,
            self.hand.name,
            self.verse,
            self.item)


class Algorithm(models.Model):
    """
    A collation algorithm
    """
    name = models.CharField(max_length=30)

    def __unicode__(self):
        return "Algorithm: {}".format(self.name)


class Variant(models.Model):
    verse = models.ForeignKey(Verse)
    variant_num = models.IntegerField()
    algorithm = models.ForeignKey(Algorithm)
    unique_together = (verse, variant_num, algorithm)


class Reading(models.Model):
    variant = models.ForeignKey(Variant)
    text = models.CharField(max_length=1000)
    label = models.IntegerField()
    unique_together = (variant, text, label)

    def save(self):
        """
        Save the object - setting a label if there's isn't one already
        """
        if not self.label:
            if not self.text:
                self.label = 0
            else:
                max_label = Reading.objects.filter(variant=self.variant).aggregate(Max('label'))['label__max'] or 0
                self.label = max_label + 1

        super(Reading, self).save()

    def __unicode__(self):
        return u"Reading: {}:{}:{}".format(
            self.variant.verse,
            self.variant.variant_num,
            self.text)


class Stripe(models.Model):
    """
    A Stripe is a generic mapping of verse to reading. A stripe
    """
    verse = models.ForeignKey(Verse)
    readings = models.ManyToManyField(Reading)
    algorithm = models.ForeignKey(Algorithm)

    def save(self, *args):
        """
        Consistency check on algorithms. We expect the caller to deal with
        the exception.
        """
        ret = super(Stripe, self).save(*args)
        for reading in self.readings.all():
            if reading.variant.algorithm.id != self.algorithm.id:
                raise ValueError(u"Algorithm mismatch {} vs {}".format(self.algorithm,
                                                                       reading.algorithm))
        return ret


class MsStripe(models.Model):
    """
    An MsStripe is a many-to-many mapping of hands to stripes.
    """
    stripe = models.ForeignKey(Stripe)
    ms_verse = models.ForeignKey(MsVerse)

    def __unicode__(self):
        return u"MsStripe: ms_verse {}, stripe {}".format(self.ms_verse,
                                                          self.stripe)


def _get_book(name, num):
    """
    Retrieve or create the specified book
    """
    try:
        db_book = Book.objects.get(name=name)
    except ObjectDoesNotExist:
        logger.debug("Creating book object for {}".format(name))
        db_book = Book()
        db_book.name = name
        db_book.num = num
        db_book.save()
    return db_book


def _get_chapter(db_book, num):
    """
    Retrieve or create the specified chapter
    """
    try:
        db_chapter = Chapter.objects.get(book=db_book, num=num)
    except ObjectDoesNotExist:
        logger.debug("Creating chapter object for {}:{}".format(db_book.name, num))
        db_chapter = Chapter()
        db_chapter.num = num
        db_chapter.book = db_book
        db_chapter.save()
    return db_chapter


def _get_verse(db_chapter, num):
    """
    Retrieve or create the specified verse
    """
    try:
        db_verse = Verse.objects.get(chapter=db_chapter, num=num)
    except ObjectDoesNotExist:
        logger.debug("Creating verse object for {}:{}".format(db_chapter.num, num))
        db_verse = Verse()
        db_verse.num = num
        db_verse.chapter = db_chapter
        db_verse.save()
    return db_verse


def _get_hand(ms, hand):
    """
    Retrieve or create the specified hand
    """
    if hand is None:
        hand = 'firsthand'
    try:
        db_hand = Hand.objects.get(manuscript=ms, name=hand)
    except ObjectDoesNotExist:
        logger.debug("Creating hand object for {}:{}".format(ms.ms_ref, hand))
        db_hand = Hand()
        db_hand.name = hand
        db_hand.manuscript = ms
        db_hand.save()
    return db_hand


@memoize
def get_all_verses(book_obj, chapter_obj, base_ms_id=None, verse_num=None):
    """
    Return all verses in a particular chapter, in this form:

    @param book_obj: a book object
    @param chapter_obj: a chapter object
    @param base_ms_id: (optional) the db id of a manuscript
    @param verse_num: (optional) return only a single verse with this number

    [(1,
      [(<ManuscriptTranscription: Manuscript 04_1424 transcription (loaded)>,
       [<MsVerse: MsVerse: ms:46, hand:firsthand, chapter:Chapter object, v:1-0>]),
      (<ManuscriptTranscription: Manuscript 04_579 transcription (loaded)>,
       [<MsVerse: MsVerse: ms:47, hand:firsthand, chapter:Chapter object, v:1-0>,
        <MsVerse: MsVerse: ms:47, hand:corrector, chapter:Chapter object, v:1-0>]),
      (<ManuscriptTranscription: Manuscript 04_03 transcription (loaded)>,
       [<MsVerse: MsVerse: ms:50, hand:firsthand, chapter:Chapter object, v:1-0>]),
      ...]),
     (2,
      [...]]
    """
    all_mss = ManuscriptTranscription.objects.all()
    base_ms = None
    if base_ms_id:
        base_ms = ManuscriptTranscription.objects.get(id=base_ms_id)
    else:
        # We still need one - so pick the first we get...
        base_ms = ManuscriptTranscription.objects.all()[0]

    base_texts = base_ms.get_text(book_obj, chapter_obj)
    sorters = {x[0]: TextSorter([i.text for i in x[1] if i.hand.name == 'firsthand'][0]) for x in base_texts}

    vs_d = {}
    for ms in all_mss:
        # If verse_num == None, then this will get everything in the chapter
        verses = ms.get_text(book_obj, chapter_obj, verse_num)
        #  [(1,[verse obj, verse obj, ...]),
        #   (2,[verse obj]),
        #   ...]
        for v in verses:
            for ms_verse in v[1]:
                if base_ms is not None:
                    my_sorter = sorters.get(v[0])
                    if my_sorter:
                        ms_verse.similarity = my_sorter(ms_verse.text)
                    else:
                        # The base text doesn't exist in this verse
                        ms_verse.similarity = ''
            me = vs_d.get(v[0])
            if not me:
                me = []
                vs_d[v[0]] = me
            me.append((ms, v[1]))

    keys = vs_d.keys()
    keys.sort()
    all_verses = []
    for k in keys:
        all_verses.append((k, vs_d[k]))

    return all_verses


class TextSorter(object):
    """
    An object for returning the Levenshtein distance between our base text
    and any other text.
    """
    def __init__(self, base_text):
        self.base_text = base_text

    def __call__(self, text):
        lev = Levenshtein.ratio(self.base_text, text) * 100.0
        #~ if lev != 100.0:
            #~ logger.warning(u"|{}|{}|{}".format(self.base_text, text, lev))
        return lev


class StripeSorter(TextSorter):
    """
    An object for returning the Levenshtein distance between our base text
    and any other stripe.
    """
    def __init__(self, base_ms_id, stripe_data):
        # If the verse doesn't exist in our base text, then just set it to blank
        self.base_text = u""
        for (stripe, ms_stripes) in stripe_data:
            my_ms_stripe = [x for x in ms_stripes if
                            (x.ms_verse.hand.manuscript.id == base_ms_id and
                             x.ms_verse.hand.name == 'firsthand')]
            if my_ms_stripe:
                # This ms_stripe is our base text's firsthand
                self.base_text = self._textify(my_ms_stripe[0].stripe.readings.all())

    def _textify(self, readings):
        return ' '.join([x.text for x in readings if x.text.strip()])

    def __call__(self, stripe):
        text = self._textify(stripe.readings.all())
        return super(StripeSorter, self).__call__(text)


@memoize
def collate(chapter_obj, verse_obj, algorithm_obj, base_ms_id):
    """
    @param verse_obj: This is optional - if set to None this function
    will return all verses in the chaper.

    Collect data verse by verse - like this:
    [(<Verse: Verse john 1:1>,
        [(<Stripe: Stripe: verse Verse john 1:1, readings...>,
          [<MsStripe: MsStripe: hand Hand firsthand of Manuscript 013...>, ...]),
         (<Stripe: Stripe: verse Verse john 1:1, readings...>,
          [<MsStripe: MsStripe: hand Hand firsthand of Manuscript 013...>, ...])
        ]),
     (<Verse: Verse john 1:2>...
    """
    collation = []
    if verse_obj:
        verses = [verse_obj]
    else:
        verses = Verse.objects.filter(chapter=chapter_obj).order_by('num')

    for verse in verses:
        stripes = Stripe.objects.filter(verse=verse, algorithm=algorithm_obj)
        my_data = []
        for st in stripes:
            ms_stripes = sorted(MsStripe.objects.filter(stripe=st),
                                key=lambda a: a.ms_verse.hand.manuscript.liste_id)
            my_data.append((st, ms_stripes))

        # Now sort it by similarity to our base ms's reading - and add the
        # similarity to the object
        sorter = StripeSorter(base_ms_id, my_data)
        for st, ms_stripes in my_data:
            st.similarity = sorter(st)

        sorted_data = sorted(my_data, key=lambda a: a[0].similarity, reverse=True)
        collation.append((verse, sorted_data))

    return collation
