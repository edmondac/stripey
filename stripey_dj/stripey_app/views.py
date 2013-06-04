from django.shortcuts import render_to_response, redirect
from stripey_app.models import ManuscriptTranscription, Book, Chapter, Hand, Verse
from stripey_lib import xmlmss
from django.core.exceptions import ObjectDoesNotExist

import logging
logger = logging.getLogger('stripey_app.views')

def index(request):
    all_mss = ManuscriptTranscription.objects.all().order_by('-ms_ref')
    n_loaded = ManuscriptTranscription.objects.filter(status='loaded').count()
    n_collated = ManuscriptTranscription.objects.filter(status='collated').count()
    n_new = all_mss.count() - n_loaded - n_collated

    return render_to_response('stripey_app/index.html', {'all_mss': all_mss,
														 'n_loaded': n_loaded,
														 'n_new': n_new})

def load(request):
    all_mss = ManuscriptTranscription.objects.all()
    for ms in all_mss:
        if ms.status in ('loaded', 'collated'):
            logger.debug("MS {} is already loaded - ignoring".format(ms))
            continue
        
        logger.info("Loading MS {}".format(ms))
        obj = xmlmss.Manuscript(ms.ms_ref, ms.xml_url)
        if not obj.book:
            raise ValueError("Couldn't work out the book")
            
        db_book = _get_book(obj.book)

        for ch in obj.chapters.values():
            db_chapter = _get_chapter(db_book, ch.num)
            
            for vs in ch.verses.values():
                for i, hand in enumerate(vs.hands):
                    db_hand = _get_hand(ms, hand)
                    db_verse = Verse()
                    db_verse.chapter = db_chapter
                    db_verse.hand = db_hand
                    db_verse.num = vs.num
                    db_verse.text = vs.texts[i]
                    db_verse.save()
        
        ms.status = 'loaded'
        ms.save()
        
    return redirect('index.html')
	
def _get_book(name):
    try:
        db_book = Book.objects.get(name=name)
    except ObjectDoesNotExist:
        logger.debug("Creating book object for {}".format(name))
        db_book = Book()
        db_book.name = name
        db_book.save()
    return db_book

def _get_chapter(db_book, num):
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
