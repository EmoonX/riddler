import sys
import asyncio
from asyncio.events import AbstractEventLoop
from ssl import SSLError

# Allow util folder to be visible
sys.path.append('..')

from quart import Quart

# Quart app object
app = Quart(__name__)

from user.auth import user_auth, discord_session_init

# Really unique secret key
app.secret_key = \
        b'l\xdew\x80"\xb5O\x8eQ\x93-\x15\xc9^\xc5\x97N\xb0l\xa5\x02\x15_\xfa'

# Create Discord OAuth2 session
discord_session_init(app)

from admin.auth import admin_auth
from admin.admin import admin
from process import process
from util.db import database

# Register app blueprints to allow other modules
for blueprint in (admin_auth, admin, user_auth, process):
    app.register_blueprint(blueprint)


@app.before_first_request
async def before():
    '''Procedures to be done upon app start.'''
    # Connect to MySQL database
    await database.connect()
    
    # Define exception handler for async loop
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_exception_handler)


def _exception_handler(loop: AbstractEventLoop, context: dict):
    '''Ígnore annoying ssl.SSLError useless exceptions due to HTTPS.'''
    exception = context.get('exception')
    if isinstance(exception, SSLError):
        return
    loop.default_exception_handler(context)
