from django.shortcuts import render_to_response, get_object_or_404
from stripey_app.models import (ManuscriptTranscription, Book, Chapter,
                                Hand, Verse, get_all_verses,
                                MappedCollation)
from django.http import HttpResponseRedirect

import logging
logger = logging.getLogger('stripey_app.views')

#~ from stripey_lib import collatex as _mod
#~ os.environ['COLLATE_JAR_PATH'] = os.path.dirname(_mod.__file__)
#~ logger.debug(os.environ['COLLATE_JAR_PATH'])
#~ from stripey_lib.collatex import collatex


def default_response(request, url, data):
    if 'base_ms_id' not in data:
        data['base_ms_id'] = int(request.COOKIES.get('base_ms', '0'))
    if 'all_mss' not in data:
        data['all_mss'] = ManuscriptTranscription.objects.all().order_by('liste_id')

    return render_to_response(url, data)


def index(request):
    all_mss = ManuscriptTranscription.objects.all().order_by('liste_id')
    books = Book.objects.all().order_by('num')
    # We want a list of chapters - per book.
    for book in books:
        book.chapters = Chapter.objects.filter(book=book).order_by('num')

    return default_response(request,
                            'index.html',
                            {'all_mss': all_mss,
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
        chapter = book.chapters.get(num=chapter_num)
    else:
        # Show the first one
        chapter = book.chapters[0]

    # Set the verses to display
    chapter.verses = verses.filter(chapter=chapter).order_by('num')

    return default_response(request,
                            'manuscript.html',
                            {'ms': ms,
                             'hands': [x.name for x in hands],
                             'books': books,
                             'chapter_to_show': chapter})


def collation(request):
    """
    Show the requested chapter in collated variants.
    """
    base_ms_id = int(request.COOKIES.get('base_ms', '0'))
    book_obj = Book.objects.get(num=request.GET.get('bk'))
    chapter_obj = Chapter.objects.get(book=book_obj,
                                      num=request.GET.get('ch'))

    last_chapter = Chapter.objects.filter(book=book_obj).order_by('-num')[0]
    is_last_chapter = False
    if chapter_obj.num == last_chapter.num:
        is_last_chapter = True

    collation = MappedCollation(book_obj, chapter_obj).get_stripes(base_ms_id)
    return default_response(request,
                            'collation.html',
                            {'book': book_obj,
                             'chapter': chapter_obj,
                             'collation': collation,
                             'is_last_chapter': is_last_chapter})


def set_base_text(request):
    """
    Sets the base text to use, the returns to the HTTP REFERER
    """
    base_ms = get_object_or_404(ManuscriptTranscription, pk=request.GET.get('ms_id'))
    referer = request.META.get('HTTP_REFERER', '/index.html')
    ret = HttpResponseRedirect(referer)
    ret.set_cookie('base_ms', value=base_ms.id, max_age=3600 * 24 * 365)
    return ret


def chapter(request):
    """
    View the text of a chapter in all manuscripts
    """
    base_ms_id = int(request.COOKIES.get('base_ms', '0'))
    book_obj = Book.objects.get(num=request.GET.get('bk'))
    chapter_obj = Chapter.objects.get(book=book_obj,
                                      num=request.GET.get('ch'))

    last_chapter = Chapter.objects.filter(book=book_obj).order_by('-num')[0]
    is_last_chapter = False
    if chapter_obj.num == last_chapter.num:
        is_last_chapter = True

    all_verses = get_all_verses(book_obj, chapter_obj)
    # Group readings together... We want a list of readings for each verse, with a list of witnesses per reading.
    grouped_verses = []
    for v, mss in all_verses:
        readings = {}
        for ms, verses in mss:
            for verse in verses:
                if len(verses) > 1:
                    wit = (ms, verse.hand.name)
                else:
                    wit = (ms, None)
                witnesses = readings.get(verse.text, [])
                witnesses.append(wit)
                readings[verse.text] = witnesses

        # Sort each group by ms id
        for i in readings:
            readings[i].sort(lambda a, b: cmp(a[0].liste_id, b[0].liste_id))

        # Now sort the groups so our base_ms is in the top one (if present)
        all_readings = readings.items()

        def sort_fn(a, b):
            a_ids = [x[0].id for x in a[1]]
            b_ids = [y[0].id for y in b[1]]
            if base_ms_id in a_ids:
                return -1
            elif base_ms_id in b_ids:
                return 1
            else:
                return 0

        all_readings.sort(sort_fn)
        grouped_verses.append((v, all_readings))

    return default_response(request,
                            'chapter.html',
                            {'book': book_obj,
                             'chapter': chapter_obj,
                             'verses': grouped_verses,
                             'is_last_chapter': is_last_chapter})


#~ def load(request):
    #~ all_mss = ManuscriptTranscription.objects.all()
    #~ for ms in all_mss:
        #~ if ms.status in ('loaded', 'collated'):
            #~ logger.debug("MS {} is already loaded - ignoring".format(ms))
            #~ continue
#~
        #~ logger.info("Loading MS {}".format(ms))
        #~ obj = xmlmss.Manuscript(ms.ms_ref, ms.xml_url)
        #~ if not obj.book:
            #~ raise ValueError("Couldn't work out the book")
#~
        #~ db_book = _get_book(obj.book, obj.num)
#~
        #~ for ch in obj.chapters.values():
            #~ db_chapter = _get_chapter(db_book, ch.num)
#~
            #~ for vs in ch.verses.values():
                #~ for i, hand in enumerate(vs.hands):
                    #~ db_hand = _get_hand(ms, hand)
                    #~ db_verse = Verse()
                    #~ db_verse.chapter = db_chapter
                    #~ db_verse.hand = db_hand
                    #~ db_verse.num = vs.num
                    #~ db_verse.text = vs.texts[i]
                    #~ db_verse.save()
#~
        #~ ms.status = 'loaded'
        #~ ms.save()

    #~ return redirect('index.html')
