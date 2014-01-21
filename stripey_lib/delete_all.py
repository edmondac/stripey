import sys
import os

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

from stripey_app.models import ManuscriptTranscription

print "Really delete everything in the stripey tables? [N/y]"
ok = raw_input()
if ok.strip().lower() == 'y':
    for v in ManuscriptTranscription.objects.all():
        print "Deleting", v.display_ref()
        v.delete()

    print "Done"
else:
    print "Aborting"
