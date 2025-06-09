from datetime import datetime
import os
import re

import requests
from requests.auth import HTTPBasicAuth

from auth import discord, User
from util.db import database


async def process_credentials(
    riddle: dict,
    path: str,
    credentials: tuple[str, str],
    status_code: int,
) -> bool:

    alias = riddle['alias']
    user = await discord.get_user()
    credentials_data = await get_path_credentials(alias, path)
    credentials_path = credentials_data['path']
    correct_credentials = \
        (credentials_data['username'], credentials_data['password'])

    if status_code == 401:
        if correct_credentials == ('', ''):
            # Almost certainly new and unseen protected path
            credentials_path = \
                await _check_and_insert_empty_credentials(riddle, user, path)

        # User couldn't access path, so nothing more to do
        _log_received_credentials(alias, user, path, credentials_path)
        return False

    if correct_credentials == ('', ''):
        # No previously recorded credentials and no 401 received;
        # we assume thus unprotected folder to avoid frequent HTTP checks
        return True

    if credentials == ('', ''):
        if await has_unlocked_path_credentials(alias, user, credentials_path):
            # No credentials given but path already unlocked; good to go
            return True

    if credentials == correct_credentials or credentials_data.get('sensitive'):
        # Matching informed credentials or sensitive auth path;
        # grant access and possibly record new user data
        await _record_user_credentials(
            alias, path, credentials_path, *correct_credentials
        )
        return True

    # Possibly unseen credentials, so HTTP-investigate and perhaps record them
    if credentials_path := (
        await _check_and_record_credentials(riddle, user, path, *credentials)
    ):
        await _record_user_credentials(alias, path, credentials_path, *credentials)
        return True

    return False


async def _check_and_insert_empty_credentials(
    riddle: dict, user: User, path: str,
) -> str:

    url = f"{riddle['root_path']}{path}"
    status_code, realm_message = _send_raw_request(url)
    if status_code != 401:
        # 200 masked as 401?
        return '/'

    while True:
        credentials_path = path
        path = os.path.dirname(path)

        url = f"{riddle['root_path']}{path}"
        status_code, _realm_message = _send_raw_request(url)
        if status_code != 401:
            break
        if _realm_message != realm_message:
            break

    # Insert raw record with unknown (NULL) username/password
    query = '''
        INSERT INTO riddle_credentials (
            riddle, path, realm_message, username, password
        ) VALUES (
            :riddle, :path, :realm_message, NULL, NULL
        )
    '''
    values = {
        'riddle': riddle['alias'],
        'path': credentials_path,
        'realm_message': realm_message,
    }
    await database.execute(query, values)
    print(
        f"> \033[1m[{riddle['alias']}]\033[0m "
        f"New protected path \033[1;3m{credentials_path}\033[0m "
        f"found by \033[1m{user.name}\033[0m "
        f"({datetime.utcnow()})"
    )

    return credentials_path


async def _check_and_record_credentials(
    riddle: dict, user: User, path: str, username: str, password: str,
) -> str | None:

    url = f"{riddle['root_path']}{path}"
    if _send_authenticated_request(url, username, password) == 401:
        # Wrong user credentials (leftover, 401 masked as 200, etc)
        return None

    status_code, realm_message = _send_raw_request(url)
    if status_code != 401:
        # Credentials removed altogether?
        username = password = ''

    while True:
        credentials_path = path
        path = os.path.dirname(path)

        url = f"{riddle['root_path']}{path}"
        if _send_authenticated_request(url, username, password) == 401:
            break
        status_code, _realm_message = _send_raw_request(url)
        if status_code != 401:
            break
        if _realm_message != realm_message:
            break

    # Add username and password to previously recorded empty credentials
    query = '''
        UPDATE riddle_credentials
        SET username = :username, password = :password
        WHERE riddle = :riddle
            AND path = :path
            AND username IS NULL
            AND password IS NULL
    '''
    values = {
        'riddle': riddle['alias'],
        'path': credentials_path,
        'username': username,
        'password': password,
    }
    if not await database.execute(query, values):
        # Empty record not present, so just insert a full new one
        query = '''
            INSERT IGNORE INTO riddle_credentials (
                riddle, path, realm_message, username, password
            ) VALUES (
                :riddle, :path, :realm_message, :username, :password
            )
        '''
        values |= {'realm_message': realm_message}
        await database.execute(query, values)

    # Log finding and user who did it
    query = '''
        INSERT IGNORE INTO _found_credentials (
            riddle, path, realm_message, cred_username, cred_password,
            acc_username, unlock_time
        ) VALUES (
            :riddle, :path, :realm_message, :cred_username, :cred_password,
            :acc_username, :unlock_time
        )
    '''
    values = {
        'riddle': riddle['alias'],
        'path': credentials_path,
        'realm_message': realm_message,
        'cred_username': username,
        'cred_password': password,
        'acc_username': user.name,
        'unlock_time': datetime.utcnow(),
    }
    if await database.execute(query, values):
        print(
            f"> \033[1m[{riddle['alias']}]\033[0m "
            f"New credentials \033[1m{username}:{password}\033[0m "
            f"for path \033[1;3m{credentials_path}\033[0m "
            f"found by \033[1m{user.name}\033[0m "
            f"({datetime.utcnow()})"
        )

    return credentials_path


def _send_raw_request(url: str) -> tuple[int, str | None]:

    res = requests.get(url, timeout=10)
    if res.status_code != 401:
        # Path isn't protected at all
        return res.status_code, None

    # Get realm message from unauthenticated (401) response header
    auth_header = res.headers['WWW-Authenticate']
    try:
        return 401, re.search(r'realm="([^"]*)"', auth_header)[1]
    except IndexError:
        return 401, None


def _send_authenticated_request(url: str, username: str, password: str) -> int:

    res = requests.get(url, auth=HTTPBasicAuth(username, password), timeout=10)
    return res.status_code


async def _record_user_credentials(
    alias: str,
    path: str,
    credentials_path: str,
    username: str | None,
    password: str | None,
):
    '''
    Insert new user credentials,
    or update existing ones with missing unlock time.
    '''

    user = await discord.get_user()

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
    if not await database.execute(query, values):
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
        if not await database.execute(query, values):
            return

    _log_received_credentials(
        alias, user, path, credentials_path, username, password
    )


async def get_path_credentials(alias: str, path: str) -> dict:
    '''Get required credentials (if any) for the visited path.'''

    query = '''
        SELECT * FROM riddle_credentials
        WHERE riddle = :riddle
    '''
    all_credentials = {
        credentials['path']: credentials
        for credentials in await database.fetch_all(query, {'riddle': alias})
    }
    if not all_credentials:
        # Avoid frequent iterations in credentialless riddles
        return {'path': '/', 'username': '', 'password': ''}

    while True:
        if credentials := all_credentials.get(path):
            # Innermost credentials found
            return dict(credentials)
        if path == '/':
            break
        path = os.path.dirname(path)

    # Path isn't protected at all
    return {'path': '/', 'username': '', 'password': ''}


async def has_unlocked_path_credentials(
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


def _log_received_credentials(
    alias: str,
    user: User,
    path: str,
    credentials_path: str,
    username: str = '',
    password: str = '',
):
    '''Log received correct/wrong credentials, highlighting their path.'''
    remaining_path = path.replace(credentials_path, '')
    highlighted_path = \
        f"\033[3m{credentials_path}\033[90;3m{remaining_path}\033[0m"
    print(
        f"\033[1m[{alias}]\033[0m "
        + ((
            'Received correct credentials '
            f"\033[1m{username or '???'}:{password or '???'}\033[0m "
            f"for path \033[1m{highlighted_path}\033[0m "
        ) if (username, password) != ('', '') else (
            'Received wrong credentials '
            f"for path {highlighted_path} "
        )) +
        f"from \033[1m{user.name}\033[0m "
        f"({datetime.utcnow()})"
    )
