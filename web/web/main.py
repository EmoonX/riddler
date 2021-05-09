import sys
import asyncio
from asyncio.events import AbstractEventLoop
from ssl import SSLError
from datetime import datetime, timedelta

# Allow util folder to be visible
sys.path.append('..')
sys.path.append('../..')

from quart import Quart, session, redirect, url_for
from quart_discord import Unauthorized
from dotenv import load_dotenv

# Quart app object
app = Quart(__name__, static_folder='../static')

# Load environment variables from .env file
load_dotenv(verbose=True)

from auth import discord_session_init

# Really unique secret key
app.secret_key = \
        b'l\xdew\x80"\xb5O\x8eQ\x93-\x15\xc9^\xc5\x97N\xb0l\xa5\x02\x15_\xfa'

# Create Discord OAuth2 session
discord_session_init(app)

from auth import auth, session_cookie
from admin.admin import admin
from admin.levels import admin_levels
from admin.cheevos import admin_cheevos
from players.players import players
from players.account import account
from countries import countries
from process import process
from levels import levels
from info import info
from get import get
from util.db import database
from inject import context_processor

for blueprint in (auth, admin, admin_levels, admin_cheevos,
        players, account, countries, process, levels, info, get):
    # Register app blueprint to allow other modules
    app.register_blueprint(blueprint)

    # Define context processor for blueprint
    blueprint.context_processor(context_processor)

# Define context processor for main app
app.context_processor(context_processor)

# Set MySQL-related options to avoid connections closing
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = SQLALCHEMY_ENGINE_OPTIONS

# Disable annoying newlines on Jinja rendered HTML templates
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

# Enable browser debug messages
app.config['DEBUG'] = True


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
    '''Set session cookie to be valid accross sites (SameSite=None)
    and also to expire only after a week of inactivity.'''
    value = session_cookie.dumps(dict(session))
    dt = datetime.utcnow() + timedelta(days=7)
    if 'Set-Cookie' in response.headers:
        response.headers.pop('Set-Cookie')
    response.set_cookie('session', value,
            expires=dt, secure=True, samesite='None')
    return response


@app.errorhandler(Unauthorized)
async def redirect_unauthorized(e: Exception):
    '''Redirect user back to login if not logged on restricted pages.'''
    return redirect(url_for("players_auth.login"))


def _exception_handler(loop: AbstractEventLoop, context: dict):
    '''Ígnore annoying ssl.SSLError useless exceptions due to HTTPS.'''
    exception = context.get('exception')
    if isinstance(exception, SSLError):
        return
    loop.default_exception_handler(context)
