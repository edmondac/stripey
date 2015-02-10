"""
Look through all manuscripts to find the closest and furthest pairs...
"""
import MySQLdb
import itertools
from compare_mss_munster import compare

def compare_all(host, db, user, password, table):
    """
    Connect to the mysql db and loop through what we find
    """
    print "\nComparison of all witnesses in db {}:{}".format(db, table)

    db = MySQLdb.connect(host=host, user=user, passwd=password, db=db, charset='utf8')
    cur = db.cursor()

    #~ print "Setting up indexes..."
    #~ try:
        #~ cur.execute("CREATE INDEX vu_id_idx ON {}_ed_map (vu_id)".format(table))
    #~ except MySQLdb.OperationalError as e:
        #~ if "Duplicate key" not in str(e):
            #~ raise
    #~ try:
        #~ cur.execute("CREATE INDEX witness_idx ON {}_ed_map (witness(10))".format(table))
    #~ except MySQLdb.OperationalError as e:
        #~ if "Duplicate key" not in str(e):
            #~ raise
    #~ cur.execute("OPTIMIZE TABLE {}_ed_map".format(table))
    #~ print "Done"

    query = """SELECT COUNT(A.vu_id) FROM Ch18Att_ed_map A INNER JOIN Ch18Att_ed_map B ON A.vu_id=B.vu_id AND A.witness=01 AND B.witness=05 AND A.ident != B.ident"""
    cur.execute(query)
    for x in cur.fetchall():
        print x

    return

    query = """SELECT DISTINCT witness FROM {}_ed_map ORDER BY witness""".format(table)
    cur.execute(query)
    witnesses = list(cur.fetchall())

    pairs = list(itertools.combinations(witnesses, 2))

    print len(pairs)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--mysql-user', required=True, help='User to connect to mysql with')
    parser.add_argument('-p', '--mysql-password', required=True, help='Password to connect to mysql with')
    parser.add_argument('-s', '--mysql-host', required=True, help='Host to connect to')
    parser.add_argument('-d', '--mysql-db', required=True, help='Database to connect to')
    parser.add_argument('-t', '--mysql-table', required=True, help='Table name to get data from')

    args = parser.parse_args()

    compare_all(args.mysql_host,
                args.mysql_db,
                args.mysql_user,
                args.mysql_password,
                args.mysql_table)

