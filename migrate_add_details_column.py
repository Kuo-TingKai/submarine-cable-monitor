import sqlite3

DB_PATH = 'network_monitor.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 检查details字段是否已存在
cursor.execute("PRAGMA table_info(alerts);")
columns = [row[1] for row in cursor.fetchall()]

if 'details' not in columns:
    print("Adding 'details' column to alerts table...")
    cursor.execute("ALTER TABLE alerts ADD COLUMN details TEXT;")
    conn.commit()
    print("Column 'details' added successfully.")
else:
    print("Column 'details' already exists. No action needed.")

conn.close() 