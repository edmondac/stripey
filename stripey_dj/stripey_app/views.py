import os
from django.shortcuts import render_to_response, redirect, get_object_or_404
from stripey_app.models import ManuscriptTranscription, Book, Chapter, Hand, Verse
from stripey_lib import xmlmss
from django.core.exceptions import ObjectDoesNotExist
from django.utils.encoding import smart_unicode

import logging
logger = logging.getLogger('stripey_app.views')

from stripey_lib import collatex as _mod
os.environ['COLLATE_JAR_PATH'] = os.path.dirname(_mod.__file__)
logger.debug(os.environ['COLLATE_JAR_PATH'])
from stripey_lib.collatex import collatex

def index(request):
    all_mss = ManuscriptTranscription.objects.all().order_by('ms_ref')
    n_loaded = ManuscriptTranscription.objects.filter(status='loaded').count()
    n_new = all_mss.count() - n_loaded
    books = Book.objects.all().order_by('num')
    # We want a list of chapters - per book.
    for book in books:
        book.chapters = Chapter.objects.filter(book=book).order_by('num')

    return render_to_response('index.html', {'all_mss': all_mss,
                                             'n_loaded': n_loaded,
                                             'n_new': n_new,
                                             'books': books})


def manuscript(request):
    ms = get_object_or_404(ManuscriptTranscription, pk=request.GET.get('ms_id'))
    hands = Hand.objects.filter(manuscript=ms)
    verses = Verse.objects.filter(hand__in=hands)
    chapters = Chapter.objects.filter(id__in=list(set([v.chapter.id for v in verses]))).order_by('num')

    books = Book.objects.filter(id__in=list(set([c.book.id for c in chapters]))).order_by('num')

    # We want a list of chapters - per book.
    for book in books:
        book.chapters = chapters.filter(book=book)

    # Are we showing any particular text?
    book_num = request.GET.get('bk')
    if book_num:
        book = [x for x in books if x.num == int(book_num)][0]
    else:
        # Show the first one
        book = books[0]

    chapter_num = request.GET.get('ch')
    if chapter_num:
        chapter = book.chapters.filter(num=chapter_num)[0]
    else:
        # Show the first one
        chapter = book.chapters[0]

    # Set the verses to display
    chapter.verses = verses.filter(chapter=chapter).order_by('num')

    return render_to_response('manuscript.html', {'ms': ms,
                                                  'hands': [x.name for x in hands],
                                                  'books': books,
                                                  'chapter_to_show': chapter})


def collate(request):
    """
    Collate all manuscripts
    """
    book_obj = Book.objects.filter(num=request.GET.get('bk'))[0]
    chapter_obj = Chapter.objects.filter(book=book_obj,
                                         num=request.GET.get('ch'))[0]
    all_verses = _get_all_verses(book_obj, chapter_obj)
    collated_verses = []
    for v, mss in all_verses:
        collation = collatex.Collation()
        for ms in mss:
            for hand, greek in ms[1]:
                collation.add_witness('{}:{}'.format(ms[0].ms_ref, hand), greek)
        rows = collation.get_alignment_table().rows
        
        collated_verses.append((v, [(row.sigil,
                                    [smart_unicode(unicode(i.token)) for i in row.cells])
                                    for row in rows]))
        break

    return render_to_response('collate.html', {'book': book_obj,
                                               'chapter': chapter_obj,
                                               'verses': collated_verses})
            

def chapter(request):
    """
    View the text of a chapter in all manuscripts
    """
    book_obj = Book.objects.filter(num=request.GET.get('bk'))[0]
    chapter_obj = Chapter.objects.filter(book=book_obj,
                                         num=request.GET.get('ch'))[0]
    all_verses = _get_all_verses(book_obj, chapter_obj)
    return render_to_response('chapter.html', {'book': book_obj,
                                               'chapter': chapter_obj,
                                               'verses': all_verses})
        

def _get_all_verses(book_obj, chapter_obj):
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

        db_book = _get_book(obj.book, obj.num)

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
