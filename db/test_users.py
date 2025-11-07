import mysql.connector

# Test database connection
config = {
    'host': 'MeirNiv.mysql.pythonanywhere-services.com',
    'user': 'MeirNiv',
    'password': 'water288zz',
    'database': 'MeirNiv$default'
}

try:
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    print(f"Found {len(users)} users in database")
    conn.close()
    print("Database connection successful!")
except Exception as e:
    print(f"Error: {e}")

# Create a new user
try:
    conn = mysql.connector.connect(**config)
    cursor = conn.cursor()

    # Insert new user
    cursor.execute("INSERT INTO users (username, email) VALUES (%s, %s)",
                   ("test_trader", "test@example.com"))
    conn.commit()
    print("Created new user: test_trader")

    # Check total users now
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    print(f"Now have {len(users)} users total")

    conn.close()
except Exception as e:
    print(f"Error creating user: {e}")