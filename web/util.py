from flask import Flask
from flask_mysqldb import MySQL

# MySQL object
mysql: MySQL = None


def mysql_init(app: Flask):
    '''Create an instance of the MySQL class for the app.'''
    global mysql
    mysql = MySQL(app)