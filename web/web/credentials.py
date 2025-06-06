from datetime import datetime
import os

from pymysql.err import IntegrityError
import requests
from requests.auth import HTTPBasicAuth

from auth import discord, User
from util.db import database


async def process_credentials(
    riddle: dict,
    path: str,
    credentials: tuple[str, str],
    status_code: int
) -> bool:

    alias = riddle['alias']
    username, password = credentials
    user = await discord.get_user()

    def _log_received_credentials(path: str, success: bool):
        '''Log received credentials based on their correctness.'''

        if success and not username:
            # No credentials needed nor received
            return

        print(
            f"\033[1m[{alias}]\033[0m "
            + ((
                'Received correct credentials '
                f"\033[1m{username}:{password}\033[0m "
            ) if success else (
                'Received wrong credentials '
            )) +
            f"for \033[3m\033[1m{path}\033[0m "
            f"from \033[1m{user.name}\033[0m "
            f"({datetime.utcnow()})"
        )

    if status_code == 401:
        # User (almost certainly) couldn't access page, so don't even bother
        # _log_received_credentials(os.path.dirname(path), success=False)
        return False

    correct_credentials = await get_path_credentials(alias, path)
    if not correct_credentials['username'] and credentials == ('', ''):
        # No credentials found, no credentials given and no 401 received,
        # so we assume unprotected folder to avoid frequent HTTP checks
        return True

    credentials_path = correct_credentials['path']
    if credentials in [
        (correct_credentials['username'], correct_credentials['password']),
        ('', ''),
    ]:
        # Grant access if user has unlocked protected folder before
        if await has_unlocked_folder_credentials(alias, user, credentials_path):
            # Record unlock time if not present yet
            # (i.e credentials were retroactively given to player before)
            query = '''
                UPDATE user_credentials
                SET unlock_time = :unlock_time
                WHERE riddle = :riddle
                    AND username = :username
                    AND path = :path
                    AND unlock_time IS NULL
            '''
            values = {
                'riddle': alias,
                'username': user.name,
                'path': credentials_path,
                'unlock_time': datetime.utcnow(),
            }
            success = await database.execute(query, values)
            if success:
                _log_received_credentials(credentials_path, success=True)

            return True

    if correct_credentials != (None, None):
        # Possibly new/different credentials, so HTTP-double-check them
        credentials_path = None
        realm_message = None
        _path = path
        while _path != '/':
            url = f"{riddle['root_path']}{_path}"
            res = requests.get(url)
            if res.status_code != 401:
                if _path == path:
                    # Visited path isn't protected at all
                    return True
                break
            else:
                # Get realm message from unauthenticated (401) response header
                realm_message = eval(
                    res.headers['WWW-Authenticate'].partition('realm=')[-1]
                )

            res = requests.get(url, auth=HTTPBasicAuth(username, password))
            if res.status_code == 401:
                if _path == path:
                    # Wrong user credentials
                    return False
                break

            credentials_path = _path
            _path = os.path.dirname(_path)

        # Correct credentials; possibly record them
        await _record_credentials(
            alias, credentials_path, realm_message, username, password
        )

    # Create new user record
    query = '''
        INSERT IGNORE INTO user_credentials
            (riddle, username, path, unlock_time)
        VALUES (:riddle, :username, :path, :unlock_time)
    '''
    values = {
        'riddle': alias,
        'username': user.name,
        'path': credentials_path,
        'unlock_time': datetime.utcnow(),
    }
    await database.execute(query, values)
    _log_received_credentials(credentials_path, success=True)

    return True


async def _record_credentials(
    alias: str, path: str, realm_message: str, username: str, password: str
):

    user = await discord.get_user()
    query = '''
        INSERT INTO _found_credentials (
            riddle, path, realm_message, cred_username, cred_password,
            acc_username, unlock_time
        ) VALUES (
            :riddle, :path, :realm_message, :cred_username, :cred_password,
            :acc_username, :unlock_time
        )
    '''
    values = {
        'riddle': alias,
        'path': path,
        'realm_message': realm_message,
        'cred_username': username,
        'cred_password': password,
        'acc_username': user.name,
        'unlock_time': datetime.utcnow(),
    }
    try:
        await database.execute(query, values)
    except IntegrityError:
        return
    else:
        print(
            f"> \033[1m[{alias}]\033[0m "
            f"Found new credentials \033[1m{username}:{password}\033[0m "
            f"for \033[1;3m{path}\033[0m "
            f"by \033[1m{user.name}\033[0m "
            f"({datetime.utcnow()})"
        )

    # Register credentials as new ones
    query = '''
        INSERT IGNORE INTO riddle_credentials (
            riddle, path, realm_message, username, password
        ) VALUES (
            :riddle, :path, :realm_message, :username, :password
        )
    '''
    values = {
        'riddle': alias,
        'path': path,
        'realm_message': realm_message,
        'username': username,
        'password': password,
    }
    await database.execute(query, values)


async def get_path_credentials(alias: str, path: str) -> dict[str, str]:

    query = '''
        SELECT * FROM riddle_credentials
        WHERE riddle = :riddle
    '''
    values = {'riddle': alias}
    result = await database.fetch_all(query, values)
    all_credentials = {row['path']: row for row in result}

    parsed_path = path.split('/')
    while parsed_path:
        path = '/'.join(parsed_path)
        credentials = all_credentials.get(path)
        if credentials:
            # Credentials and innermost protect folder found
            return {
                'path': path,
                'username': credentials['username'],
                'password': credentials['password'],
            }
        parsed_path.pop()

    # No credentials found at all
    return {
        'path': '/',
        'username': '',
        'password': '',
    }


async def has_unlocked_folder_credentials(
    alias: str, user: User, path: str
) -> bool:
    '''Check if player has unlocked credentials for path.'''
    query = '''
        SELECT 1 FROM user_credentials
        WHERE riddle = :riddle
            AND username = :username
            AND path = :path
    '''
    values = {
        'riddle': alias,
        'username': user.name,
        'path': path,
    }
    has_player_unlocked = await database.fetch_val(query, values)
    return has_player_unlocked


async def get_all_unlocked_credentials(
    alias: str, user: User
) -> dict[str, dict]:

    query = '''
        SELECT rc.path, rc.username, rc.password
        FROM riddle_credentials rc INNER JOIN user_credentials uc
            ON rc.riddle = uc.riddle AND rc.path = uc.path
        WHERE rc.riddle = :riddle AND uc.username LIKE :username
    '''
    values = {
        'riddle': alias,
        'username': user.name if user else '%',
    }
    result = await database.fetch_all(query, values)
    credentials = {
        row['path']: {
            'username': row['username'],
            'password': row['password'],
        }
        for row in result
    }
    return credentials

