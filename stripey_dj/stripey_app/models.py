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
