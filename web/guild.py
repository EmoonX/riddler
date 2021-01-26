from flask import Blueprint, request, render_template, \
        session, redirect, url_for
from MySQLdb.cursors import DictCursor

from util import mysql

# Create app blueprint
guild = Blueprint('guild', __name__, template_folder='templates')


@guild.route('/guild/<guild>/', methods=('GET', 'POST'))
def config(guild: str):
    '''Guild configuration.'''

    def r(msg):
        '''Small helper function.'''
        return render_template('guild.htm', msg=msg, alias=guild)
    
    # Need to be corrrectly logged to access guild config
    if not 'guild' in session or session['guild'] != guild:
        return redirect(url_for('auth.login'))

    # Just render page normally on GET
    if request.method == 'GET':
        return r('')
    
    category = 'Levels'
    level_id = '001'
    filename = 'potato'

    # Insert level info on database
    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute('INSERT INTO levels VALUES (%s, %s, %s, %s)',
            (session['guild'], category, level_id, filename))
    mysql.connection.commit()

    return r('Guild info updated successfully!')
