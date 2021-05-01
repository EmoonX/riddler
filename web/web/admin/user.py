from quart import Blueprint, request

from util.db import database

# Create app blueprint
admin_user = Blueprint('admin_user', __name__)


@admin_user.route('/admin/update-user', methods=['GET'])
async def update_user():
    '''Update user tables on DB, replacing
    old username and/or discriminator with the new one(s).'''

    # We only need to update manually the accounts table, since
    # remaining ones are updated in cascade per foreign keys pure magic).
    query = 'UPDATE accounts ' \
            'SET username = :name_new, discriminator = :disc_new ' \
            'WHERE username = :name_old AND discriminator = :disc_old '
    values = {'name_new': request.args.get('name_new'),
            'disc_new': request.args.get('disc_new'),
            'name_old': request.args.get('name_old'),
            'disc_old': request.args.get('disc_old')}
    await database.execute(query, values)

    return 'SUCCESS', 200
