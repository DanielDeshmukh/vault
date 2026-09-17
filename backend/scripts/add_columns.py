import psycopg2

conn = psycopg2.connect(
    'postgresql://neondb_owner:npg_vVxtn09FaNrY@ep-bold-lab-a53tkz2z.us-east-2.aws.neon.tech/neondb?sslmode=require'
)
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
