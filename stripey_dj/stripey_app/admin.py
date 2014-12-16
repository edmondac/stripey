from stripey_app.models import ManuscriptTranscription, Book
from django.contrib import admin


class ManuscriptTranscriptionAdmin(admin.ModelAdmin):
    list_display = ('ms_ref', 'ms_name', 'tischendorf', 'ga', 'liste_id')

class BookAdmin(admin.ModelAdmin):
    list_display = ('name', 'num')


admin.site.register(ManuscriptTranscription, ManuscriptTranscriptionAdmin)
admin.site.register(Book, BookAdmin)
