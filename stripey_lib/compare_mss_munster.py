#!/usr/bin/python
"""
Compare the text of two (or more) manuscripts in a Muenster mysql database
"""

import MySQLdb


def compare(host, db, user, password, table, witnesses):
    """
    Connect to the mysql db and loop through what we find
    """
    assert len(witnesses) == 2
    print "Comparison of {} in db {}".format(', '.join(witnesses), db)

    db = MySQLdb.connect(host=host, user=user, passwd=password, db=db, charset='utf8')
    cur = db.cursor()

    cur.execute("""SELECT A.vu_id, A.greek, B.greek FROM {}_ed_map A
                   INNER JOIN ed_map B
                   ON A.vu_id=B.vu_id
                   AND A.witness=%s
                   AND B.witness=%s
                   AND A.ident != B.ident""".format(table), witnesses)
    n = 0
    for row in cur.fetchall():
        if not row:
            break

        print u"VU {}: \n\t{}:\t{}\n\t{}:\t{}".format(row[0], witnesses[0], row[1], witnesses[1], row[2])
        n += 1

    print "Showing {} differences".format(n)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('witness', nargs='+', help='Witnesses to compare')
    parser.add_argument('-u', '--mysql-user', required=True, help='User to connect to mysql with')
    parser.add_argument('-p', '--mysql-password', required=True, help='Password to connect to mysql with')
    parser.add_argument('-s', '--mysql-host', required=True, help='Host to connect to')
    parser.add_argument('-d', '--mysql-db', required=True, help='Database to connect to')
    parser.add_argument('-t', '--table', required=True, help='Table name to get data from')

    args = parser.parse_args()

    compare(args.mysql_host,
            args.mysql_db,
            args.mysql_user,
            args.mysql_password,
            args.table,
            args.witness)
