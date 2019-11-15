class PysonicException(Exception):
    """ Something bad happened. """

    def __init__(self, message):
        Exception.__init__(self)
        self.message = message

    def __repr__(self) -> str:
        return f'PysonicError("{self.message}")'

    def __str__(self) -> str:
        return self.message
