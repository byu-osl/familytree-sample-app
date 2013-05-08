class NotLoggedInException(Exception):
    def __init__(self, value="No user is logged in"):
        self.value = value
    def __str__(self):
        return repr(self.value)

class NotRespondingException(Exception):
    def __init__(self, value="FamilySearch Not Responding"):
        self.value = value
    def __str__(self):
        return repr(self.value)

class DBError(Exception):
    def __init__(self, value="DB Error"):
        self.value = value
    def __str__(self):
        return repr(self.value)

class DBErrorNotUnique(Exception):
    def __init__(self, value="Entry in DB is not unique"):
        self.value = value
    def __str__(self):
        return repr(self.value)

