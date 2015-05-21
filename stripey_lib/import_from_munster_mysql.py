# -*- coding: utf-8 -*-
#!/usr/bin/python

import sys
import MySQLdb


#~ class Translator(object):
    #~ def __init__(self):
        #~ # We have latin text, that corresponds to greek
        #~ #  and square brackets for supplied text (which we'll just accept and remove the brackets)
        #~ #  and full stops representing missing text, which we'll replace with spaces
        #~ #  and number refs (e.g. 18:2) representing verses, which we'll keep as is
        #~ #  and brackets representing who knows what, which we'll leave alone
        #~ #  and some odd characters that I don't understand, which we'll remove
#~
        #~ self.uni_from = u'.[]() abgdezhqiklmnxoprs~tufcyw0123456789:-ˆ¿¯,…?/'
        #~ self.uni_to = u'___() αβγδεζηθικλμνξοπρσςτυφχψω0123456789:-_______'
        #~ self.translate_table = {ord(frm): self.uni_to[i]
                                #~ for i, frm in enumerate(self.uni_from)}
#~
    #~ def __call__(self, unicode_in):
        #~ for x in unicode_in:
            #~ if x not in self.uni_from:
                #~ print x
                #~ print unicode_in
                #~ raise ValueError((x, unicode_in))
        #~ ret = unicode_in.translate(self.translate_table)
        #~ ret = ret.replace(u'_', u'')
        #~ return ret
#~ translate = Translator()


def load_witness(witness, cur, table, dialect):
    """
    Load a particular witness from the db
    """
    cur.execute("SELECT * FROM {table} WHERE {HSNR} = %s".format(**dialect), (witness, ))
    reverse = {v: k for k, v in dialect.items()}
    field_names = [reverse.get(i[0]) for i in cur.description]
    attestations = []
    while True:
        row = cur.fetchone()
        if row is None:
            break
        attestations.append(row)

    for row in attestations:
        obj = {field_names[i]: val for i, val in enumerate(row)
               if field_names[i]}
        #~ assert obj['CHBEG'] == obj['CHEND'], obj

        #~ rdg = obj['RDG'].strip()
#~
        #~ # Square brackets...
        #~ rdg = rdg.replace(u'»', u'[')
        #~ rdg = rdg.replace(u'¼', u']')
#~
        #~ if obj['RDG'] == '\x88 \xbb2\xbca\r':
            #~ print "Wierd: {}".format(obj['RDG'])
            #~ continue
        #~ if obj['SUFF'] == '*':
            #~ # Original firsthand reading (before he corrected it)
            #~ continue
#~
        #~ assert obj['SUFF'].strip() == '', obj
#~
        #~ if "/lectionary influence/" in rdg:
            #~ rdg = rdg.replace("/lectionary influence/", "")
#~
        #~ if rdg == 'DEF':
            #~ # Text deficient (lacuna, gap?)...
            #~ greek = None
            #~ ident = -1  # NOTE - this isn't the same as RNR == -1...
#~
        #~ elif rdg == 'SINE ADD':
            #~ # Addition in another witness not present here
            #~ greek = None
            #~ ident = -2
#~
        #~ else:
            #~ # Translate to unicode greek
            #~ greek = translate(unicode(rdg.lower()))
            #~ ident = None

        greek = obj['LESART'] if 'LESART' in obj else 'unavailable'
        ident = obj['VARID2']  # assumption is that this is ECM2's variant id

        # Find ident or make a nWEND one
        cur.execute(u"""SELECT id FROM {}_ed_vus WHERE BOOK=%s AND CHBEG=%s
                        AND CHEND=%s AND VBEG=%s AND VEND=%s AND WBEG=%s
                        AND WEND=%s""".format(table),
                    (obj['BOOK'], obj['CHBEG'], obj['CHEND'], obj['VBEG'],
                     obj['VEND'], obj['WBEG'], obj['WEND']))
        for row in cur.fetchall():
            vu_id = row[0]
            break
        else:
            raise ValueError("Can't find vu")

        #~ if ident is None:
            #~ cur.execute(u"SELECT ident FROM {}_ed_map WHERE vu_id=%s AND greek=%s".format(table),
                        #~ (vu_id, greek))
            #~ for row in cur.fetchall():
                #~ ident = row[0]
                #~ break
            #~ else:
                #~ cur.execute(u"SELECT MAX(ident) FROM {}_ed_map WHERE vu_id=%s".format(table),
                            #~ (vu_id, ))
                #~ row = cur.fetchone()
                #~ if row[0] is None:
                    #~ ident = 1
                #~ else:
                    #~ ident = row[0] + 1

        cur.execute(u"""INSERT INTO {}_ed_map (witness, vu_id, greek, ident)
                        VALUES (%s, %s, %s, %s);""".format(table),
                    (get_ga(witness), vu_id, greek, ident))

        #~ print witness, obj['VBEG'], obj['VEND'], obj['WBEG'], obj['WEND'], greek, ident


def get_ga(wit):
    """
    Convert a Munster witness id into a GA number
    """
    wit = int(wit)

    if 100000 < wit < 200000:
        ret = "P{}".format(int(str(wit)[2:-1]))
    elif 200000 < wit < 300000:
        ret = "0{}".format(int(str(wit)[2:-1]))
    elif 300000 < wit < 400000:
        ret = str(int(str(wit)[2:-1]))
    elif 400000 < wit < 500000:
        ret = "L{}".format(int(str(wit)[2:-1]))
    elif wit == 1:
        # Special case
        # XXX - maybe ZEUGE would be a better column than HSNR?
        ret = "A"
    else:
        raise ValueError("Can't handle {}".format(wit))

    if str(wit).endswith('1'):
        ret += 'S'
    return ret


def get_dialect(db, table):
    """
    Look at the database table and return something that translates
    the columns into a standard set.
    """
    cur = db.cursor()
    cur.execute("SELECT * FROM {}".format(table))
    field_names = [i[0] for i in cur.description]

    default = ("BOOK", "CHBEG", "CHEND", "VBEG", "VEND", "WBEG", "WEND", "VARID2", 'HSNR', 'LESART')

    dialects = [("BOOK", "CHBEG", "CHEND", "VBEG", "VEND", "WBEG", "WEND", "VARID2", 'MSNR', None),
                ("BUCH", "KAPANF", "KAPEND", "VERSANF", "VERSEND", "WORTANF", "WORTEND", "LABEZ", "HSNR", None),
                ("BUCH", "KAPANF", "KAPEND", "VERSANF", "VERSEND", "WORTANF", "WORTEND", "VARID2", "HSNR", 'LESART'),
                ("BUCH", "CHBEG", "CHEND", "VBEG", "VEND", "WBEG", "WEND", "VARID2", "HSNR", None),
                ("BUCH", "CHBEG", "CHEND", "VBEG", "VEND", "WBEG", "WEND", "VARID2", "HSNR", 'LESART'),
                ]

    class NoMatch(Exception):
        pass

    match = None
    for dialect in dialects:
        try:
            for x in dialect:
                if x is not None and x not in field_names:
                    raise NoMatch
        except NoMatch:
            continue
        else:
            match = dialect
            break

    if not match:
        raise NoMatch("Can't identify dialect")

    print "Dialect {} detected".format(dialects.index(match))

    return {default[i]: match[i] for i in range(len(default))}


def load_all(host, db, user, password, table):
    """
    Connect to the mysql db and loop through what we find
    """
    db = MySQLdb.connect(host=host, user=user, passwd=password, db=db, charset='utf8')
    cur = db.cursor()

    cur.execute("DROP TABLE IF EXISTS ed_map;")
    cur.execute("DROP TABLE IF EXISTS ed_vus;")
    cur.execute("DROP TABLE IF EXISTS {}_ed_map;".format(table))
    cur.execute("DROP TABLE IF EXISTS {}_ed_vus;".format(table))

    # Phase 1: load variant units
    cur.execute("""CREATE TABLE {}_ed_vus (
                        id INT AUTO_INCREMENT KEY,
                        BOOK INT,
                        CHBEG INT,
                        CHEND INT,
                        VBEG INT,
                        VEND INT,
                        WBEG INT,
                        WEND INT);""".format(table))

    forward_dialect = get_dialect(db, table)

    d = {'table': table}
    d.update(forward_dialect)
    cur.execute("""INSERT INTO {table}_ed_vus (BOOK, CHBEG, CHEND, VBEG, VEND, WBEG, WEND)
                       SELECT {BOOK}, {CHBEG}, {CHEND}, {VBEG}, {VEND}, {WBEG}, {WEND}
                       FROM {table}
                       GROUP BY {BOOK}, {CHBEG}, {CHEND}, {VBEG}, {VEND}, {WBEG}, {WEND};"""
                .format(**d))

    cur.execute("""CREATE TABLE {}_ed_map (
                    witness TEXT NOT NULL,
                    vu_id INT NOT NULL,
                    greek TEXT CHARACTER SET UTF8,
                    ident TEXT NOT NULL,

                    FOREIGN KEY (vu_id)
                        REFERENCES {}_ed_vus(id)
                    );""".format(table, table))

    # Phase 2: load readings
    cur.execute("SELECT DISTINCT {HSNR} FROM {table};".format(**d))

    witnesses = set()
    for row in cur.fetchall():
        witnesses.add(row[0])

    print
    for i, wit in enumerate(witnesses):
        sys.stdout.write("\r{} / {}: {}     ".format(i + 1, len(witnesses), wit))
        sys.stdout.flush()
        try:
            load_witness(wit, cur, table, d)
        except Exception as e:
            print e
            print
            raise
        else:
            db.commit()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--mysql-user', required=True, help='User to connect to mysql with')
    parser.add_argument('-p', '--mysql-password', required=True, help='Password to connect to mysql with')
    parser.add_argument('-s', '--mysql-host', required=True, help='Host to connect to')
    parser.add_argument('-d', '--mysql-db', required=True, help='Database to connect to')
    parser.add_argument('-t', '--table', required=True, help='Table name to get data from')

    args = parser.parse_args()

    load_all(args.mysql_host,
             args.mysql_db,
             args.mysql_user,
             args.mysql_password,
             args.table)
    print

if __name__ == "__main__":
    main()
