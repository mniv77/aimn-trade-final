"""
=========================================================
AATA Common Database Module
=========================================================

Shared database connection for all Builders.

Every Builder should import get_connection()
instead of creating its own connection.

=========================================================
"""

import mysql.connector
from builder_config import *


def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )