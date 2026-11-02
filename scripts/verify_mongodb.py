"""
scripts/verify_mongodb.py
==========================
Verifies live connectivity to MongoDB Atlas cloud database.

RUN:
    python scripts/verify_mongodb.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from backend.config import settings
from backend.db.client import db_manager


def main():
    print("=" * 70)
    print("  PROJECTMIND AI — MONGODB ATLAS CONNECTIVITY CHECK")
    print("=" * 70)

    uri = getattr(settings, "mongodb_uri", None)
    db_name = getattr(settings, "mongodb_db_name", "projectmind")

    if not uri or not uri.strip():
        print("\n[!] MONGODB_URI is not set in your .env file.")
        print("\nPlease add your MongoDB Atlas connection string to .env:")
        print("  MONGODB_URI=mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority")
        print("  MONGODB_DB_NAME=projectmind\n")
        print("=" * 70)
        return

    # Mask credentials for display
    display_uri = uri
    if "@" in display_uri:
        parts = display_uri.split("@")
        prefix = parts[0].split("://")[0] + "://***:***@"
        display_uri = prefix + parts[1]

    print(f"\nTarget Database : {db_name}")
    print(f"Target URI      : {display_uri}")
    print("\nConnecting to MongoDB Atlas cluster...")

    health = db_manager.ping()

    if health.get("status") == "online":
        print("\n" + "-" * 70)
        print("  [SUCCESS] SUCCESSFULLY CONNECTED TO MONGODB ATLAS!")
        print("-" * 70)
        print(f"  • Latency      : {health.get('latency_ms')} ms")
        print(f"  • Version      : {health.get('version')}")
        print(f"  • Database     : {health.get('database')}")
        print()

        # Test write & read
        try:
            print("Testing write & read operation...")
            sessions_col = db_manager.sessions
            test_doc = {"_id": "__ping_test__", "test": True, "created_at": "now"}
            sessions_col.update_one({"_id": "__ping_test__"}, {"$set": test_doc}, upsert=True)
            read_back = sessions_col.find_one({"_id": "__ping_test__"})
            sessions_col.delete_one({"_id": "__ping_test__"})
            if read_back and read_back.get("test"):
                print("  [SUCCESS] Read/write probe verified successfully!")
        except Exception as e:
            print(f"  [!] Write test warning: {e}")

        print("=" * 70)
    else:
        print("\n" + "-" * 70)
        print("  [FAILED] COULD NOT CONNECT TO MONGODB ATLAS")
        print("-" * 70)
        print(f"  Status : {health.get('status')}")
        print(f"  Error  : {health.get('error')}")
        print("\nTroubleshooting tips:")
        print("  1. Verify your IP is whitelisted in MongoDB Atlas -> Network Access -> Add IP (0.0.0.0/0 for anywhere).")
        print("  2. Verify database username and password in MONGODB_URI.")
        print("  3. Check that your connection string begins with 'mongodb+srv://'.")
        print("=" * 70)


if __name__ == "__main__":
    main()

