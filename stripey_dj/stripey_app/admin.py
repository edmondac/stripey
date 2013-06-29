from stripey_app.models import ManuscriptTranscription
from django.contrib import admin


class ManuscriptTranscriptionAdmin(admin.ModelAdmin):
    list_display = ('ms_ref', 'ms_name', 'tischendorf', 'ga', 'status')


admin.site.register(ManuscriptTranscription, ManuscriptTranscriptionAdmin)
