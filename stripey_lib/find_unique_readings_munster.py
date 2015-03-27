#!/usr/bin/python
"""
Find readings unique to two (or more) manuscripts in a Muenster mysql database
"""

import MySQLdb
import sys


def compare(host, db, user, password, table, witnesses):
    """
    Connect to the mysql db and loop through what we find
    """
    print "Looking for unique readings in {} in db {}:{}".format(', '.join(witnesses), db, table)

    db = MySQLdb.connect(host=host, user=user, passwd=password, db=db, charset='utf8')
    cur = db.cursor()

    vu_mapping = {}
    cur.execute("SELECT id, bv, ev, bw, ew FROM {}_ed_vus".format(table))
    for row in cur.fetchall():
        i, bv, ev, bw, ew = row
        ref = "{}/".format(bv)
        if bv == ev:
            if bw == ew:
                ref += str(bw)
            else:
                ref += "{}-{}".format(bw, ew)
        else:
            ref += "{}-{}/{}".format(bw, ev, ew)
        vu_mapping[i] = ref

    # Let's get all the readings for our first witness
    query = """SELECT vu_id, ident, greek FROM {}_ed_map
               WHERE witness=%s""".format(table)
    cur.execute(query, witnesses[0])
    wit1_readings = list(cur.fetchall())
    our_witnesses = set(witnesses)

    print
    for i, (vu_id, ident, greek) in enumerate(wit1_readings):
        # Find all witnesses with that reading
        query = """SELECT witness FROM {}_ed_map
                   WHERE vu_id=%s
                   AND ident=%s""".format(table)
        cur.execute(query, (vu_id, ident))
        support = set(x[0] for x in cur.fetchall())
        sys.stdout.write("\r{} of {}:\t{}   ".format(i + 1, len(wit1_readings), len(support)))
        sys.stdout.flush()

        if support == our_witnesses:
            print "\nMATCH", vu_id, vu_mapping[vu_id], greek
            print

            #~
        #~
    #~ n = 0
    #~ w1_missing = 0
    #~ w2_missing = 0
    #~ for row in cur.fetchall():
        #~ if not row:
            #~ break
#~
        #~ if row[1] is None:
            #~ w1_missing += 1
            #~ continue
        #~ if row[2] is None:
            #~ w2_missing += 1
            #~ continue
#~
        #~ print u"VU {}: \n\t{}:\t{}\n\t{}:\t{}".format(row[0], witnesses[0], row[1], witnesses[1], row[2])
        #~ n += 1
#~
    #~ print "***\n> Showing {} differences between {} and {}".format(n, witnesses[0], witnesses[1])
    #~ if w1_missing:
        #~ print " > {} is missing in {} places of difference".format(witnesses[0], w1_missing)
    #~ if w2_missing:
        #~ print " > {} is missing in {} places of difference".format(witnesses[1], w2_missing)
#~
    #~ return n

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('witness', nargs='+', help='Witnesses to compare')
    parser.add_argument('-u', '--mysql-user', required=True, help='User to connect to mysql with')
    parser.add_argument('-p', '--mysql-password', required=True, help='Password to connect to mysql with')
    parser.add_argument('-s', '--mysql-host', required=True, help='Host to connect to')
    parser.add_argument('-d', '--mysql-db', required=True, help='Database to connect to')
    parser.add_argument('-t', '--mysql-table', required=True, help='Table name to get data from')

    args = parser.parse_args()

    compare(args.mysql_host,
            args.mysql_db,
            args.mysql_user,
            args.mysql_password,
            args.mysql_table,
            [x.replace(',', '') for x in args.witness])
