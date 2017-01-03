# -*- coding: utf-8 -*-
"""
Uses XmlMss.py to parse manuscripts, then displays the results in html.
"""

preamble = """
This page shows the differences, per verse, for selected
manuscripts. Each variant (of a verse) is assigned a letter. The first
manuscript will always show 'a' for each verse that is present, and
the next variant of that verse to be found will be 'b', and so on.
"""

from .XmlMss import (Manuscript,
                    Chapter,
                    Verse)

class HTMLVerse(Verse):
    """
    Subclasses Verse and adds HTML display
    """
    def get_ident(self, hand):
        i = super(HTMLVerse, self)._get_ident_id(hand)
        if i is not None:
            ident = self.idents[i]
            text = self.texts[i]
            return '<span title="%s: %s">%s</span>' % (self.num, text, ident)
        else:
            return '&nbsp;'

class HTMLChapter(Chapter):
    """
    Subclasses Chapter and adds HTML display
    """
    verse_class = HTMLVerse


class HTMLManuscript(Manuscript):
    """
    Subclasses Manuscript and adds HTML display
    """
    chapter_class = HTMLChapter

    def __init__(self, name):
        super(HTMLManuscript, self).__init__(name)

    def stripes_trs(self, chap):
        """
        Get the table row for the specified chapter (str)
        """
        c = self.chapters.get(chap)
        if not c:
            return ""

        stripe_obj = c.get_stripes('&nbsp;')
        rows = []
        for hand in stripe_obj.hands:
            text = stripe_obj.hands[hand]
            rows.append("<tr><th>MS %s (%s)</th><td>%s</td></tr>" 
                        % (self.name, hand, text))
               
        return "".join(rows)
               

def html_compare(mss_ids, output_filename):
    with open(output_filename, 'w') as fh:
        fh.write("""<html>
<head>
 <link rel="stylesheet" type="text/css" href="style.css">
 <meta http-equiv="Content-type" content="text/html;charset=UTF-8">
</head>
<body>\n""")

        fh.write("<h1>Summary of MSS %s for John's Gospel</h1>"
                 % (mss_ids, ))
        fh.write("<p>%s</p>" % (preamble, ))
        
        mss = []
        for x in mss_ids:
            mss.append(HTMLManuscript(x))

        for i in range(1,22):
            fh.write("<br><b>John %s</b><br><table>\n" % (i, ))
            for m in mss:
                s = str(m.stripes_trs(str(i))).encode("UTF-8")
                fh.write(s)
            fh.write("</table><hr>")

        fh.write("</body></html>")
    print(("Written file %s" % (output_filename, )))

if __name__ == "__main__":
    html_compare(("07",
                  "01",
                  "02",
                  "03",
                  "04",
                  ),
                 'test.html')
