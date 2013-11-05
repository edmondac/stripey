from django.shortcuts import render_to_response, get_object_or_404
from stripey_app.models import (ManuscriptTranscription, Book, Chapter,
                                Hand, Verse, MsVerse, get_all_verses,
                                collate, Algorithm, MsChapter)
from django.http import HttpResponseRedirect, HttpResponse
import json
from memoize import memoize
from collections import defaultdict
import logging
logger = logging.getLogger('stripey_app.views')


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


def hand(request):
    """
    Display info about this manuscript hand
    """
    ms_id = request.GET.get('ms_id')
    hand_name = request.GET.get('hand')
    ms = get_object_or_404(ManuscriptTranscription, pk=ms_id)
    all_hands = Hand.objects.filter(manuscript=ms)
    hand = all_hands.filter(name=hand_name)[0]

    # Per-chapter list of refs
    chapter_refs = []
    for ch in MsChapter.objects.filter(manuscript=ms).order_by('chapter__book__num', 'chapter__num'):
        verses = MsVerse.objects.filter(hand=hand, verse__chapter=ch.chapter).count()
        if verses:
            chapter_refs.append((ch.chapter, verses))

    total_corrections = sum([x[1] for x in chapter_refs])

    return default_response(request,
                            'hand.html',
                            {'hand': hand_name,
                             'other_hands': [x.name for x in all_hands if x != hand],
                             'chapter_refs': chapter_refs,
                             'total_corrections': total_corrections,
                             'ms': ms})

def manuscript(request):
    """
    Display info about this manuscript
    """
    ms_id = request.GET.get('ms_id')
    ms = get_object_or_404(ManuscriptTranscription, pk=ms_id)

    # Needed for all situations
    my_books = []
    all_books = Book.objects.all().order_by('num')
    for book in all_books:
        chapters = [x.chapter for x in
                    MsChapter.objects.filter(manuscript=ms,
                                             chapter__book=book).order_by('chapter__num')]
        if chapters:
            # Record this book, and add its chapters to it
            my_books.append(book)
            book.chapters = chapters

    # Needed if we've got a book specified
    book_to_show = None
    bk_id = request.GET.get('bk')
    if bk_id:
        book_to_show = [x for x in my_books if x.num == int(bk_id)][0]

    # Needed if we've got a chapter specified
    chapter_to_show = None
    ch_id = request.GET.get('ch')
    if ch_id:
        assert book_to_show, "Should have a book to show"
        hands, chapter_to_show = _manuscript_chapter_data(ms_id, bk_id, ch_id)
    else:
        hands = Hand.objects.filter(manuscript=ms)

    correctors = [x.name for x in hands if x.name != 'firsthand']
    correctors.sort()

    return default_response(request,
                            'manuscript.html',
                            {'ms': ms,
                             'correctors': correctors,
                             'books': my_books,
                             'book_to_show': book_to_show,
                             'chapter_to_show': chapter_to_show})


#~ def manuscript_book(request):
    #~ """
    #~ Display info about the specified book in this manuscript
    #~ """
    #~ ms, book, chapters = _manuscript_book_data(ms_id, book_num)
    #~ return default_response(request,
                            #~ 'manuscript_book.html',
                            #~ {'ms': ms,
                             #~ 'book': book,
                             #~ 'chapters': chapters})
#~

#~ def _manuscript_book_data(request):
    #~ """
    #~ Display info about the specified book in this manuscript
    #~ """
    #~ ms = get_object_or_404(ManuscriptTranscription, pk=request.GET.get('ms_id'))
    #~ hands = Hand.objects.filter(manuscript=ms)
    #~ book = get_object_or_404(Book, num=request.GET.get('bk'))
    #~ chapters = [x.chapter for x in
                #~ MsChapter.objects.filter(chapter__book=book,
                                         #~ manuscript=ms).order_by('chapter__num')]
    #~ return (ms, hands, book, chapters)


@memoize
def _manuscript_chapter_data(ms_id, bk, ch):
    """
    Parse the request and return the data required to make the manuscript page
    and also the correctors json blob
    """
    ms = get_object_or_404(ManuscriptTranscription, pk=ms_id)
    my_chapter = get_object_or_404(Chapter, num=ch, book__num=bk)
    hands = Hand.objects.filter(manuscript=ms)

    # Set the verses to display
    verses = MsVerse.objects.filter(hand__in=hands)
    my_chapter.verses = verses.filter(verse__chapter__num=ch).order_by('verse__num',
                                                                       'hand__id')
    return hands, my_chapter


#~ def manuscript_chapter(request):
    #~ """
    #~ Show the text for this manuscript (of the specified book/chapter or just
    #~ the first one we find.
    #~ """
    #~ (ms, hands, books, chapter) = _manuscript_chapter_data(request.GET.get('ms_id'),
                                                           #~ request.GET.get('bk'),
                                                           #~ request.GET.get('ch'))
    #~ return default_response(request,
                            #~ 'manuscript.html',
                            #~ {'ms': ms,
                             #~ 'hands': [x.name for x in hands],
                             #~ 'books': books,
                             #~ 'chapter_to_show': chapter})


def manuscript_correctors_json(request):
    """
    Return the JSON blob to draw the correctors graph for this manuscript
    """
    ms = get_object_or_404(ManuscriptTranscription, pk=request.GET.get('ms_id'))
    hands = [x for x in Hand.objects.filter(manuscript=ms) if x.name != 'firsthand']
    my_books = set([c.chapter.book for c in MsChapter.objects.filter(manuscript=ms)])

    matrix = []
    for h in hands:
        # No hand refers to itself
        row = [0 for i in hands]
        for book in my_books:
            refs = MsVerse.objects.filter(hand=h, verse__chapter__book=book).count()
            # For now, just say every hand refers to every chapter
            row.append(refs)
        matrix.append(row)

    # We don't need to calculate it all again - just look up the relevant value
    # in the matrix and put a 1 in place, to make it look pretty.
    tot_h = len(hands)
    for i, b in enumerate(my_books):
        row = []
        for j in range(tot_h):
            ref = 1 if matrix[j][tot_h+i] else 0
            row.append(ref)
        # No book refers to itself
        row.extend([0 for i in my_books])
        matrix.append(row)

    ret = {'packageNames': [h.name for h in hands] + [b.name.title() for b in my_books],
           'matrix': matrix}

    return HttpResponse(json.dumps(ret), mimetype='application/json')


def book_correctors_json(request):
    """
    Return the JSON blob to draw the correctors graph for this book
    """
    ms = get_object_or_404(ManuscriptTranscription, pk=request.GET.get('ms_id'))
    bk_id = request.GET.get('bk')
    hands = [x for x in Hand.objects.filter(manuscript=ms) if x.name != 'firsthand']
    chapters = Chapter.objects.filter(book__num=bk_id).order_by('num')

    matrix = []
    for h in hands:
        # No hand refers to itself
        row = [0 for i in hands]
        for chapter in chapters:
            refs = MsVerse.objects.filter(hand=h, verse__chapter=chapter).count()
            # For now, just say every hand refers to every chapter
            row.append(refs)
        matrix.append(row)

    # We don't need to calculate it all again - just look up the relevant value
    # in the matrix and put a 1 in place, to make it look pretty.
    tot_h = len(hands)
    for i, c in enumerate(chapters):
        row = []
        for j in range(tot_h):
            ref = 1 if matrix[j][tot_h+i] else 0
            row.append(ref)
        # No chapter refers to itself
        row.extend([0 for i in chapters])
        matrix.append(row)

    ret = {'packageNames': [h.name for h in hands] + ["Ch {}".format(c.num) for c in chapters],
           'matrix': matrix}

    return HttpResponse(json.dumps(ret), mimetype='application/json')


def chapter_correctors_json(request):
    """
    Return the JSON blob to draw the correctors graph for this chapter
    """
    # We care about hands and chapter.verses here
    #~ ret = {'hands': ['a', 'b', 'v'],
           #~ 'verses': [(1, ['a']),
                      #~ (2, ['b']),
                      #~ (3, ['a', 'v'])]}
    hands, chapter = _manuscript_chapter_data(request.GET.get('ms_id'),
                                              request.GET.get('bk'),
                                              request.GET.get('ch'))
    found_hands = set()
    verses = defaultdict(list)
    for v in chapter.verses:
        if v.hand.name == 'firsthand':
            # initialise the empty list
            verses[v.verse.num]
        else:
            found_hands.add(v.hand.name)
            verses[v.verse.num].append(v.hand.name)
    verses_l = []
    for k in sorted(verses.keys()):
        verses_l.append((k, verses[k]))
    ret = {'hands': list(found_hands),
           'verses': verses_l}
           #~ 'verses': [(v.verse.num, [x.name for x in v.hand])
                      #~ for v in chapter.verses]}
    return HttpResponse(json.dumps(ret), mimetype='application/json')


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
    v = int(v)
    last_verse = Verse.objects.filter(chapter=chapter_obj).order_by('-num')[0]
    is_last_verse = None
    if last_verse.num == v:
        is_last_verse = True

    all_verses = get_all_verses(book_obj, chapter_obj, base_ms_id, v)
    # Group readings together... We want a list of readings for each verse, with a list of witnesses per reading.
    grouped_verses = []
    for vs, mss in all_verses:
        readings = {}
        for ms, verses in mss:
            for verse in verses:
                witnesses = readings.setdefault(verse.text,
                                                ([], verse.similarity))[0]
                witnesses.append((ms, verse.hand.name))

        # Sort each group by liste id
        for i in readings:
            readings[i][0].sort(key=lambda a: a[0].liste_id)

        # Now sort the groups so our base_ms is in the top one (if present)
        all_readings = sorted(readings.items(), key=lambda a: a[1][1], reverse=True)

        grouped_verses.append((vs, all_readings))

    assert len(grouped_verses) == 1, grouped_verses

    algos = Algorithm.objects.all()

    return default_response(request,
                            'chapter.html',
                            {'book': book_obj,
                             'chapter': chapter_obj,
                             'v': v,
                             'verse': grouped_verses[0],
                             'is_last_chapter': is_last_chapter,
                             'is_last_verse': is_last_verse,
                             'algorithms': algos})
