"""Poll until the DATABASE_URL is reachable, then exit 0."""
import os, sys, time
import psycopg2

url = os.environ.get("DATABASE_URL", "")
if not url:
    sys.exit(0)

for attempt in range(30):
    try:
        psycopg2.connect(url).close()
        print("db ready")
        sys.exit(0)
    except psycopg2.OperationalError as e:
        print(f"waiting for db ({e})")
        time.sleep(2)

print("db never became ready")
sys.exit(1)
