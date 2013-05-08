from flask import session

from models.person import *
from config import db
from base import Base
from familytree.api import API

import time

class User(Base):
    def __init__(self,entries=None):
        if entries:
            Base.__init__(self, entries)
            return
        self.version = "1.0"
        self.api_id = ''
        self.api_data = {}
        self.lds = False

    @staticmethod
    def get(id = ''):
        if not id:
            raise DBError

        # lookup user
        data = db.users.find_one({'api_id':id})

        # if not found then return a new instance
        if not data:
            user = User()
            user.api_id = id
            user.save()
            return user

        user = User(data)
        if user.version != "1.0":
            unew = User.copy(user)
            unew.save()
            return unew

        return user

    @staticmethod
    def copy(user):
        unew = User()
        unew._id = user._id
        unew.api_id = user.api_id
        try:
            unew.api_data = user.api_data
        except:
            pass
        return unew

    @staticmethod
    def get_current():
        # get API object
        api = API(session['access_token'])
        # get current user
        api_data = api.get_user()
        userID = api_data['personId']
        user = User.get(userID)
        # store user information
        user.api_data = api_data
        user.ldsPermission()
        # This is what we'll use when it is implemented
        # user.ldsMember()
        user.save()
        return user

    def save(self):
        db.users.save(self.serialize())

    # temporary function using the old API until the new one is fully
    # supported
    def ldsPermission(self):
        api = API(session['access_token'])
        api_data = api.get_permissions()
        if 'permissions' in api_data:
            for permission in api_data['permissions']:
                if permission['value'] == 'View LDS Information':
                    self.lds = True
                    return
        self.lds = False

    def ldsMember(self):
        if 'ldsMemberAccount' in self.api_data:
            self.lds = data['ldsMemberAccount']
        self.lds = False

    def displayName(self):
        if 'displayName' in self.api_data:
            return self.api_data['displayName']
        else:
            return ''
