"""
Load the index of mss from the IGNTP
"""

import xml.etree.ElementTree as ET
import urllib2
import os
import re

IGNTP_INDEX = "http://arts-itsee.bham.ac.uk/itseeweb/igntp/transcriptions.htm"
IGNTP_CACHE = '.igntp.cache'

#re_entry = re.compile('<td><font[^>]+>([^>]+)</td><td><font[^>]+><I>John</i></td><td><font face=Gentium color=black size="3"><a target="principal" href="http://epapers.bham.ac.uk/827/">Raw XML</a></td><td><font face=Gentium color=black size="3"><a target="_blank" href="http://www.iohannes.com/XML/P2.xml">IGNTPtranscripts</td>')
re_table = re.compile('<table.*?</table>')

def get_index_data():
    if not os.path.exists(IGNTP_CACHE):
        data = urllib2.urlopen(IGNTP_INDEX).read()
        tables = re_table.findall(data)
        with open(IGNTP_CACHE, 'w') as cache:
            cache.write("<xml>%s</xml>" % ('\n'.join(tables)))

get_index_data()
tree = ET.parse(IGNTP_CACHE)
root = tree.getroot()

# TODO - finish this!
