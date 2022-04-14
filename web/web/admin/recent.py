from quart import Blueprint, abort
from quart_discord import requires_authorization

from admin.admin import root_auth
from util.db import database

admin_recent = Blueprint('admin_recent', __name__)


@admin_recent.post('/admin/update-recent')
@requires_authorization
async def update_recent():
    '''Update players' last placements and recent scores.'''

    ok = await root_auth()
    if not ok:
        abort(401)

    # Update `last_placement` fields
    # in `accounts` with current player placements
    query = '''
        DROP TABLE IF EXISTS placements;
        CREATE TEMPORARY TABLE IF NOT EXISTS placements AS (
            SELECT username, discriminator, RANK() OVER w AS idx
            FROM accounts
            WHERE global_score > 0
            WINDOW w AS (ORDER BY global_score DESC)
        );        
        UPDATE accounts AS acc
        SET last_placement = (
            SELECT idx FROM placements AS plc
            WHERE acc.username = plc.username
                AND acc.discriminator = plc.discriminator
        )
        WHERE global_score > 0;
    '''
    await database.execute(query)

    # Update them also for individual riddles in `riddle_accounts`
    query = '''
        DROP TABLE IF EXISTS placements;
        CREATE TEMPORARY TABLE IF NOT EXISTS placements AS (
            SELECT riddle, username, discriminator, RANK() OVER w AS idx
            FROM riddle_accounts
            WHERE score > 0
            WINDOW w AS (
                PARTITION BY riddle
                ORDER BY score DESC
            )
        );        
        UPDATE riddle_accounts AS racc
        SET last_placement = (
            SELECT idx FROM placements AS plc
            WHERE racc.riddle = plc.riddle
                AND racc.username = plc.username
                AND racc.discriminator = plc.discriminator
        )
        WHERE score > 0;
    '''
    await database.execute(query)

    return 'SUCCESS :)', 200
