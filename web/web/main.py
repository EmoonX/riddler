import asyncio
from asyncio.events import AbstractEventLoop
from datetime import datetime, timedelta
import sys
from ssl import SSLError

# Allow util folder to be visible
sys.path.append('..')
sys.path.append('../..')

from quart import Quart, session, request, redirect, url_for
from quartcord import Unauthorized
from dotenv import load_dotenv

# Quart app object
app = Quart(__name__, static_folder='../static')

# Load environment variables from .env file
load_dotenv(verbose=True)

from auth import discord_session_init

# Really unique secret key
app.secret_key = (
    b'l\xdew\x80"\xb5Z\x8eQ\x93-\x15'
        b'\xc9^\xc5\x97N\xb0l\xa5\x02\x15_\xfa'
)
# Create Discord OAuth2 session object
discord_session_init(app)

from admin.cheevos import admin_cheevos
from admin.levels import admin_levels
from admin.recent import admin_recent
from admin.update import admin_update
from auth import auth, session_cookie
from countries import countries
from get import get
from home import home
from info import info
from levels import levels
from players.players import players
from players.account import account
from players.profile import profile
from process import process
from inject import context_processor
from util.db import database

for blueprint in (
    admin_cheevos, admin_levels, admin_recent, admin_update,
    auth, countries, get, home, info, levels,
    players, account, profile, process,
):
    # Context processor for blueprint
    blueprint.context_processor(context_processor)
    
    # Register app blueprint to allow other modules
    app.register_blueprint(blueprint)

# Context processor for main app
app.context_processor(context_processor)

# Disable annoying newlines on Jinja-rendered HTML templates
app.jinja_env.trim_blocks = True
app.jinja_env.lstrip_blocks = True

# Enable browser debug messages
app.config['DEBUG'] = True


@app.before_request
async def before():
    '''Procedures to be done upon app start.'''
    
    # Make decorator work as @app.before_first_request instead
    app.before_request_funcs[None].remove(before)
    
    # Connect to MySQL database
    await database.connect()

    # Define exception handler for async loop
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_exception_handler)


@app.after_request
async def cookies(response):
    '''Set session cookie to be valid accross sites (SameSite=None)
    and to expire only after some (or a long) time of inactivity.'''

    value = session_cookie.dumps(dict(session))
    expire_time = datetime.utcnow() + timedelta(days=365)
    if 'Set-Cookie' in response.headers:
        response.headers.pop('Set-Cookie')
    response.set_cookie(
        'session', value,
        expires=expire_time, secure=True, samesite='None'
    )
    return response


@app.errorhandler(Unauthorized)
async def redirect_unauthorized(_e):
    '''Redirect user back to login if not logged on restricted pages.'''
    return redirect(
        url_for("players_auth.login", redirect_url=request.url)
    )


def _exception_handler(loop: AbstractEventLoop, context: dict):
    '''Ígnore annoying ssl.SSLError useless exceptions due to HTTPS.'''
    exception = context.get('exception')
    if isinstance(exception, SSLError):
        return
    loop.default_exception_handler(context)
