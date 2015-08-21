from django.conf.urls import patterns, url

urlpatterns = patterns(
    'stripey_app.views',
    url(r'^$', 'index'),
    url(r'index.html', 'index'),
    url(r'search.html', 'search'),
    url(r'book.html', 'book'),
    url(r'chapter.html', 'chapter'),
    url(r'collation.html', 'collation'),
    url(r'set_base_text.html', 'set_base_text'),
    url(r'hand.html', 'hand'),
    url(r'manuscript.html', 'manuscript'),
    url(r'manuscript_correctors.json', 'manuscript_correctors_json'),
    url(r'book_correctors.json', 'book_correctors_json'),
    url(r'chapter_correctors.json', 'chapter_correctors_json'),
    url(r'nexus.html', 'nexus'),
    url(r'nexus_file.txt', 'nexus_file'),
)

urlpatterns += patterns(
    '',
    url(r'^logout/$', 'django.contrib.auth.views.logout', {'next_page': '/'}))
