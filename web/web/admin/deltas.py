from quart import Blueprint, abort
from quart_discord import requires_authorization

from admin.admin import root_auth
from util.db import database

admin_deltas = Blueprint('admin_deltas', __name__)


@admin_deltas.get('/admin/update-deltas')
@requires_authorization
async def update_deltas():
    '''AAA'''
    
    ok = await root_auth()
    if not ok:
        abort(401)

    # Reset `last_placement` fields
    # in `accounts` with current player placements
    query = '''
        DROP TABLE IF EXISTS placements;
        CREATE TEMPORARY TABLE IF NOT EXISTS placements AS (
            SELECT username, discriminator,
                ROW_NUMBER() OVER w AS idx
                FROM accounts AS acc
            WHERE global_score > 0
            WINDOW w AS (ORDER BY global_score DESC));
        
        UPDATE accounts AS acc
        SET last_placement = (
            SELECT idx FROM placements AS plc
            WHERE acc.username = plc.username
                AND acc.discriminator = plc.discriminator
        )
        WHERE global_score > 0;'''
    await database.execute(query)

    return 'SUCCESS :)', 200
