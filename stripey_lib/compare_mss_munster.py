#!/usr/bin/python
"""
Compare the text of two (or more) manuscripts in a Muenster mysql database
"""

import MySQLdb
import itertools


def compare(host, db, user, password, table, witnesses):
    """
    Connect to the mysql db and loop through what we find
    """
    assert len(witnesses) == 2
    print "\nComparison of {} in db {}:{}".format(', '.join(witnesses), db, table)

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

    query = """SELECT A.vu_id, A.greek, B.greek, A.ident, B.ident FROM {}_ed_map A
               INNER JOIN {}_ed_map B
               ON A.vu_id=B.vu_id
               AND A.witness=%s
               AND B.witness=%s
               AND A.ident != B.ident""".format(table, table)
    cur.execute(query, witnesses)
    n = 0
    w1_missing = 0
    w2_missing = 0
    for row in cur.fetchall():
        if not row:
            break

        if row[1] is None:
            w1_missing += 1
            continue
        if row[2] is None:
            w2_missing += 1
            continue

        print u"VU {} ({}): \n\t{}:\t{} ({})\n\t{}:\t{} ({})".format(row[0], vu_mapping[row[0]], witnesses[0], row[1], row[3], witnesses[1], row[2], row[4])
        n += 1

    print "***\n> Showing {} differences between {} and {}".format(n, witnesses[0], witnesses[1])
    if w1_missing:
        print " > {} is missing in {} places of difference".format(witnesses[0], w1_missing)
    if w2_missing:
        print " > {} is missing in {} places of difference".format(witnesses[1], w2_missing)

    return n

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

    diffs = []
    for pair in itertools.combinations(args.witness, 2):
        diffs.append(compare(args.mysql_host,
                             args.mysql_db,
                             args.mysql_user,
                             args.mysql_password,
                             args.mysql_table,
                             [x.replace(',', '') for x in pair]))
    print "Summary of differences of pairs: " + ', '.join(str(x) for x in diffs)
    print "  > average pairwise difference: ", sum(diffs)/len(diffs)*1.0
    print "  > min|max pairwise difference: ", min(diffs), max(diffs)
