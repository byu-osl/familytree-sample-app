from flask import Blueprint, request, redirect, render_template, session, jsonify, url_for

from views.auth import auth, authenticated
from models.user import *
from models.person import *

import json

### Ancestor Pages ### 

ancestors = Blueprint('ancestors', __name__, template_folder='templates')

@ancestors.route('/', defaults={'personID':None})
@ancestors.route('/<personID>')
def show(personID):
    # Check if authenticiated
    if not authenticated():
        return redirect(url_for('auth.login')+'?callback='+request.path)

    session['ajax'] = False

    userID = session['userID']
    user = User.get(userID)

    # get person to display in profile
    if not personID:
        personID = userID
    person = Person.get(user=user,api_id=personID)

    # set the number of generations shown in the pedigree
    generations = 7

    return render_template('ancestors.html',login=True,
                           menu='ancestors',
                           user=user,
                           person=person,
                           startID=person.api_id,
                           ancestors='{}',
                           generations=generations)


@ancestors.route('/list/<personID>')
def list(personID):

    # Check if authenticiated
    if not authenticated():
        return redirect(url_for('auth.login')+'?callback=/ancestors/' + personID)
    
    session['ajax'] = True

    sync = False
    if 'sync' in request.args:
        sync = True

    userID = session['userID']
    user = User.get(userID)

    person = Person.get(user=user,api_id=personID,sync=sync)

    # get ancestors
    ancestors = Person.pedigree(user=user,api_id=personID, generations=6, sync=sync)

    people = {}  
    for ancestor in ancestors:
        people[ancestor.api_id] = ancestor

    return render_template('ancestor-list.html',
                           user=user,
                           person=person,
                           people=people)
