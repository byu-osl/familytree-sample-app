from flask.sessions import SessionInterface, SessionMixin
from flask import request
from werkzeug.datastructures import CallbackDict

from config import db
from base import Base

from datetime import datetime, timedelta
import json
from uuid import uuid4

### TBD use expire in Pymongo

class Session(Base):
    def __init__(self,entries=None):
        if entries:
            Base.__init__(self, entries)
            return
        self.version = '1.0'
        self.session_id = ''
        self.values = '{}'
        self.created = datetime.now()

    @staticmethod
    def get(session_id=''):
        # lookup session
        data = db.session.find_one({'session_id':session_id})

        if not data:
            return Session.new(session_id=session_id)

        session = Session(data)
        if session.version != "1.0":
            snew = Session()
            snew._id = session._id
            snew.session_id = session.session_id
            snew.save()
            return snew

        return session

    @staticmethod
    def new(session_id=''):
        session = Session()
        session.session_id = session_id
        session.save()
        return session

    @staticmethod
    def delete(session_id=''):
        db.session.remove({'session_id':session_id})

    def save(self):
        db.session.save(self.serialize())

    def expired(self,expiration):
        now = datetime.now()
        return now > self.created + expiration

class MongoSession(CallbackDict, SessionMixin):

    def __init__(self, data=None, session_id=None):
        def on_update(self):
            self.modified = True
        CallbackDict.__init__(self, data, on_update)
        self.session_id = session_id
        self.modified = False

class MongoSessionInterface(SessionInterface):

    def generate_session_id(self):
        return str(uuid4())

    def get_mongo_expiration_time(self, app, session):
        if session.permanent:
            return app.permanent_session_lifetime
        return timedelta(days=1)

    def open_session(self, app, request):
        session_id = request.cookies.get(app.session_cookie_name)
        if not session_id:
            session_id = self.generate_session_id()
        session = Session.get(session_id=session_id)
        data = json.loads(session.values)
        mongo = MongoSession(session_id=session_id, data=data)
        if session.expired(self.get_mongo_expiration_time(app,mongo)):
            Session.delete(session_id=session_id)
            session = Session.new(session_id=session_id)
            mongo = MongoSession(session_id=session_id)
        return mongo        

    def save_session(self, app, mongo, response):
        if not mongo.modified:
            return

        domain = self.get_cookie_domain(app)
        mongo_exp = self.get_mongo_expiration_time(app, mongo)
        cookie_exp = self.get_expiration_time(app, mongo)
        session = Session.get(session_id=mongo.session_id)
        session.values = json.dumps(dict(mongo))
        session.save()
        response.set_cookie(app.session_cookie_name, session.session_id,
                            expires=cookie_exp, httponly=True,
                            domain=domain)
