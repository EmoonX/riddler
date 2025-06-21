import os

import discord
from oauthlib.oauth2.rfc6749.errors import (
    InvalidGrantError, MismatchingStateError
)
from pymysql.err import IntegrityError
from quart import Blueprint, Quart, redirect, render_template, request
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

    user = await discord.get_user()
    query = '''
        SELECT 1 FROM accounts
        WHERE discord_id = :discord_id
    '''
    if await database.fetch_val(query, {'discord_id': user.id}):
        # Account has already been created, nothing to do here
        return redirect('/about')

    # Render registration page on GET
    if request.method == 'GET':
        return await r('')

    # Check if user tried to submit a phony country code
    form = await request.form
    country = country_names.get(form['country'])
    if not country:
        return await r('No bogus countries allowed...')

    # Insert user data into accounts table
    query = '''
        INSERT INTO accounts (username, display_name, discord_id, country)
        VALUES (:username, :display_name, :discord_id, :country)
    '''
    values = {
        'username': user.name,
        'display_name': user.display_name,
        'discord_id': user.id,
        'country': form['country'],
    }
    try:
        await database.execute(query, values)
    except IntegrityError:
        return f"""
            Username <code>{user.name}</code> already in database.
            Please contact an admin.
        """, 409  # Conflict
    
    await _post_callback()

    # Redirect to post-registration page
    return redirect('/about')


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
        return redirect('/')
    except MismatchingStateError:
        discord.revoke()
        return redirect('/login')

    user = await discord.get_user()
    query = '''
        SELECT 1 FROM accounts
        WHERE discord_id = :discord_id
    '''
    if not await database.fetch_val(query, {'discord_id': user.id}):
        # Account not found in database, so make user sign up instead
        return redirect('/register')

    await _post_callback()

    # Redirect to post-login page
    url = data.get('redirect_url', '/')
    return redirect(url)


async def _post_callback():
    '''Post-callback procedures.'''

    # Possibly update missing/outdated account info
    user = await discord.get_user()
    query = '''
        UPDATE accounts
        SET username = :username,
            display_name = :display_name,
            avatar_url = :avatar_url
        WHERE discord_id = :discord_id
    '''
    values = {
        'username': user.name,
        'display_name': user.display_name,
        'avatar_url': user.avatar_url,
        'discord_id': user.id,
    }
    await database.execute(query, values)


@auth.get('/logout')
def logout():
    '''Revoke credentials and log user out of application.'''

    # Discord credentials are gone
    discord.revoke()

    # Always redirect to homepage (for consistency and avoiding 401s)
    return redirect('/')
