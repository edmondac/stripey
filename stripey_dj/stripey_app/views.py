from django.shortcuts import render_to_response, get_object_or_404
from stripey_app.models import (ManuscriptTranscription, Book, Chapter,
                                Hand, Verse, MsVerse, get_all_verses,
                                collate, Algorithm)
from django.http import HttpResponseRedirect

import logging
logger = logging.getLogger('stripey_app.views')


def default_response(request, url, data):
    if 'base_ms_id' not in data:
        data['base_ms_id'] = int(request.COOKIES.get('base_ms', '0'))
    if 'all_mss' not in data:
        data['all_mss'] = ManuscriptTranscription.objects.all().order_by('liste_id')
    if 'show_accents' not in data:
        data['show_accents'] = request.COOKIES.get('show_accents', 'none')

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
    verses = MsVerse.objects.filter(hand__in=hands)
    chapters = Chapter.objects.filter(id__in=list(set([v.verse.chapter.id for v in verses]))).order_by('num')

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
    chapter.verses = verses.filter(verse__chapter=chapter).order_by('verse__num')

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
    algorithm_obj = Algorithm.objects.get(name=request.GET.get('al'))
    chapter_obj = Chapter.objects.get(book=book_obj,
                                      num=request.GET.get('ch'))
    v = request.GET.get('v')
    is_last_verse = None
    if (v is not None and v != 'None'):
        v = int(v)
        verse_obj = Verse.objects.get(chapter=chapter_obj,
                                      num=v)
        last_verse = Verse.objects.filter(chapter=chapter_obj).order_by('-num')[0]
        if last_verse.num == verse_obj.num:
            is_last_verse = True
    else:
        verse_obj = None

    last_chapter = Chapter.objects.filter(book=book_obj).order_by('-num')[0]
    is_last_chapter = False
    if chapter_obj.num == last_chapter.num:
        is_last_chapter = True

    # Get our memoized collation data
    collation = collate(chapter_obj, verse_obj, algorithm_obj, base_ms_id)

    algos = Algorithm.objects.all()

    return default_response(request,
                            'collation.html',
                            {'book': book_obj,
                             'chapter': chapter_obj,
                             'v': v,
                             'collation': collation,
                             'is_last_chapter': is_last_chapter,
                             'is_last_verse': is_last_verse,
                             'algorithm': algorithm_obj,
                             'algorithms': algos})


def set_base_text(request):
    """
    Sets the base text to use and returns to the HTTP REFERER
    """
    base_ms = get_object_or_404(ManuscriptTranscription, pk=request.GET.get('base_ms_id'))
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

    v = request.GET.get('v')
    if v == 'None':
        #FIXME - needed???
        v = None
    is_last_verse = None
    if v:
        v = int(v)
        verse_obj = Verse.objects.get(chapter=chapter_obj,
                                      num=v)
        last_verse = Verse.objects.filter(chapter=chapter_obj).order_by('-num')[0]
        if last_verse.num == verse_obj.num:
            is_last_verse = True
    else:
        verse_obj = None

    all_verses = get_all_verses(book_obj, chapter_obj, base_ms_id, v)
    # Group readings together... We want a list of readings for each verse, with a list of witnesses per reading.
    grouped_verses = []
    for vs, mss in all_verses:
        readings = {}
        for ms, verses in mss:
            for verse in verses:
                if len(verses) > 1:
                    wit = (ms, verse.hand.name)
                else:
                    wit = (ms, None)
                witnesses = readings.get(verse.text, ([], verse.similarity))
                witnesses[0].append(wit)
                readings[verse.text] = witnesses

        # Sort each group by liste id
        for i in readings:
            readings[i][0].sort(key=lambda a: a[0].liste_id)

        # Now sort the groups so our base_ms is in the top one (if present)
        all_readings = sorted(readings.items(), key=lambda a: a[1][1], reverse=True)

        grouped_verses.append((vs, all_readings))

    algos = Algorithm.objects.all()

    return default_response(request,
                            'chapter.html',
                            {'book': book_obj,
                             'chapter': chapter_obj,
                             'v': v,
                             'verses': grouped_verses,
                             'is_last_chapter': is_last_chapter,
                             'is_last_verse': is_last_verse,
                             'algorithms': algos})
