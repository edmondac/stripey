# -*- coding: utf-8 -*-
#!/usr/bin/python

import sys
import string
import sqlite3
import os
import re

LABELS = string.ascii_letters
MISSING = "-"
GAP = "?"


def nexus(input_files, output_file):
    """
    Read in text files, parse and output a nexus file
    """
    db = '/tmp/lg.db'
    if os.path.exists(db):
        print "Using existing db: {}".format(db)
    else:
        conn = sqlite3.connect(db)
        c = conn.cursor()
        c.execute('CREATE TABLE attestations (vu int, witness text, reading text)')

        print "Reading input files"
        for i, in_f in enumerate(input_files):
            sys.stdout.write("\r{}/{}: {}    ".format(i + 1, len(input_files), in_f))
            sys.stdout.flush()
            with open(in_f) as f:
                for line in f:
                    bits = line.split()
                    vu = bits[0]
                    for arg in bits[1:]:
                        arg = arg.decode('latin1')
                        reading = arg[-1]
                        wit = arg[:-1]
                        if len(wit) != 2:
                            # Check special cases
                            if (u'ý' in wit or
                                    '^' in wit):
                                # corrector - ignore for now...
                                continue
                            if u'ü' in wit:
                                # marginal note - ignore for now
                                continue

                            for char in u'*+\x84':
                                # Firsthand chars:
                                # * = firsthand
                                # + = text (vs. margin)
                                # \x84 is both together
                                wit = wit.replace(char, '')

                            if '_' in wit:
                                # multiple readings - just take the first one
                                if wit.endswith('_1'):
                                    wit = wit[:-2]
                                else:
                                    continue

                            elif (wit.endswith(u'\xab') or '/' in wit):
                                # more than one reading supported... treat as a gap
                                wit = wit[:2]
                                reading = GAP

                        if not re.match('[A-Z][a-z]', wit):
                            print "HELLO?", wit
                        try:
                            c.execute("""INSERT INTO attestations (vu, witness, reading)
                                        VALUES ({}, '{}', '{}')""".format(vu, wit, reading))
                        except:
                            print "HELP2", vu, len(wit), wit, wit[-1], reading
                            for x in wit:
                                print x
                            raise
        print "Committing"
        conn.commit()

    print "Getting witnesses"
    conn = sqlite3.connect(db)
    c = conn.cursor()
    witnesses = [row[0] for row in c.execute("SELECT DISTINCT witness FROM attestations")]
    vus = sorted([x[0] for x in c.execute("SELECT DISTINCT vu FROM attestations")])

    symbols = set()
    matrix = []
    print "Creating NEXUS file"
    for i, wit in enumerate(witnesses):
        sys.stdout.write("\r{}/{}: {}    ".format(i + 1, len(witnesses), wit))
        sys.stdout.flush()

        wit_map = {}
        for row in c.execute("SELECT vu, reading FROM attestations WHERE witness = '{}'".format(wit)):
            symbols.add(row[1])
            wit_map[row[0]] = row[1]

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

    with open(output_file, 'w') as fh:
        fh.write(nexus_data)

    print "NEXUS file written to {}".format(output_file)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', help='Filename(s) to get data from', nargs='+')
    parser.add_argument('output_file', help='Filename to save nexus data to')
    args = parser.parse_args()

    nexus(args.input_file,
          args.output_file)


if __name__ == "__main__":
    main()
