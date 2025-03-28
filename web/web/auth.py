import os

import discord
from oauthlib.oauth2.rfc6749.errors import (
    InvalidGrantError, MismatchingStateError
)
from quart import (
    Quart, Blueprint, request, session,
    render_template, redirect, url_for,
)
from quart.sessions import SecureCookieSessionInterface
from quartcord import DiscordOAuth2Session, exceptions

from countries import country_names
from util.db import database

# Discord OAuth2 sessionz
discord: DiscordOAuth2Session

# Interface for storing Quart session cookie
session_cookie: SecureCookieSessionInterface

# For type hinting in general
User = discord.User

# Create app blueprint
auth = Blueprint('players_auth', __name__)


def discord_session_init(app: Quart):
    '''Configure and create Discord OAuth2 object.'''

    # Discord OAuth2 configs
    app.config['DISCORD_CLIENT_ID'] = os.getenv('DISCORD_CLIENT_ID')
    app.config['DISCORD_CLIENT_SECRET'] = os.getenv('DISCORD_CLIENT_SECRET')
    app.config['DISCORD_REDIRECT_URI'] = f"https://{os.getenv('DOMAIN_NAME')}/callback"
    app.config['DISCORD_BOT_TOKEN'] = os.getenv('DISCORD_TOKEN')

    # Create session object
    global discord
    discord = DiscordOAuth2Session(app)

    async def _get_user() -> User:
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
        return render_template('players/register.htm', user=user, msg=msg)

    # Get authenticated Discord user
    user = await discord.get_user()

    # If account has already been created, nothing to do here
    query = '''
        SELECT * FROM accounts
        WHERE discord_id = :discord_id OR username = :username
    '''
    values = {'discord_id': user.id, 'username': user.name}
    already_created = await database.fetch_one(query, values)
    if already_created:
        return redirect(url_for('info.info_page', page='about'))

    # Render registration page on GET
    if request.method == 'GET':
        return await r('')

    # Check if user tried to submit a phony country code
    form = await request.form
    country = country_names.get(form['country'])
    if not country:
        return await r('No bogus countries allowed...')

    # Insert value on accounts table
    query = '''
        INSERT INTO accounts (username, country)
        VALUES (:username, :country)
    '''
    values = {'username': user.name, 'country': form['country']}
    await database.execute(query, values)
    
    await _post_callback()

    # Redirect to post-registration page
    return redirect(url_for('home.homepage'))


@auth.get('/login')
async def login():
    '''Create Discord session and redirect to callback URL.'''
    scope = ['identify']
    url = request.args.get('redirect_url', '/')
    return await discord.create_session(
        scope=scope, data={'redirect_url': url}
    )


@auth.get('/callback')
async def callback():
    '''Callback for OAuth2 authentication.'''

    # Execute the callback (and treat errors)
    try:
        data = await discord.callback()
    except exceptions.AccessDenied:
        return 'Unauthorized', 401
    except MismatchingStateError:
        discord.revoke()
        return redirect('/login')

    # Search for user's account in database
    user = await discord.get_user()
    query = '''
        SELECT * FROM accounts
        WHERE username = :name
    '''
    values= {'name': user.name}
    account = await database.fetch_one(query, values)
    if not account:
        return redirect(url_for('.register'))

    await _post_callback()

    # Otherwise, redirect to post-login page
    url = data.get('redirect_url', '/')
    return redirect(url)


async def _post_callback():
    '''Procedures to be done post-callback.'''
    
    user = await discord.get_user()
    
    # This will be run only once, either on register or post-hiatus login
    query = '''
        UPDATE accounts
        SET discord_id = :discord_id
        WHERE username = :username
    '''
    values = {'discord_id': user.id, 'username': user.name}
    await database.execute(query, values)
    
    # Fallback if bot failed to pick previous name changes (e.g was down)
    query = '''
        UPDATE accounts
        SET display_name = :display_name, avatar_url = :avatar_url
        WHERE discord_id = :discord_id
    '''
    values = {
        'display_name': user.display_name,
        'avatar_url': user.avatar_url,
        'discord_id': user.id,
    }
    await database.execute(query, values)


@auth.get('/logout')
async def logout():
    '''Revoke credentials and logs user out of application.'''

    # Discord credentials are gone
    discord.revoke()

    # Get rid of session data
    if 'user' in session:
        session.pop('user')

    # Redirect to last page user was in (if any)
    url = request.args.get('redirect_url', '/')
    return redirect(url)
