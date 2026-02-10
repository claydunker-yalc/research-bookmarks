"""
Migration script to create category management tables.
Run this SQL in Supabase SQL Editor.
"""

SQL = """
-- Categories table for managing email digest themes
CREATE TABLE IF NOT EXISTS categories (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    embedding vector(1536),  -- For semantic matching against quotes
    source VARCHAR(20) DEFAULT 'requested' CHECK (source IN ('discovered', 'requested')),
    is_active BOOLEAN DEFAULT true,
    digest_frequency VARCHAR(20) DEFAULT 'weekly' CHECK (digest_frequency IN ('weekly', 'manual')),
    min_quotes_for_digest INTEGER DEFAULT 5,
    last_digest_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for embedding similarity search
CREATE INDEX IF NOT EXISTS categories_embedding_idx ON categories
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Index for active categories lookup
CREATE INDEX IF NOT EXISTS categories_active_idx ON categories (is_active) WHERE is_active = true;

-- Track sent category digests to avoid repetition
CREATE TABLE IF NOT EXISTS category_digest_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    category_id UUID REFERENCES categories(id) ON DELETE CASCADE,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    quote_ids UUID[] NOT NULL,
    article_count INTEGER,
    subject VARCHAR(255)
);

-- Index for recent category digest lookups
CREATE INDEX IF NOT EXISTS category_digest_history_category_idx ON category_digest_history (category_id, sent_at DESC);

-- RPC function to search quotes by embedding similarity
CREATE OR REPLACE FUNCTION search_quotes(
    query_embedding vector(1536),
    match_count int DEFAULT 50,
    similarity_threshold float DEFAULT 0.5
)
RETURNS TABLE (
    id uuid,
    article_id uuid,
    quote_text text,
    embedding vector(1536),
    created_at timestamptz,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        q.id,
        q.article_id,
        q.quote_text,
        q.embedding,
        q.created_at,
        1 - (q.embedding <=> query_embedding) AS similarity
    FROM quotes q
    WHERE 1 - (q.embedding <=> query_embedding) > similarity_threshold
    ORDER BY q.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
"""

if __name__ == "__main__":
    print("Run this SQL in your Supabase SQL Editor:")
    print("=" * 60)
    print(SQL)
    print("=" * 60)
