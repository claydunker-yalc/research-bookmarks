"""
Migration script to create the digest_history table.
Run this SQL in Supabase SQL Editor to track sent digests.
"""

SQL = """
-- Track sent curator digests to avoid repetition
create table if not exists digest_history (
  id uuid primary key default gen_random_uuid(),
  sent_at timestamptz default now(),
  theme text,
  anchor_quote_id uuid references quotes(id),
  anchor_article_id uuid references articles(id),
  cluster_quote_ids uuid[]  -- All quote IDs in the cluster
);

-- Index for recent lookups
create index if not exists digest_history_sent_at_idx on digest_history (sent_at desc);
"""

if __name__ == "__main__":
    print("Run this SQL in your Supabase SQL Editor:")
    print("=" * 60)
    print(SQL)
    print("=" * 60)
