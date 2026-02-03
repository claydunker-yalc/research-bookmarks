"""
Migration script to create the quotes table in Supabase.
Run this once to set up the quote extraction feature.
"""

import httpx
from config import SUPABASE_URL, SUPABASE_KEY

# SQL to create the quotes table and related objects
SQL = """
-- Create quotes table
create table if not exists quotes (
  id uuid primary key default gen_random_uuid(),
  article_id uuid references articles(id) on delete cascade,
  quote_text text not null,
  embedding vector(1536),
  created_at timestamptz default now()
);

-- Index for vector similarity search
create index if not exists quotes_embedding_idx on quotes using hnsw (embedding vector_cosine_ops);

-- Index for article lookups
create index if not exists quotes_article_id_idx on quotes (article_id);
"""

# Function SQL (separate because it uses $$ which can be tricky)
FUNCTION_SQL = """
create or replace function search_quotes(query_embedding vector(1536), match_count int default 20)
returns table (
  id uuid,
  article_id uuid,
  quote_text text,
  created_at timestamptz,
  similarity float
)
language plpgsql
as $func$
begin
  return query
  select
    quotes.id,
    quotes.article_id,
    quotes.quote_text,
    quotes.created_at,
    1 - (quotes.embedding <=> query_embedding) as similarity
  from quotes
  where quotes.embedding is not null
  order by quotes.embedding <=> query_embedding
  limit match_count;
end;
$func$;
"""

def run_migration():
    """Execute the migration using Supabase's REST API."""

    # Supabase SQL execution endpoint
    # This requires using the SQL Editor API or direct postgres connection
    # The anon key typically can't execute DDL

    # Try using the postgrest-py query endpoint
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal"
    }

    print("Note: This migration requires running SQL in the Supabase Dashboard.")
    print("The anon key doesn't have DDL permissions.")
    print("\nPlease run the following SQL in your Supabase SQL Editor:\n")
    print("=" * 60)
    print(SQL)
    print(FUNCTION_SQL)
    print("=" * 60)

    return False

if __name__ == "__main__":
    run_migration()
