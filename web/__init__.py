import sys

from quart import Quart

# Avoid "no module named" errors because of __init__.py
#sys.path.append('.')
#sys.path.append('..')

from ..util.db import database

# Quart app object
app = Quart(__name__)

from auth import auth
from guild import guild

for blueprint in (auth, guild):
    # Register app blueprint to allow other modules
    app.register_blueprint(blueprint)

# "Unique" and "secret" secret key
app.secret_key = 'RASPUTIN'


@app.before_first_request
async def connect():
    '''Connect to MySQL database on app start.'''
    await db.database.connect()


# Run Quart application
if __name__ == '__main__':
    app.run(host='0.0.0.0')
