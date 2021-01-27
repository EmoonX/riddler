from databases import Database

# Create asynchronous database object from connection URL
DB_URL = 'mysql://emoon:emoon@127.0.0.1:3336/guilds'
database = Database(DB_URL)
