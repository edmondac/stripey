from django.conf.urls import url
from stripey_app import views

urlpatterns = [
    url(r'^$', views.index),
    url(r'index.html', views.index),
    url(r'search.html', views.search),
    url(r'book.html', views.book),
    url(r'chapter.html', views.chapter),
    url(r'collation.html', views.collation),
    url(r'set_base_text.html', views.set_base_text),
    url(r'hand.html', views.hand),
    url(r'manuscript.html', views.manuscript),
    url(r'manuscript_correctors.json', views.manuscript_correctors_json),
    url(r'book_correctors.json', views.book_correctors_json),
    url(r'chapter_correctors.json', views.chapter_correctors_json),
    url(r'nexus.html', views.nexus),
    url(r'nexus_file.txt', views.nexus_file),
]
