import os

from quart import (
    Quart, Blueprint, request, session,
    render_template, redirect, url_for,
)
from quart.sessions import SecureCookieSessionInterface
from quart_discord import DiscordOAuth2Session, exceptions
from oauthlib.oauth2.rfc6749.errors import (
    InvalidGrantError, MismatchingStateError
)

from countries import country_names
from webclient import bot_request
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
    app.config['DISCORD_CLIENT_ID'] = os.getenv('DISCORD_CLIENT_ID')
    app.config['DISCORD_CLIENT_SECRET'] = os.getenv('DISCORD_CLIENT_SECRET')
    app.config['DISCORD_REDIRECT_URI'] = f"https://{os.getenv('DOMAIN_NAME')}/callback"
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
        return render_template('players/register.htm', user=user, msg=msg)

    # Get authenticated Discord user
    user = await discord.get_user()

    # If account has already been created, nothing to do here
    query = '''
        SELECT * FROM accounts
        WHERE discord_id = :discord_id
    '''
    values = {'discord_id': user.id}
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
        INSERT INTO accounts (display_name, username, discord_id, country)
        VALUES (:display_name, :username, :discord_id, :country)
    '''
    values |= {
        'display_name': user.display_name,
        'username': user.name,
        'country': form['country'],
    }
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
    
    user = await discord.fetch_user()
    query = '''
        UPDATE accounts
        SET discord_id = :discord_id
        WHERE username = :name
    '''
    values = {'discord_id': user.id, 'name': user.name}
    await database.execute(query, values)
    
    print(user.avatar_url)
    
    return

    # Get pure base64 data from URL and convert it to image
    mime, data = imgdata.split(',', maxsplit=1)
    mime += ','
    data = b64decode(data)
    img = Image.open(BytesIO(data))

    if folder == 'cheevos':
        # Center and crop cheevo image 1:1
        left, top, right, bottom = (0, 0, img.width, img.height)
        if img.width > img.height:
            left = (img.width - img.height) / 2
            right = left + img.height
        elif img.height > img.width:
            top = (img.height - img.width) / 2
            bottom = top + img.width
        box = (left, top, right, bottom)
        img = img.crop(box)

        # Resize cheevo image to 200x200
        size = (300, 300)
        img = img.resize(size)

    avatars_dir = f"/static/avatars"
    if not os.path.isdir(avatars_dir):
        os.makedirs(avatars_dir)

    # Save image on riddle's thumbs folder
    path = f"{avatars_dir}/{user.id}.png"
    img.save(path)
    print(f"[{alias}] Image {filename} successfully saved.")



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
