import json
import string
import re
from collections import defaultdict
import logging
from django.shortcuts import render_to_response, get_object_or_404
from stripey_app.models import (ManuscriptTranscription, Book, Chapter,
                                Hand, Verse, MsVerse, get_all_verses,
                                collate, Algorithm, MsChapter, MsBook)
from django.http import HttpResponseRedirect, HttpResponse

from .memoize import memoize
logger = logging.getLogger('stripey_app.views')


def default_response(request, url, data):
    if 'base_ms_id' not in data:
        data['base_ms_id'] = int(request.COOKIES.get('base_ms', '0'))
    if 'all_mss' not in data:
        misc_mss = ManuscriptTranscription.objects.filter(liste_id__lt=10000).order_by('liste_id')
        pap_mss = ManuscriptTranscription.objects.filter(liste_id__lt=20000).filter(liste_id__gte=10000).order_by('liste_id')
        maj_mss = ManuscriptTranscription.objects.filter(liste_id__lt=30000).filter(liste_id__gte=20000).order_by('liste_id')
        min_mss = ManuscriptTranscription.objects.filter(liste_id__lt=40000).filter(liste_id__gte=30000).order_by('liste_id')
        lec_mss = ManuscriptTranscription.objects.filter(liste_id__gte=40000).order_by('liste_id')
        data['all_mss'] = (('Special', misc_mss),
                           ('Papyri', pap_mss),
                           ('Majuscules', maj_mss),
                           ('Minuscules', min_mss),
                           ('Lectionaries', lec_mss))
    data['query'] = request.GET.get('query') or ''
    data['absurl'] = request.build_absolute_uri('/').split('//', 1)[1]
    data['user'] = request.META.get('REMOTE_USER')
    return render_to_response(url, data)


def index(request):
    """
    The home page. Show a list of all manuscript transcriptions loaded.
    """
    misc_mss = ManuscriptTranscription.objects.filter(liste_id__lt=10000).order_by('liste_id')
    pap_mss = ManuscriptTranscription.objects.filter(liste_id__lt=20000).filter(liste_id__gte=10000).order_by('liste_id')
    maj_mss = ManuscriptTranscription.objects.filter(liste_id__lt=30000).filter(liste_id__gte=20000).order_by('liste_id')
    min_mss = ManuscriptTranscription.objects.filter(liste_id__lt=40000).filter(liste_id__gte=30000).order_by('liste_id')
    lec_mss = ManuscriptTranscription.objects.filter(liste_id__gte=40000).order_by('liste_id')

    books = Book.objects.all().order_by('num')
    # We want a list of chapters - per book.
    for book in books:
        book.chapters = Chapter.objects.filter(book=book).order_by('num')

    for mss in (misc_mss, pap_mss, maj_mss, min_mss, lec_mss):
        for ms in mss:
            ms.books = MsBook.objects.filter(manuscript=ms)

    return default_response(request,
                            'index.html',
                            {'all_mss': (('Special', misc_mss),
                                         ('Papyri', pap_mss),
                                         ('Majuscules', maj_mss),
                                         ('Minuscules', min_mss),
                                         ('Lectionaries', lec_mss)),
                             'books': books})


def search(request):
    """
    Search results
    """
    query = request.GET.get('query')

    res = MsVerse.objects.filter(raw_text__icontains=query).order_by(
        'verse__chapter__book__num',
        'verse__chapter__num',
        'verse__num',
        'hand__manuscript__liste_id')

    return default_response(request,
                            'search.html',
                            {'results': res,
                             'query': query})


def book(request):
    """
    Show a list of all manuscript transcriptions loaded for the specified book.
    """
    book_num = request.GET.get('bk')
    book = get_object_or_404(Book, num=book_num)

    misc_mss = ManuscriptTranscription.objects.filter(msbook__book__num=book_num).filter(liste_id__lt=10000).order_by('liste_id')
    pap_mss = ManuscriptTranscription.objects.filter(msbook__book__num=book_num).filter(liste_id__lt=20000).filter(liste_id__gte=10000).order_by('liste_id')
    maj_mss = ManuscriptTranscription.objects.filter(msbook__book__num=book_num).filter(liste_id__lt=30000).filter(liste_id__gte=20000).order_by('liste_id')
    min_mss = ManuscriptTranscription.objects.filter(msbook__book__num=book_num).filter(liste_id__lt=40000).filter(liste_id__gte=30000).order_by('liste_id')
    lec_mss = ManuscriptTranscription.objects.filter(msbook__book__num=book_num).filter(liste_id__gte=40000).order_by('liste_id')

    chapters = Chapter.objects.filter(book=book).order_by('num')

    for mss in (misc_mss, pap_mss, maj_mss, min_mss, lec_mss):
        for ms in mss:
            ms.books = MsBook.objects.filter(manuscript=ms)

    return default_response(request,
                            'book.html',
                            {'all_mss': (('Special', misc_mss),
                                         ('Papyri', pap_mss),
                                         ('Majuscules', maj_mss),
                                         ('Minuscules', min_mss),
                                         ('Lectionaries', lec_mss)),
                             'chapters': chapters,
                             'book': book})


def hand(request):
    """
    Display info about this manuscript hand
    """
    ms_id = request.GET.get('ms_id')
    hand_name = request.GET.get('hand')
    ms = get_object_or_404(ManuscriptTranscription, pk=ms_id)
    all_hands = Hand.objects.filter(manuscript=ms)
    hand = all_hands.filter(name=hand_name)[0]

    # Per-book list of refs
    book_refs = []
    for bk in MsBook.objects.filter(manuscript=ms).order_by('book__num'):
        # Per-chapter list of refs
        bk.chapter_refs = []
        for ch in MsChapter.objects.filter(manuscript=ms, chapter__book=bk.book).order_by('chapter__num'):
            verses = MsVerse.objects.filter(hand=hand, verse__chapter=ch.chapter).count()
            if verses:
                bk.chapter_refs.append((ch.chapter, verses))
        if bk.chapter_refs:
            book_refs.append((bk, sum([x[1] for x in bk.chapter_refs])))

    total_corrections = sum([b[1] for b in book_refs])

    return default_response(request,
                            'hand.html',
                            {'hand': hand_name,
                             'other_hands': [x.name for x in all_hands if x != hand],
                             'book_refs': book_refs,
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
    corrections_per_book = []
    all_books = Book.objects.all().order_by('num')
    for book in all_books:
        chapters = [x.chapter for x in
                    MsChapter.objects.filter(manuscript=ms,
                                             chapter__book=book).order_by('chapter__num')]
        if chapters:
            # Record this book, and add its chapters to it
            my_books.append(book)
            book.chapters = chapters

            # Now calculate how many corrected verses there are in this book
            n_corr = len(set([x.verse for x in
                              MsVerse.objects.filter(hand__manuscript=ms,
                                                     verse__chapter__book=book).exclude(hand__name='firsthand')]))
            n_vs = MsVerse.objects.filter(hand__manuscript=ms,
                                          verse__chapter__book=book,
                                          hand__name='firsthand').count()
            corrections_per_book.append((book, n_corr, 100.0 * n_corr / n_vs))

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

    correctors = [x.name for x in sorted(hands, key=lambda z:z.handorder) if x.name != 'firsthand']

    return default_response(request,
                            'manuscript.html',
                            {'ms': ms,
                             'correctors': correctors,
                             'corrections_per_book': corrections_per_book,
                             'books': my_books,
                             'book_to_show': book_to_show,
                             'chapter_to_show': chapter_to_show})


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
                                                                       'hand__handorder')
    return hands, my_chapter


def manuscript_correctors_json(request):
    """
    Return the JSON blob to draw the correctors graph for this manuscript
    """
    ms = get_object_or_404(ManuscriptTranscription, pk=request.GET.get('ms_id'))
    hands = [x for x in Hand.objects.filter(manuscript=ms).order_by('handorder') if x.name != 'firsthand']
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
            ref = 1 if matrix[j][tot_h + i] else 0
            row.append(ref)
        # No book refers to itself
        row.extend([0 for i in my_books])
        matrix.append(row)

    ret = {'packageNames': [h.name for h in hands] + [b.name.title() for b in my_books],
           'matrix': matrix}

    return HttpResponse(json.dumps(ret), content_type='application/json')


def book_correctors_json(request):
    """
    Return the JSON blob to draw the correctors graph for this book
    """
    ms = get_object_or_404(ManuscriptTranscription, pk=request.GET.get('ms_id'))
    bk_id = request.GET.get('bk')
    hands = [x for x in Hand.objects.filter(manuscript=ms).order_by('handorder') if x.name != 'firsthand']
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
            ref = 1 if matrix[j][tot_h + i] else 0
            row.append(ref)
        # No chapter refers to itself
        row.extend([0 for i in chapters])
        matrix.append(row)

    ret = {'packageNames': [h.name for h in hands] + ["Ch {}".format(c.num) for c in chapters],
           'matrix': matrix}

    return HttpResponse(json.dumps(ret), content_type='application/json')


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
            found_hands.add(v.hand)
            verses[v.verse.num].append(v.hand.name)
    verses_l = []
    for k in sorted(verses.keys()):
        verses_l.append((k, verses[k]))
    ret = {'hands': [h.name for h in sorted(found_hands, key=lambda x: x.handorder)],
           'verses': verses_l}

    return HttpResponse(json.dumps(ret), content_type='application/json')


def collation(request):
    """
    Show the requested chapter in collated variants.
    """
    base_ms_id = int(request.COOKIES.get('base_ms', '0'))
    book_obj = Book.objects.get(num=request.GET.get('bk'))
    algorithm_obj = Algorithm.objects.get(name=request.GET.get('al'))
    chapter_obj = Chapter.objects.get(book=book_obj,
                                      num=request.GET.get('ch'))
    v = _int_from_val(request.GET.get('v'))
    is_last_verse = None
    if v is not None:
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
    collation = collate(book_obj, chapter_obj, verse_obj, algorithm_obj, base_ms_id)

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
    base_ms_id = int(request.GET.get('base_ms_id'))
    if base_ms_id >= 0:
        # Check that's a valid ms id
        get_object_or_404(ManuscriptTranscription, pk=base_ms_id)
    else:
        # Un-set it by saying -1
        base_ms_id = -1

    referer = request.META.get('HTTP_REFERER', '/index.html')
    ret = HttpResponseRedirect(referer)
    ret.set_cookie('base_ms', value=base_ms_id, max_age=3600 * 24 * 365)
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

    v = _int_from_val(request.GET.get('v'))
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
        all_readings = sorted(list(readings.items()), key=lambda a: a[1][1], reverse=True)

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


def _int_from_val(x, default=None):
    """
    Returns an integer from the passed in value, unless it is
    None or the string 'None' - in which case it returns default.
    """
    if (x is not None and x != 'None' and x != ''):
        return int(x)
    else:
        return default


def nexus(request):
    """
    Create a nexus file, suitable for input to SplitsTree4
    """
    book_obj = Book.objects.get(num=request.GET.get('bk'))
    ch = _int_from_val(request.GET.get('ch'))
    v = _int_from_val(request.GET.get('v'))
    frag = _int_from_val(request.GET.get('frag'), 0)
    algorithm_obj = Algorithm.objects.get(name=request.GET.get('al'))
    algos = Algorithm.objects.all()
    nexus_variant = request.GET.get('variant', 'default')
    ga_regex = request.GET.get('ga_regex', '')

    restricted_bit = 'all'
    if ga_regex:
        restricted_bit = hash(ga_regex)

    nexus_filename = "stripey_{}{}{}_{}.{}.nex".format(book_obj.name.replace(' ', '_'),
                                                       '_{}'.format(ch) if ch else '',
                                                       '_{}'.format(v) if v else '',
                                                       restricted_bit,
                                                       algorithm_obj.name)

    return default_response(request,
                            'nexus.html',
                            {'book': book_obj,
                             'algorithm': algorithm_obj,
                             'algorithms': algos,
                             'ch': ch,
                             'v': v,
                             'nexus_variant': nexus_variant,
                             'nexus_filename': nexus_filename,
                             'frag': frag,
                             'frag_options': [0, 10, 20],
                             'ga_regex': ga_regex})


def nexus_file(request):
    """
    Takes a collation and makes a SplitsTree4-compatible nexus file
    """
    base_ms_id = int(request.COOKIES.get('base_ms', '0'))
    bk = request.GET.get('bk')
    ch = _int_from_val(request.GET.get('ch'))
    v = _int_from_val(request.GET.get('v'))
    frag = _int_from_val(request.GET.get('frag'), 0)
    al = request.GET.get('al')
    nexus_variant = request.GET.get('variant', None)
    ga_regex = request.GET.get('ga_regex', '')

    nexus = _nexus_file(bk, ch, v, al, base_ms_id, nexus_variant, frag, ga_regex)
    return HttpResponse(nexus, content_type='text/plain')


@memoize
def _nexus_file(bk, ch, v, al, base_ms_id, variant="default", frag=0, ga_regex=None):
    """
    Memoized innards of the nexus file creation
    @param bk: book num
    @param ch: chapter num or None for all chapters
    @param v: verse num or None for all verses
    @param al: algorithm name to use, e.g. dekker
    @param base_ms_id: id of the base manuscript for the collation
    @param variant: NEXUS file variant to create. Options are:
        * default - default (Mesquite and my modified MrBayes
        * mrbayes - has restrictions on symbols that can be used
    @param frag: the threshold (percentage) of variant units that a witness
             needs to have so as not to be considered "fragmentary" and thus
             be excluded.
    @param ga_regex: (optional) a regular expression used to restrict the witnesses
    """
    book_obj = Book.objects.get(num=bk)
    if ch is not None:
        chapter_obj = Chapter.objects.get(book=book_obj,
                                          num=ch)
        if v is not None:
            verse_obj = Verse.objects.get(chapter=chapter_obj,
                                          num=v)
        else:
            verse_obj = None
    else:
        chapter_obj = None
        verse_obj = None

    algorithm_obj = Algorithm.objects.get(name=al)

    ga_regex_re = None
    if ga_regex:
        ga_regex_re = re.compile(ga_regex)

    # Get our memoized collation data
    collation = collate(book_obj, chapter_obj, verse_obj, algorithm_obj, base_ms_id)

    if variant == 'mrbayes':
        LABELS = "0123456789"  # mrbayes doesn't support custom symbols...
    else:
        LABELS = string.ascii_letters

    MISSING = "-"
    GAP = "?"

    # to keep a list of unique taxa and count their variant units:
    taxa = defaultdict(int)
    symbols = set()
    matrix = {}  # keyed on verse, then {(ms_ga, hand_name): [labels], ...}

    for verse, data in collation:
        matrix[verse] = {}
        for stripe, mss in data:
            if ga_regex_re:
                mss = [x for x in mss if ga_regex_re.match(x.ms_verse.hand.manuscript.ga)]
                if not mss:
                    continue
                #~ print "Restricting by {} to {} mss".format(ga_regex, len(mss))

            stripe_labels = []
            for r in stripe.readings.all():
                if r.label == 0:
                    # Label 0 implies blank text => gap
                    stripe_labels.append(GAP)
                elif r.label > len(LABELS):
                    raise ValueError("Unsupported label index {} - check NEXUS variant"
                                     .format(r.label))
                else:
                    symbols.add(LABELS[r.label - 1])
                    stripe_labels.append(LABELS[r.label - 1])

            for ms in mss:
                hand = ms.ms_verse.hand
                ident = (hand.manuscript.ga,
                         hand.name.replace('(', '').replace(')', '').replace(':', '_'))
                if ident in matrix[verse]:
                    # Can't handle multiple instances of the same passage
                    # in a given hand. Ignore the rest...
                    print(("Ignoring {}'s subsequent reading of {}".format(
                        ident, ms.ms_verse.verse)))
                    continue
                matrix[verse][ident] = stripe_labels
                taxa[ident] += len(stripe_labels)
        if matrix[verse] == {}:
            print(("WARNING: Empty dict for {} - it will be omitted".format(verse)))
            del matrix[verse]

    # Remove fragmentary witnesses
    frag_thresh = max(taxa.values()) * frag / 100.0
    labs = [x for x in sorted(taxa.keys())
            if taxa[x] >= frag_thresh]
    if len(labs) < len(taxa):
        print(("WARNING: Ignoring {} fragmentary witnesses (threshold {}%)"
               .format(len(taxa) - len(labs), frag)))

    # Taxa section
    nexus = """#nexus
BEGIN Taxa;
DIMENSIONS ntax={};
TAXLABELS
""".format(len(labs))
    for i, l in enumerate(labs):
        #nexus += "[{}] '{}_{}'\n".format(i + 1, l[0], l[1])
        nexus += "{}_{}\n".format(l[0], l[1])
    nexus += ";\nEND;"

    # Characters section
    syms = sorted(symbols)

    # Now the matrix
    matrix_bit = "MATRIX\n"
    linelength = None
    for lab in labs:
        all_chars = []
        for verse in matrix:
            if lab in matrix[verse]:
                all_chars.extend(matrix[verse][lab])
            else:
                # Add correct num of "missing" signs
                any_old_lab = list(matrix[verse].keys())[0]
                for i in range(len(matrix[verse][any_old_lab])):
                    all_chars.append(MISSING)
        else:
            if linelength is not None:
                assert linelength == len(all_chars), (linelength, len(all_chars))
            linelength = len(all_chars)
            matrix_bit += "{}_{} {}\n".format(lab[0], lab[1], ''.join(all_chars))

    nexus += """
BEGIN Characters;
DIMENSIONS nchar={};

FORMAT
    datatype=STANDARD
    missing={}
    gap={}
    symbols="{}"
;
""".format(linelength, MISSING, GAP, ' '.join(syms))

    nexus += matrix_bit
    nexus += """;
END;
"""

    return nexus
