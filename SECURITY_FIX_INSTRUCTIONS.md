# CRITICAL SECURITY FIX: Enable Row Level Security

## The Problem
Supabase detected that your tables are publicly accessible because Row Level Security (RLS) is not enabled. This means anyone can read, write, or delete your data.

## The Solution
You need to:
1. Enable RLS on all tables
2. Ensure your backend is using the **service_role** key (not the anon key)
3. Apply RLS policies that block public access while allowing your backend to work

## Step-by-Step Instructions

### Step 1: Verify Your Supabase Key Type

**CRITICAL:** Your backend should use the `service_role` key, not the `anon` key.

1. Go to your Supabase project dashboard
2. Navigate to **Settings → API**
3. You'll see two keys:
   - **anon/public key** - Used for client-side apps with RLS (DON'T use this for your backend)
   - **service_role key** - Used for backend servers, bypasses RLS (USE THIS)

4. Check your `.env` file and make sure `SUPABASE_KEY` is set to your **service_role key**

```bash
# In your .env file, it should look like:
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxpYmt... (service_role key)
```

### Step 2: Apply the RLS Migration

1. Go to your Supabase project dashboard
2. Navigate to **SQL Editor** (in the left sidebar)
3. Click **New query**
4. Copy and paste the entire contents of `supabase_enable_rls.sql` into the editor
5. Click **Run** (or press Cmd+Enter)

You should see a success message. This will:
- Enable RLS on all 5 tables (articles, quotes, digest_history, categories, category_digest_history)
- Create policies that only allow access via service_role key
- Block all unauthorized public access

### Step 3: Verify the Fix

1. In the Supabase SQL Editor, run this verification query:

```sql
SELECT schemaname, tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
AND tablename IN ('articles', 'quotes', 'digest_history', 'categories', 'category_digest_history');
```

2. All tables should show `rowsecurity = true`

3. Check the Supabase dashboard email - the security warning should disappear within a few hours

### Step 4: Test Your Application

1. Restart your backend server:
```bash
cd backend
python main.py
```

2. Test that everything still works by:
   - Viewing articles at your frontend
   - Adding a new article
   - Running a search

If your backend is using the **service_role key** (as it should be), everything will work normally because the service role bypasses RLS.

## What Changed?

### Before:
- ❌ Tables were publicly accessible
- ❌ Anyone with your Supabase URL could read/write/delete data
- ❌ No security policies in place

### After:
- ✅ RLS enabled on all tables
- ✅ Only service_role can access data
- ✅ Public/anonymous access is blocked
- ✅ Your backend API continues to work normally

## Troubleshooting

### "My backend API isn't working after enabling RLS"

This means you're using the `anon` key instead of the `service_role` key. Fix:
1. Go to Supabase Dashboard → Settings → API
2. Copy the **service_role** key (not the anon key)
3. Update your `.env` file: `SUPABASE_KEY=<service_role_key>`
4. Restart your backend

### "I want to add user authentication later"

If you add Supabase Auth later and want multiple users:
1. Add a `user_id` column to relevant tables
2. Update the RLS policies to check `auth.uid() = user_id`
3. Use the anon key in your frontend with authenticated users

For now, the service_role approach is perfect for a single-user backend API.

## Questions?

- Supabase RLS docs: https://supabase.com/docs/guides/auth/row-level-security
- Security best practices: https://supabase.com/docs/guides/api/securing-your-api
