from flask import Blueprint, request, render_template
from MySQLdb.cursors import DictCursor

from util import mysql

# Create app blueprint
guild = Blueprint('guild', __name__, template_folder='templates')


@guild.route('/guild/<alias>', methods=('GET', 'POST'))
def guild_config(alias: str):
    '''Guild configuration.'''

    def r(msg):
        '''Small helper function.'''
        return render_template('guild.htm', msg=msg)

    # Just render page normally on GET
    if request.method == 'GET':
        return r('')
