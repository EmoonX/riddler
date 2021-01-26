from flask import Blueprint, request, render_template, \
        session, redirect, url_for
from MySQLdb.cursors import DictCursor

from util import mysql

# Create app blueprint
guild = Blueprint('guild', __name__, template_folder='templates')


@guild.route('/guild/<alias>/', methods=('GET', 'POST'))
def config(alias: str):
    '''Guild configuration.'''

    def r(msg):
        '''Small helper function.'''
        return render_template('guild.htm', msg=msg, alias=alias)
    
    # Need to be corrrectly logged to access guild config
    if not 'alias' in session or session['alias'] != alias:
        return redirect(url_for("auth.login"))

    # Just render page normally on GET
    if request.method == 'GET':
        return r('')
