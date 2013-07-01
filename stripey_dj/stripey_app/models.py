from django.db import models
from django.core.exceptions import ObjectDoesNotExist
from stripey_lib import xmlmss

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
    liste_id = models.IntegerField()

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
        logger.debug(u"Found info: {}, {}, {}, {}".format(self.ms_name,
                                                          self.tischendorf,
                                                          self.ga,
                                                          self.liste_id))

        db_book = _get_book(obj.book, obj.num)

        for ch in obj.chapters.values():
            db_chapter = _get_chapter(db_book, ch.num)

            for verse_list in ch.verses.values():
                for j, vs in enumerate(verse_list):
                    for i, hand in enumerate(vs.hands):
                        db_hand = _get_hand(self, hand)
                        db_verse = Verse()
                        db_verse.chapter = db_chapter
                        db_verse.hand = db_hand
                        db_verse.num = vs.num
                        db_verse.item = j
                        db_verse.text = vs.texts[i]
                        db_verse.save()

        self.status = 'loaded'
        self.save()

    def __unicode__(self):
        return "Manuscript {} transcription ({})".format(
            self.ms_ref,
            self.status)

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
            for verse in Verse.objects.filter(chapter=chapter_obj,
                                              hand=hand,
                                              ).order_by('num'):
                me = v_d.get(verse.num)
                if not me:
                    me = []
                    v_d[verse.num] = me
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


class Book(models.Model):
    name = models.CharField(max_length=20)
    num = models.IntegerField()


class Chapter(models.Model):
    book = models.ForeignKey(Book)
    num = models.IntegerField()


class Verse(models.Model):
    chapter = models.ForeignKey(Chapter)
    hand = models.ForeignKey(Hand)
    num = models.IntegerField()
    item = models.IntegerField()  # for "duplicate" verses
    text = models.CharField(max_length=1000)

    def __unicode__(self):
        return "Verse: ms:{}, hand:{}, chapter:{}, v:{}-{}".format(
            self.hand.manuscript.id,
            self.hand.name,
            self.chapter,
            self.num,
            self.item)


class CollatedVerse(models.Model):
    verse = models.ForeignKey(Verse)
    variant = models.IntegerField()
    text = models.CharField(max_length=1000)


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
       [<Verse: Verse: ms:46, hand:firsthand, chapter:Chapter object, v:1-0>]),
      (<ManuscriptTranscription: Manuscript 04_579 transcription (loaded)>,
       [<Verse: Verse: ms:47, hand:firsthand, chapter:Chapter object, v:1-0>,
        <Verse: Verse: ms:47, hand:corrector, chapter:Chapter object, v:1-0>]),
      (<ManuscriptTranscription: Manuscript 04_03 transcription (loaded)>,
       [<Verse: Verse: ms:50, hand:firsthand, chapter:Chapter object, v:1-0>]),
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
