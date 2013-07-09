# coding=UTF-8

from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from stripey_lib import xmlmss
from collections import OrderedDict
from django.db.models import Max
import string
import logging
logger = logging.getLogger('stripey_app.models')


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
        Load the XML, parse it, and create chapter, verse and hand objects.
        """
        if self.status == 'loaded':
            logger.debug("MS {} is already loaded - ignoring".format(self))
            return

        logger.info("Loading MS {}".format(self))
        obj = xmlmss.Manuscript(self.ms_ref, self.xml_filename)
        if not obj.book:
            raise ValueError("Couldn't work out the book")

        self.ms_name = obj.ms_desc.get('ms_name', '')
        self.tischendorf = obj.ms_desc.get('Tischendorf', '')
        self.ga = obj.ms_desc.get('GA', '')
        self.liste_id = obj.ms_desc.get('Liste', '')
        self.save()
        logger.debug(u"Found info: {}, {}, {}, {}".format(self.ms_name,
                                                          self.tischendorf,
                                                          self.ga,
                                                          self.liste_id))

        db_book = _get_book(obj.book, obj.num)

        for ch in obj.chapters.values():
            db_chapter = _get_chapter(db_book, ch.num)

            for verse_list in ch.verses.values():
                for j, vs in enumerate(verse_list):
                    db_verse = _get_verse(db_chapter, vs.num)
                    for i, hand in enumerate(vs.hands):
                        db_hand = _get_hand(self, hand)
                        ms_verse = MsVerse()
                        ms_verse.verse = db_verse
                        ms_verse.hand = db_hand
                        ms_verse.item = j
                        ms_verse.text = vs.texts[i]
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

    def get_text(self, book_obj, chapter_obj):
        """
        Return the text of the relevant book, chapter (db objects)
        in a list of tuples  [(1,[verse obj, verse obj, ...]),
                              (2,[verse obj]),
                              ...]

        Multiple verse_objs are possible where there are multiple hands
        at work and in commentary manuscripts that mention the verse
        more than once.
        """
        v_d = {}
        for hand in Hand.objects.filter(manuscript=self):
            for verse in MsVerse.objects.filter(verse__chapter=chapter_obj,
                                                hand=hand,
                                                ).order_by('verse__num'):
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
    text = models.CharField(max_length=1000)

    def __unicode__(self):
        return "MsVerse: ms:{}, hand:{}, verse:{} ({})".format(
            self.hand.manuscript.id,
            self.hand.name,
            self.verse,
            self.item)


class Variant(models.Model):
    verse = models.ForeignKey(Verse)
    variant_num = models.IntegerField()


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
            max_label = Reading.objects.filter(variant=self.variant).aggregate(Max('label'))['label__max'] or 0
            self.label = max_label + 1

        super(Reading, self).save()

    def display_label(self):
        return string.lowercase[self.label - 1]

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
    
    def __unicode__(self):
        return u"Stripe: verse {}, readings {}".format(self.verse,
                                                       self.readings)


class MsStripe(models.Model):
    """
    A HandStripe is a many-to-many mapping of hands to stripes.
    """
    stripe = models.ForeignKey(Stripe)
    ms_verse = models.ForeignKey(MsVerse)

    def __unicode__(self):
        return u"HandStripe: ms_verse {}, stripe {}".format(self.ms_verse,
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


def get_all_verses(book_obj, chapter_obj):
    """
    Return all verses in a particular chapter, in this form:

    [(1,
      [(<ManuscriptTranscription: Manuscript 04_1424 transcription (loaded)>,
       [<MsVerse: MsVerse: ms:46, hand:firsthand, chapter:Chapter object, v:1-0>]),
      (<ManuscriptTranscription: Manuscript 04_579 transcription (loaded)>,
       [<MsVerse: MsVerse: ms:47, hand:firsthand, chapter:Chapter object, v:1-0>,
        <MsVerse: MsVerse: ms:47, hand:corrector, chapter:Chapter object, v:1-0>]),
      (<ManuscriptTranscription: Manuscript 04_03 transcription (loaded)>,
       [<MsVerse: MsVerse: ms:50, hand:firsthand, chapter:Chapter object, v:1-0>]),
      ...],
     (2,
      [...]]
    """
    all_mss = ManuscriptTranscription.objects.all()
    vs_d = {}
    for ms in all_mss:
        verses = ms.get_text(book_obj, chapter_obj)
        #  [(1,[verse obj, verse obj, ...]),
        #   (2,[verse obj]),
        #   ...]
        for v in verses:
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


class memoize(dict):
    """
    A memoize decorator from:
     http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize
    """
    def __init__(self, func):
        self.func = func

    def __call__(self, *args):
        return self[args]

    def __missing__(self, key):
        result = self[key] = self.func(*key)
        return result

@memoize
def collate(chapter_obj, verse_obj, base_ms_id):
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
        stripes = Stripe.objects.filter(verse=verse)
        my_data = []
        for st in stripes:
            ms_stripes = MsStripe.objects.filter(stripe=st)
            my_data.append((st, ms_stripes))

        # Now sort it so that our base_ms_id appears in the first entry each time
        collation.append((verse,
                          sorted(my_data,
                                 key=lambda x: base_ms_id not in
                                               [y.ms_verse.hand.manuscript.id for y in x[1]])))

    return collation
