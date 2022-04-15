import os

from databases import Database

# Create asynchronous database object from connection URL
host = os.getenv('MYSQL_HOST')
port = os.getenv('MYSQL_PORT')
DB_URL = f"mysql://emoon:emoon@{host}:{port}/riddler"
database = Database(DB_URL)
