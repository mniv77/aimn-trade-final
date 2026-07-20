"""
=========================================================
AATA Builder Configuration
=========================================================

Shared configuration used by all Builder programs.

Any Builder that needs database access should import
this file instead of hardcoding configuration.

Example:

from builder_config import *

=========================================================
"""

# -------------------------------------------------------
# Database Configuration
# -------------------------------------------------------

DB_HOST = "MeirNiv.mysql.pythonanywhere-services.com"
DB_NAME = "MeirNiv$AATA"
DB_USER = "MeirNiv"
DB_PASSWORD = "mayyam28"      # Fill in your password
 

# -------------------------------------------------------
# Academy Configuration
# -------------------------------------------------------

CREATED_BY = "Meir Niv"

DEFAULT_PRIORITY = 5

ACADEMY_NAME = "AATA"

VERSION = "1.0"