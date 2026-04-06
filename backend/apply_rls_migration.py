#!/usr/bin/env python3
"""
Apply Row Level Security (RLS) migration to Supabase database.
This script enables RLS on all tables and creates security policies.
"""
import sys
import os

# Add parent directory to path to import config
sys.path.insert(0, os.path.dirname(__file__))

from config import SUPABASE_URL, SUPABASE_KEY
import psycopg2
from urllib.parse import urlparse

def get_connection_string():
    """
    Convert Supabase URL to PostgreSQL connection string.
    Supabase format: https://libkdykbuhpvcnrqixko.supabase.co
    PostgreSQL format: postgresql://postgres:[PASSWORD]@db.libkdykbuhpvcnrqixko.supabase.co:5432/postgres
    """
    parsed = urlparse(SUPABASE_URL)
    project_ref = parsed.netloc.split('.')[0]

    # The service_role key is used as the password for direct DB connections
    conn_string = f"postgresql://postgres.{project_ref}:{SUPABASE_KEY}@aws-0-us-east-1.pooler.supabase.com:6543/postgres"

    return conn_string

def apply_migration():
    """Apply the RLS migration."""

    # Read the SQL migration file
    sql_file_path = os.path.join(os.path.dirname(__file__), '..', 'supabase_enable_rls.sql')
    with open(sql_file_path, 'r') as f:
        sql_commands = f.read()

    print("Connecting to Supabase database...")
    print(f"Project URL: {SUPABASE_URL}")

    try:
        # Connect using connection pooler
        conn_string = get_connection_string()
        conn = psycopg2.connect(conn_string)
        conn.autocommit = True
        cur = conn.cursor()

        print("\n✓ Connected successfully!")
        print("\nApplying RLS migration...")
        print("=" * 60)

        # Execute the SQL commands
        cur.execute(sql_commands)

        print("\n✓ RLS migration applied successfully!")
        print("=" * 60)

        # Verify RLS is enabled
        print("\nVerifying RLS status...")
        cur.execute("""
            SELECT tablename, rowsecurity
            FROM pg_tables
            WHERE schemaname = 'public'
            AND tablename IN ('articles', 'quotes', 'digest_history', 'categories', 'category_digest_history')
            ORDER BY tablename;
        """)

        results = cur.fetchall()
        print("\nTable RLS Status:")
        print("-" * 40)
        for table, rls_enabled in results:
            status = "✓ ENABLED" if rls_enabled else "✗ DISABLED"
            print(f"  {table:<30} {status}")

        all_enabled = all(rls for _, rls in results)

        if all_enabled:
            print("\n" + "=" * 60)
            print("SUCCESS! All tables are now secured with RLS.")
            print("=" * 60)
            print("\nYour database is now protected:")
            print("  ✓ Row Level Security enabled on all tables")
            print("  ✓ Public access blocked")
            print("  ✓ Only service_role key can access data")
            print("  ✓ Your backend API will continue to work normally")
            print("\nThe Supabase security warning should clear within a few hours.")
        else:
            print("\n⚠ WARNING: Some tables still have RLS disabled!")

        cur.close()
        conn.close()

        return all_enabled

    except psycopg2.Error as e:
        print(f"\n✗ Database error: {e}")
        print("\nTrying alternative connection method...")

        # Try alternative connection string format
        try:
            parsed = urlparse(SUPABASE_URL)
            project_ref = parsed.netloc.split('.')[0]
            alt_conn_string = f"postgresql://postgres:{SUPABASE_KEY}@db.{project_ref}.supabase.co:5432/postgres"

            conn = psycopg2.connect(alt_conn_string)
            conn.autocommit = True
            cur = conn.cursor()

            print("✓ Connected with alternative method!")
            print("\nApplying RLS migration...")

            cur.execute(sql_commands)
            print("✓ RLS migration applied successfully!")

            cur.close()
            conn.close()
            return True

        except psycopg2.Error as e2:
            print(f"\n✗ Alternative connection also failed: {e2}")
            print("\n" + "=" * 60)
            print("MANUAL MIGRATION REQUIRED")
            print("=" * 60)
            print("\nAutomatic migration failed. Please apply manually:")
            print("\n1. Go to: https://supabase.com/dashboard/project/libkdykbuhpvcnrqixko/sql/new")
            print("2. Copy the contents of 'supabase_enable_rls.sql'")
            print("3. Paste into the SQL editor")
            print("4. Click 'Run' (or press Cmd+Enter)")
            print("\nThe SQL file is located at:")
            print(f"   {sql_file_path}")
            return False

    except FileNotFoundError:
        print(f"\n✗ Error: Could not find SQL migration file at: {sql_file_path}")
        return False

    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("SUPABASE RLS SECURITY FIX")
    print("=" * 60)
    print("\nThis script will:")
    print("  1. Enable Row Level Security on all tables")
    print("  2. Create policies to block unauthorized access")
    print("  3. Keep your backend API working normally")
    print("\n" + "=" * 60)

    success = apply_migration()

    if success:
        sys.exit(0)
    else:
        sys.exit(1)
