from django.conf.urls import patterns, url

urlpatterns = patterns('stripey_app.views',
    url(r'^$', 'index'),
    url(r'index.html', 'index'),
    url(r'chapter.html', 'chapter'),
    url(r'collation.html', 'collation'),
    url(r'set_base_text.html', 'set_base_text'),
    url(r'manuscript.html', 'manuscript'),
    url(r'correctors.json', 'correctors_json'),
)
