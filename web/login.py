import os

from flask import Flask, request, render_template
from flask_mysqldb import MySQL
from MySQLdb.cursors import DictCursor
import bcrypt

# Flask app object
app = Flask(__name__)

# "Unique" and "secret" secret key
app.secret_key = 'RASPUTIN'

# Database connection details
app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT'))
app.config['MYSQL_USER'] = 'emoon'
app.config['MYSQL_PASSWORD'] = 'emoon'
app.config['MYSQL_DB'] = 'guilds'

# MySQL object
mysql = MySQL(app)


@app.route('/login/', methods=('GET', 'POST'))
def login():
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


# Run Flask application
if __name__ == '__main__':
    app.run(host='0.0.0.0')
