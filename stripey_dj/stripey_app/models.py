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

    def load(self):
        if self.status in ('loaded', 'collated'):
            logger.debug("MS {} is already loaded - ignoring".format(self))
            return

        logger.info("Loading MS {}".format(self))
        obj = xmlmss.Manuscript(self.ms_ref, self.xml_filename)
        if not obj.book:
            raise ValueError("Couldn't work out the book")

        db_book = _get_book(obj.book, obj.num)

        for ch in obj.chapters.values():
            db_chapter = _get_chapter(db_book, ch.num)

            for vs in ch.verses.values():
                for i, hand in enumerate(vs.hands):
                    db_hand = _get_hand(self, hand)
                    db_verse = Verse()
                    db_verse.chapter = db_chapter
                    db_verse.hand = db_hand
                    db_verse.num = vs.num
                    db_verse.text = vs.texts[i]
                    db_verse.save()

        self.status = 'loaded'
        self.save()

    def __unicode__(self):
        return "Manuscript {} transcription ({})".format(
            self.ms_ref,
            self.status)

    def get_text(self, book_obj, chapter_obj):
        """
        Return the text of the relevant book, chapter (db objects)
        in a list of tuples of tuples [(1,((hand, text), (hand2, text)),
                                       (2,((hand, text)...]
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
                me.append((hand.name, verse.text))

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
    [(1, [(<ManuscriptTranscription: Manuscript 87 transcription (loaded)>,
           [(u'firsthand', u'(greek text)'),
            (u'secunda_manu', u'(greek text)')]),
          (<ManuscriptTranscription...
     (2, [(<ManuscriptTranscription: Manuscript 01 transcription (loaded)>,
           [(u'firsthand', u'(greek text)')]),
          (<ManuscriptTranscription: Manuscript 02 transcription (loaded)>,
           [(u'firsthand', u'(greek text)')]), ...
    """
    all_mss = ManuscriptTranscription.objects.all()
    vs_d = {}
    for ms in all_mss:
        verses = ms.get_text(book_obj, chapter_obj)
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
