import sqlite3
from werkzeug.security import check_password_hash

conn = sqlite3.connect("health_vault.db")
conn.row_factory = sqlite3.Row
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", [t["name"] for t in tables])
admins = conn.execute("SELECT * FROM admins").fetchall()
print("Admins:", len(admins))
for a in admins:
    print(dict(a))
    print("admin123 check:", check_password_hash(a["password_hash"], "admin123"))
