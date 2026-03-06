import sqlite3


def main():
    conn = sqlite3.connect("health_vault.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    print("Tables:", cursor.fetchall())
    conn.close()


if __name__ == "__main__":
    main()
