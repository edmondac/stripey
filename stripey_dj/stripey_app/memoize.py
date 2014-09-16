import threading
import cPickle as pickle
import os
import time
import hashlib


class memoize(dict):
    """
    A memoize decorator based on:
     http://wiki.python.org/moin/PythonDecoratorLibrary#Memoize

    But with added locking - so we only calculate things once...
    """
    def __init__(self, func):
        self.func = func
        self.lock = threading.Lock()

    def __call__(self, *args):
        return self[args]

    def __missing__(self, key):
        with self.lock:
            result = self[key] = self.func(*key)
            return result


class picklify(object):
    """
    A picklify decorator that does memoization but in pickles on disk,
    rather than in memory.

    The in-memory dictionary is a map of args to pickle file.

    This also has locking, so you can only use it one at a time.
    """
    FOLDER = os.path.join(os.environ.get('HOME', 'tmp'), '.picklify')
    MAXAGE = 24 * 3600

    def __init__(self, func):
        self.func = func
        self.lock = threading.Lock()
        if not os.path.exists(self.FOLDER):
            os.mkdir(self.FOLDER)

        self.mapping = {}

    def _get_pickle_file(self, args):
        if args in self.mapping:
            return self.mapping[args]

        myhash = hashlib.sha224(str(args)).hexdigest()
        pickle_file = os.path.join(self.FOLDER, myhash)
        self.mapping[args] = pickle_file
        return pickle_file

    def __call__(self, *args):
        pickle_file = self._get_pickle_file(args)
        if os.path.exists(pickle_file):
            mtime = os.path.getmtime(self.mapping[args])
            if time.time() - mtime <= self.MAXAGE:
                # Get the pickled version
                with open(self.mapping[args], 'rb') as pf:
                    print " - unpickle <- {}".format(self.mapping[args])
                    return pickle.load(pf)

        # We're still here - so get fresh data and store it
        with self.lock:
            result = self.func(*args)
            with open(pickle_file, 'wb') as pf:
                print " - pickle -> {}".format(pickle_file)
                pickle.dump(result, pf)
            return result


if __name__ == "__main__":
    @picklify
    def test(a, b):
        return {'a': a, 'b': b}

    print test(1, 2)
    print test(3, 4)
    print test(1, 2)
    print test(3, 4)
    print test(1, 5)
    print test(3, 4)
    print test(1, 2)
