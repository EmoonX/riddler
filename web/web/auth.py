import os

from quart import Quart, Blueprint, request, session, \
        render_template, redirect, url_for
from quart_discord import DiscordOAuth2Session, exceptions
from quart_discord.models.user import User
from quart.sessions import SecureCookieSessionInterface
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError

from countries import country_names
from util.db import database

# Discord OAuth2 sessionz
discord: DiscordOAuth2Session

# Interface for storing Quart session cookie
session_cookie: SecureCookieSessionInterface

# Create app blueprint
auth = Blueprint('players_auth', __name__)


def discord_session_init(app: Quart):
    '''Configure and create Discord OAuth2 object.'''
    
    # Discord OAuth2 configs
    app.config['DISCORD_CLIENT_ID'] = 803127673165053993
    app.config['DISCORD_CLIENT_SECRET'] = os.getenv('DISCORD_CLIENT_SECRET')
    app.config['DISCORD_REDIRECT_URI'] = \
            'https://riddler.emoon.dev/callback'
    app.config['DISCORD_BOT_TOKEN'] = os.getenv('DISCORD_TOKEN')

    # Create session object
    global discord
    discord = DiscordOAuth2Session(app)

    async def _get_user():
        '''Return Discord OAuth2 user object.
        If token/cookie error is thrown, make user log in again.'''
        try:
            return await discord.fetch_user()
        except InvalidGrantError:
            discord.revoke()
            return await discord.fetch_user()
    setattr(discord, 'get_user', _get_user)

    # Create session cookie
    global session_cookie
    session_cookie = \
            SecureCookieSessionInterface().get_signing_serializer(app)


@auth.route('/register', methods=['GET', 'POST'])
async def register():
    '''Register new account on database based on Discord auth.'''
    
    def r(msg):
        '''Render page with **kwargs.'''
        return render_template('players/register.htm',
                user=user, msg=msg)
    
    # Get authenticated Discord user
    user = await discord.get_user()

    # If account was already created, nothing to do here
    query = 'SELECT * FROM accounts ' \
            'WHERE username = :username AND discriminator = :disc'
    values = {'username': user.name, 'disc': user.discriminator}
    already_exists = await database.fetch_one(query, values)
    if already_exists:
        return redirect(url_for('info.about'))
    
    # Render registration page on GET
    if request.method == 'GET':
        return await r('')
    
    # Check if user tried to submit a phony country code
    form = await request.form
    country = country_names.get(form['country'])
    if not country:
        return await r('No bogus countries allowed...')
    
    # Insert value on accounts table
    query = 'INSERT INTO accounts ' \
            '(username, discriminator, country) ' \
            'VALUES (:username, :disc, :country)'
    values['country'] = form['country']
    await database.execute(query, values)

    # Redirect to post-registration page
    return redirect(url_for('info.about'))


@auth.route('/login', methods=['GET'])
async def login():
    '''Create Discord session and redirect to callback URL.'''
    scope = ['identify']
    return await discord.create_session(scope=scope)


@auth.route('/callback')
async def callback():
    '''Callback for OAuth2 authentication.'''

    # Execute the callback
    try:
        await discord.callback()
    except exceptions.AccessDenied:
        return 'Unauthorized', 401

    # If user doesn't have an account on database, do registration
    user = await discord.get_user()
    query = 'SELECT * FROM accounts ' \
            'WHERE username = :name AND discriminator = :disc'
    values= {'name': user.name, 'disc': user.discriminator}
    found = await database.fetch_one(query, values)
    if not found:
        return redirect(url_for('.register'))
    
    # Save account database info on session dict
    query = 'SELECT * FROM accounts ' \
            'WHERE username = :name AND discriminator = :disc'
    values = {'name': user.name, 'disc': user.discriminator}
    result = await database.fetch_one(query, values)
    session['country'] = result['country']

    # Otherwise, redirect to post-login page
    return redirect(url_for('players.global_list'))


@auth.route('/logout')
async def logout():
    '''Revoke credentials and logs user out of application.'''

    # Discord credentials are gone
    discord.revoke()

    # Get rid of session data
    if 'user' in session:
        session.pop('user')

    # Redirect to front page
    return redirect(url_for('players.global_list'))
