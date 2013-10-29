import threading

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
