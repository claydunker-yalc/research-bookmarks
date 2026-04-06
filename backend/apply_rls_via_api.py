#!/usr/bin/env python3
"""
Apply Row Level Security (RLS) migration using Supabase REST API.
"""
import sys
import os
import requests

sys.path.insert(0, os.path.dirname(__file__))

from config import SUPABASE_URL, SUPABASE_KEY

def execute_sql_via_api(sql: str) -> bool:
    """Execute SQL using Supabase REST API."""

    # Use the query endpoint
    url = f"{SUPABASE_URL}/rest/v1/rpc"

    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }

    print(f"Attempting to execute SQL via REST API...")
    print(f"URL: {url}")

    # Split SQL into individual statements
    statements = [s.strip() for s in sql.split(';') if s.strip() and not s.strip().startswith('--')]

    success_count = 0
    for i, statement in enumerate(statements):
        if not statement:
            continue

        print(f"\nExecuting statement {i+1}/{len(statements)}...")

        # Try using the query function
        response = requests.post(
            url,
            headers=headers,
            json={"query": statement}
        )

        if response.status_code in [200, 201, 204]:
            success_count += 1
            print(f"  ✓ Success")
        else:
            print(f"  ✗ Failed: {response.status_code} - {response.text}")

    return success_count == len(statements)

def main():
    """Apply the RLS migration."""

    print("=" * 60)
    print("SUPABASE RLS SECURITY FIX (API Method)")
    print("=" * 60)

    # Read the SQL file
    sql_file_path = os.path.join(os.path.dirname(__file__), '..', 'supabase_enable_rls.sql')

    try:
        with open(sql_file_path, 'r') as f:
            sql = f.read()
    except FileNotFoundError:
        print(f"\n✗ Error: Could not find SQL file at: {sql_file_path}")
        return False

    print("\nAttempting to apply RLS migration via REST API...")
    print("This may not work due to API limitations.")
    print("\n" + "=" * 60)

    success = execute_sql_via_api(sql)

    if not success:
        print("\n" + "=" * 60)
        print("API METHOD FAILED - MANUAL MIGRATION REQUIRED")
        print("=" * 60)
        print("\nSupabase's REST API doesn't support DDL statements.")
        print("You need to apply the migration manually through the dashboard.")
        print("\nSteps:")
        print("1. Go to: https://supabase.com/dashboard/project/libkdykbuhpvcnrqixko/sql/new")
        print("2. Copy the contents of 'supabase_enable_rls.sql'")
        print("3. Paste into the SQL editor")
        print("4. Click 'Run' (or press Cmd+Enter)")
        print("\nI can open the URL for you if you'd like.")
        return False

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
