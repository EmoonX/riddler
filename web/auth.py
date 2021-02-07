import os

from quart import Blueprint, Quart, session, redirect, url_for
from quart.sessions import SecureCookieSessionInterface
from quart_discord import DiscordOAuth2Session, requires_authorization

from util.db import database

# !! Only in development environment.
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = 'true'

# Create app blueprint
auth = Blueprint('auth', __name__)

# Discord OAuth2 sessionz
discord: DiscordOAuth2Session

# Interface for storing Quart session cookie
session_cookie: SecureCookieSessionInterface


def discord_session_init(app: Quart):
    '''Configure and create Discord OAuth2 object.'''
    # Discord OAuth2 configs
    app.config['DISCORD_CLIENT_ID'] = 803127673165053993
    app.config['DISCORD_CLIENT_SECRET'] = os.getenv('DISCORD_CLIENT_SECRET')
    app.config['DISCORD_REDIRECT_URI'] = \
            'https://riddler.emoon.dev/callback/'
    app.config['DISCORD_BOT_TOKEN'] = os.getenv('DISCORD_BOT_TOKEN')

    # Create session object
    global discord
    discord = DiscordOAuth2Session(app)

    # Create session cookie
    global session_cookie
    session_cookie = \
            SecureCookieSessionInterface().get_signing_serializer(app)


@auth.route('/login/', methods=['GET'])
async def login():
    '''Create Discord session and redirect to callback URL.'''
    return await discord.create_session(scope=['identify'])


@auth.route('/callback/')
async def callback():
    '''Callback for OAuth2 authentication.'''
    # Execute the callback
    await discord.callback()

    # If user doesn't have an account on database, create it
    riddle = 'cipher'
    user = await discord.fetch_user()
    query = 'SELECT * FROM accounts WHERE ' \
            'riddle = :riddle AND username = :name AND discriminator = :disc'
    values = {'riddle': riddle, 'name': user.name, 'disc': user.discriminator}
    result = await database.fetch_one(query, values)
    if not result:
        query = 'INSERT INTO accounts ' \
                '(riddle, username, discriminator, title) ' \
                'VALUES (:riddle, :name, :disc, "Player")'
        await database.execute(query, values)
        query = 'SELECT * FROM accounts WHERE ' \
            'riddle = :riddle AND username = :name AND discriminator = :disc'
        result = await database.fetch_one(query, values)
    
    # Save some important user info on session dict
    session['username'] = user.username
    session['disc'] = user.discriminator

    # Redirect to post-login page
    return redirect(url_for('.me'))


@auth.route('/me/')
@requires_authorization
async def me():
    user = await discord.fetch_user()
    token = await DiscordOAuth2Session.get_authorization_token()
    return 'Hello %s!<br>Here\'s your user info: %s' \
            % (user.name, token)


@auth.route('/logout/')
async def logout():
    '''Revokes credentials and logs user out of application.'''
    discord.revoke()
    return 'Logged out. :('
