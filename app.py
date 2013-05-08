from flask import Flask, redirect, session, abort, url_for

from models.session import MongoSessionInterface

### Configuration ###

app = Flask(__name__)
app.config["SECRET_KEY"] = "=\xb0\xe9\x02\x8f\n\x9e\xde\x03\xe2\xcb\xc0\r\x00\x8d\xfe\xae\xe1\x89\xceR\xf7\x1c\x19"
app.session_interface = MongoSessionInterface()

### Handlers ###

from views.index import index
app.register_blueprint(index)

from views.auth import auth
app.register_blueprint(auth, url_prefix='/auth')

from views.ancestors import ancestors
app.register_blueprint(ancestors, url_prefix='/ancestors')

from views.profile import profile
app.register_blueprint(profile, url_prefix='/profile')

### Exceptions ###

from views.exceptions import *

@app.errorhandler(NotLoggedInException)
def not_logged_in(error):
    if 'app' in session:
        del session['app']
        if not session['ajax']:
            return redirect(url_for('auth.login'))
        else:
            return 'Forbidden',403

    return 'Database connection failed', 500

@app.errorhandler(500)
def general_error(error):
    if 'app' in session:
        del session['app']
    if not session['ajax']:
        return redirect(url_for('auth.error'))
    else:
        import traceback
        if app.debug:
            app.logger.error(traceback.format_exc())
        else:
            print traceback.format_exc()
        return '500',500

if __name__ == '__main__': 
    app.debug = True
    app.run(host='0.0.0.0')

else:

    import logging
    from logging.handlers import SMTPHandler
    from logging import Formatter
    from config import ADMINS,emailAddress,emailPassword,logFile
    from datetime import date
    
    today = date.today().strftime("%d %m %Y")
    mail_handler = SMTPHandler(('smtp.gmail.com',587),
                               emailAddress,
                               ADMINS, 'app -- %s' % today,
                               credentials=(emailAddress,emailPassword),
                               secure=())
    mail_handler.setLevel(logging.ERROR)
    mail_handler.setFormatter(Formatter('''
    Message type:       %(levelname)s
    Location:           %(pathname)s:%(lineno)d
    Module:             %(module)s
    Function:           %(funcName)s
    Time:               %(asctime)s

    Message:

    %(message)s
    '''))

    app.logger.addHandler(mail_handler)

    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(logFile,maxBytes=10000,backupCount=5)
    file_handler.setLevel(logging.WARNING)
    app.logger.addHandler(file_handler)

