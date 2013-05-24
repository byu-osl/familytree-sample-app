from flask import Blueprint, request, redirect, render_template, session, url_for, make_response

import json
import urllib

from models.user import User
from config import key, sandbox

### Authentication via FamilyTree OAuth 2 ### 

auth = Blueprint('auth', __name__, template_folder='templates')

def authenticated():
    """ Check whether a session is authenticated """
    return 'app' in session

@auth.route('/login')
def login():
    # If authenticated, then go to callback
    if authenticated():
        callback = request.args.get('callback',default='/')
        return redirect(callback) 

    session.clear()

    # Get Discovery resource
    if sandbox:
        uri = 'https://sandbox.familysearch.org/.well-known/app-meta.json'
    else:
        uri = 'https://familysearch.org/.well-known/app-meta.json'
    try:
        result = urllib.urlopen(uri).read()
        response = json.loads(result)
    except:
        return render_template("redirect.html",callback=url_for('auth.down'))

    session['discovery'] = response
    authorize_uri = response['links']['http://oauth.net/core/2.0/endpoint/authorize']['href']

    redirect_uri = '%s://%s%s' % (request.scheme, request.host, url_for('auth.oauth'))

    authorize_uri += "?response_type=code&client_id=%s&redirect_uri=%s" % (key, redirect_uri)

    return redirect(authorize_uri)

@auth.route('/oauth')
def oauth():
    if 'error' in request.args:
        # TBD: log error_description
        # print "error"
        return render_template("redirect.html",callback=url_for('auth.down'))
    
    if not 'code' in request.args:
        # TBD: log the error
        # print "no code"
        return render_template("redirect.html",callback=url_for('auth.down'))

    code = request.args['code']

    uri = session['discovery']['links']['http://oauth.net/core/2.0/endpoint/token']['href']

    try:
        params = {
            'grant_type':'authorization_code',
            'code':code,
            'client_id':key,
            }
        data = urllib.urlencode(params)
        response = eval(urllib.urlopen(uri,data).read().replace('null', 'None'))
        access_token = response['access_token']
    except:
        return render_template("redirect.html",callback=url_for('auth.down'))

    # store session information
    session['app'] = True
    session['access_token'] = access_token
    session['ajax'] = False

    # get current user ID for session
    user = User.get_current()
    session['userID'] = user.api_id

    # TBD: callback
    callback = request.args.get('callback',default='/')
    if callback == '/':
        callback = '/ancestors/' + session['userID']

    return render_template('redirect.html',callback=callback)

@auth.route('/logout')
def logout(): 
    if not authenticated():
        return redirect('/')
    if sandbox:
        uri = 'https://sandbox.familysearch.org/.well-known/app-meta.json'
    else:
        uri = 'https://familysearch.org/.well-known/app-meta.json'
    try:
        result = urllib.urlopen(uri).read()
        response = json.loads(result)
        logout_uri = response['links']['fs-identity-v2-logout']['href']
    except:
        return redirect('/') 
    try:
        urllib.urlopen(logout_uri)
    except:
        pass

    session.clear()

    return redirect('/')

@auth.route('/down')
def down():
    return render_template('down.html')

@auth.route('/error')
def error():
    session['ajax'] = False 
    return render_template('error.html')
