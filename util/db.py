import os
import warnings

from databases import Database

# Silence usual "Warning: Duplicate entry" from INSERT INTO queries
warnings.filterwarnings('ignore', module=r"aiomysql")

# Create asynchronous database object from connection URL
host = os.getenv('MYSQL_HOST')
port = os.getenv('MYSQL_PORT')
DB_URL = f"mysql://root:root@{host}:{port}/riddler"
database = Database(DB_URL)
