class Base:
    def __init__(self, entries):
        self.__dict__.update(**entries)

    def serialize(self):
        return self.__dict__

