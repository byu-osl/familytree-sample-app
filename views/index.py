from flask import Blueprint, request, redirect, render_template, session, url_for
from flask.views import MethodView

from auth import authenticated
from models.user import *
from models.person import *

import json

### Home Page ### 

index = Blueprint('index', __name__)

@index.route('/')
def show():
    if authenticated():
        userID = session['userID']
        user = User.get(userID)

        return render_template('index.html',
                               menu="home",
                               login=True,
                               user=user)

    return render_template('index.html', menu="home")
