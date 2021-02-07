import sys
import asyncio
from asyncio.events import AbstractEventLoop
from ssl import SSLError

# Allow util folder to be visible
sys.path.append('..')

from quart import Quart, request, session

# Quart app object
app = Quart(__name__)

from user.auth import discord_session_init

# Really unique secret key
app.secret_key = \
        b'l\xdew\x80"\xb5O\x8eQ\x93-\x15\xc9^\xc5\x97N\xb0l\xa5\x02\x15_\xfa'

# Create Discord OAuth2 session
discord_session_init(app)

from admin.auth import admin_auth
from admin.admin import admin
from user.auth import user_auth, session_cookie
from process import process
from levels import levels
from util.db import database

# Register app blueprints to allow other modules
for blueprint in (admin_auth, admin, user_auth, process, levels):
    app.register_blueprint(blueprint)


@app.before_first_request
async def before():
    '''Procedures to be done upon app start.'''
    # Connect to MySQL database
    await database.connect()
    
    # Define exception handler for async loop
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_exception_handler)


@app.after_request
async def cookies(response):
    '''Set session cookie to be valid accross sites (SameSite=None).'''
    value = session_cookie.dumps(dict(session))
    if 'Set-Cookie' in response.headers:
        response.headers.pop('Set-Cookie')
    response.set_cookie('session', value,
            secure=True, samesite='None')
    return response


def _exception_handler(loop: AbstractEventLoop, context: dict):
    '''Ígnore annoying ssl.SSLError useless exceptions due to HTTPS.'''
    exception = context.get('exception')
    if isinstance(exception, SSLError):
        return
    loop.default_exception_handler(context)
