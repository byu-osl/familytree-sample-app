from flask import Blueprint, request, redirect, render_template, session, jsonify, url_for

from views.auth import auth, authenticated
from models.user import *
from models.person import *

import json
import urllib

### Profile Page ### 

profile = Blueprint('profile', __name__, template_folder='templates')

@profile.route('/', defaults={'personID':None})
@profile.route('/<personID>')
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

    return render_template('profile.html',login=True,
                           menu='profile',
                           user=user,
                           person=person)

@profile.route('/list/<personID>')
def list(personID):
    # Check if authenticiated
    if not authenticated():
        return redirect(url_for('auth.login')+'?callback=/profile/' + personID)

    sync = False
    if 'sync' in request.args:
        sync = True

    session['ajax'] = True  

    userID = session['userID']
    user = User.get(userID)

    person = Person.get(user=user,api_id=personID,sync=sync)
    
    # get parents
    requestIDs = []
    parents = person.getParents()
    for parent in parents:
        if parent['fatherID']:
            requestIDs.append(parent['fatherID'])
        if parent['motherID']:
            requestIDs.append(parent['motherID'])
    parentdict = {}
    people = Person.get_people(user=user,personIDs=requestIDs)
    for p in people:
        parentdict[p.getID()] = p

    families = person.getFamilies()

    # get spouses
    requestIDs = person.getSpouseIDs()
    spouses = {}
    people = Person.get_people(user=user,personIDs=requestIDs)
    for p in people:
        spouses[p.getID()] = p

    # get children
    requestIDs = []
    for family in families:
        for childID in family['children']:
            requestIDs.append(childID)
    children = {}
    people = Person.get_people(user=user,personIDs=requestIDs)
    for p in people:
        children[p.getID()] = p

    # sort children
    person.sortChildren(children)

    return render_template('profile-list.html',
                           user=user,
                           person=person,
                           parents=parents,
                           parentdict=parentdict,
                           families=families,
                           spouses=spouses,
                           children=children)
