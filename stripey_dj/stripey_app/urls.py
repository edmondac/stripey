from django.conf.urls import patterns, url

urlpatterns = patterns('stripey_app.views',
    url(r'^$', 'index'),
    url(r'index.html', 'index'),
    url(r'load.html', 'load'),
    url(r'manuscript.html', 'manuscript'),
)
