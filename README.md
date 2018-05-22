# Overview #
Stripey is a Django application written during my PhD studies. Its purpose has been to explore the [IGNTP's XML transcriptions of John's Gospel](http://iohannes.com/transcriptions/index.html). It was mostly developed between 2012 and 2015.


# Installation #

The django_dj folder contains a Django project with a single application django_app. Installation is straightforward if you know Django:

1.  Create a python 3 virtualenv using the supplied requirements.txt. Activate it.
1.  Install Django in the virtualenv. This project was developed for 1.10.4 (which is pretty old, but newer versions may work...)
1.  Install a database. I use PostgreSQL version 9.4.5.
1.  Copy settings.py.in to settings.py, and add a secret key where it says "DEFINE ME"
1.  Create the database schema: `python manage.py migrate`
1.  To run the server in development mode, just do: `python manage.py runserver`
1.  It will tell you the URL to visit to use the application.

I'd recommend that you run Django behind nginx using uwsgi or a similar approach rather than leaving the development server running - if it's open to the Internet. You should also set up authentication - which I also used nginx for.

To populate your database, you need XML files from [http://iohannes.com/transcriptions/index.html](http://iohannes.com/transcriptions/index.html). Download some, and use `cd stripey_dj && python stripey_lib/load_all.py --help` and follow the instructions.   

Andrew Edmondson, May 2018.