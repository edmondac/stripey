from django.db import models
import logging
logger = logging.getLogger('stripey_app.models')


class ManuscriptTranscription(models.Model):
    ms_ref = models.CharField(max_length=10)
    xml_url = models.CharField(max_length=200)
    status = models.CharField(max_length=20,
                              blank=True)

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
