import os

from databases import Database

# Create asynchronous database object from connection URL
DB_URL = 'mysql://emoon:emoon@%s:%d/guilds' \
        % (os.getenv('MYSQL_HOST'), int(os.getenv('MYSQL_PORT')))
database = Database(DB_URL)
