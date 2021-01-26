from flask import Blueprint, request, render_template
from MySQLdb.cursors import DictCursor
import bcrypt

from util import mysql

# Create app blueprint
login = Blueprint('login', __name__, template_folder='templates')


@login.route('/login/', methods=('GET', 'POST'))
def guild_login():
    '''Guild login system.'''

    def r(msg):
        '''Small helper function.'''
        return render_template('login.htm', msg=msg)

    # Just render page normally on GET
    if request.method == 'GET':
        return r('')

    # Check if user entered guild alias and password in form
    if not ('alias' in request.form and 'password' in request.form):
        return r('Please fill out the form!')

    # Check if alias exists in database
    alias = request.form['alias']
    cursor = mysql.connection.cursor(DictCursor)
    cursor.execute('SELECT * FROM guilds where alias = %s', (alias,))
    guild = cursor.fetchone()
    if not guild:
        return r('Guild alias doesn\'t exist in database.')

    # Check if password's hash matches stored hash
    password = request.form['password']
    match = bcrypt.checkpw(
            password.encode('utf-8'), guild['password_hash'].encode('utf-8'))
    if not match:
        return r('Wrong password.')

    # ????
    return 'HAX0R'
