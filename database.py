import mysql.connector.pooling
import config

dbconfig = {
    "host": config.DB_HOST,
    "user": config.DB_USER,
    "password": config.DB_PASSWORD,
    "database": config.DB_NAME
}

# Create a pool of 5-10 connections that stay open
cnxpool = mysql.connector.pooling.MySQLConnectionPool(
    pool_name="aimn_pool",
    pool_size=5,
    **dbconfig
)

def get_db_connection():
    return cnxpool.get_connection()