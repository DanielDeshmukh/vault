import os
import psycopg2

db_url = os.environ.get("DATABASE_URL")
if not db_url:
    raise RuntimeError("DATABASE_URL not set")

conn = psycopg2.connect(db_url.replace("postgresql://", "postgresql+psycopg2://"))
cur = conn.cursor()

cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name='users'")
cols = [r[0] for r in cur.fetchall()]
print("Existing columns:", cols)

if "designation" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN designation VARCHAR(100)")
    print("Added designation column")

if "is_approved" not in cols:
    cur.execute("ALTER TABLE users ADD COLUMN is_approved BOOLEAN DEFAULT TRUE")
    print("Added is_approved column")

conn.commit()
conn.close()
print("Done")
