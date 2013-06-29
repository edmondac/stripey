from stripey_app.models import ManuscriptTranscription
from django.contrib import admin


class ManuscriptTranscriptionAdmin(admin.ModelAdmin):
    list_display = ('ms_ref', 'ms_name', 'tischendorf', 'ga', 'liste_id', 'status')


admin.site.register(ManuscriptTranscription, ManuscriptTranscriptionAdmin)
