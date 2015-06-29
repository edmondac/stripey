#!/usr/bin/python

import os
import sys

# Sort out the paths so we can import the django stuff
sys.path.append('../stripey_dj/')
os.environ['DJANGO_SETTINGS_MODULE'] = 'stripey_dj.settings'

import django
django.setup()

from stripey_app.models import Algorithm
from django.db import connection


def query(sql):
    cursor = connection.cursor()
    cursor.execute(sql)

    return cursor.fetchall()


def find_uncollated():
    for algo in Algorithm.objects.all():
        sql = "SELECT chapter_id, num FROM stripey_app_verse WHERE NOT EXISTS (SELECT * FROM stripey_app_stripe WHERE verse_id = stripey_app_verse.id AND algorithm_id = {});".format(algo.id)
        uncol = [x for x in query(sql) if x is not None]
        print "Algorithm {} is missing {} verses".format(algo.name, len(uncol))
        if uncol:
            print ', '.join(['\t{}:{}'.format(x[0], x[1]) for x in uncol])


if __name__ == "__main__":
    find_uncollated()
