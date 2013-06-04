from django.shortcuts import render_to_response
from stripey_app.models import ManuscriptTranscription

def index(request):
    all_mss = ManuscriptTranscription.objects.all().order_by('-ms_ref')
    return render_to_response('stripey_app/index.html', {'all_mss': all_mss})

