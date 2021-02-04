import sys
import asyncio
from asyncio.events import AbstractEventLoop
from ssl import SSLError

# Allow util folder to be visible
sys.path.append('..')

from quart import Quart

# Quart app object
app = Quart(__name__)

from admin.auth import auth
from admin.admin import admin
from process import process
from util.db import database

for blueprint in (auth, admin, process):
    # Register app blueprint to allow other modules
    app.register_blueprint(blueprint)

# "Unique" and "secret" secret key
app.secret_key = 'RASPUTIN'


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
