import sys

# Allow util folder to be visible
sys.path.append('..')

from quart import Quart

# Quart app object
app = Quart(__name__)

from auth import auth
from guild import guild
from util.db import database

for blueprint in (auth, guild):
    # Register app blueprint to allow other modules
    app.register_blueprint(blueprint)

# "Unique" and "secret" secret key
app.secret_key = 'RASPUTIN'


@app.before_first_request
async def connect():
    '''Connect to MySQL database on app start.'''
    await database.connect()
