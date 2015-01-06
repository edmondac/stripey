# -*- coding: utf-8 -*-
#!/usr/bin/python

import sys
import string
import MySQLdb

LABELS = string.ascii_letters
MISSING = "-"
GAP = "?"


def nexus(host, db, user, password, filename):
    """
    Connect to the mysql db and loop through what we find
    """
    db = MySQLdb.connect(host=host, user=user, passwd=password, db=db, charset='utf8')
    cur = db.cursor()

    cur.execute("SELECT id FROM ed_vus ORDER BY id")
    vus = sorted([x[0] for x in cur.fetchall()])

    cur.execute("SELECT DISTINCT(witness) FROM ed_map")
    witnesses = [x[0] for x in cur.fetchall()][:20]
    symbols = set()
    matrix = []
    print
    for i, wit in enumerate(witnesses):
        sys.stdout.write("\r{}/{}: {}    ".format(i + 1, len(witnesses), wit))
        sys.stdout.flush()

        cur.execute("SELECT vu_id, ident FROM ed_map WHERE witness = %s",
                    (wit, ))
        wit_map = {}
        for row in cur.fetchall():
            ident = row[1]
            if ident == -1:
                # Missing
                label = MISSING
            elif ident == -2:
                # No text where something else has an addition...
                label = LABELS[0]
            else:
                # General reading
                label = LABELS[ident + 1]
                symbols.add(label)

            wit_map[row[0]] = label

        stripe = []
        for vu in vus:
            stripe.append(wit_map.get(vu, GAP))
        matrix.append("{} {}".format(wit, ''.join(stripe)))

    nexus_data = """#nexus
BEGIN Taxa;
DIMENSIONS ntax={};
TAXLABELS
{}
;
END;
BEGIN Characters;
DIMENSIONS nchar={};

FORMAT
    datatype=STANDARD
    missing={}
    gap={}
    symbols="{}"
;
MATRIX
{}
;
END;
""".format(len(witnesses),
           "\n".join(witnesses),
           len(vus),
           MISSING,
           GAP,
           ' '.join(sorted(list(symbols))),
           '\n'.join(matrix))

    with open(filename, 'w') as fh:
        fh.write(nexus_data)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('-u', '--mysql-user', required=True, help='User to connect to mysql with')
    parser.add_argument('-p', '--mysql-password', required=True, help='Password to connect to mysql with')
    parser.add_argument('-s', '--mysql-host', required=True, help='Host to connect to')
    parser.add_argument('-d', '--mysql-db', required=True, help='Database to connect to')
    parser.add_argument('output_file', help='Filename to save nexus data to')
    args = parser.parse_args()

    nexus(args.mysql_host,
          args.mysql_db,
          args.mysql_user,
          args.mysql_password,
          args.output_file)


if __name__ == "__main__":
    main()
