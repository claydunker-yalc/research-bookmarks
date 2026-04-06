-- =====================================================
-- CRITICAL SECURITY FIX: Enable Row Level Security
-- =====================================================
-- This script secures your Supabase tables by enabling RLS
-- and creating policies that prevent unauthorized access.
--
-- IMPORTANT: Your backend API will continue to work because
-- it uses the service role key which bypasses RLS.
-- =====================================================

-- Enable RLS on all tables
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE quotes ENABLE ROW LEVEL SECURITY;
ALTER TABLE digest_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE category_digest_history ENABLE ROW LEVEL SECURITY;

-- =====================================================
-- Drop existing policies if any (to make script idempotent)
-- =====================================================

DROP POLICY IF EXISTS "Service role can manage articles" ON articles;
DROP POLICY IF EXISTS "Service role can manage quotes" ON quotes;
DROP POLICY IF EXISTS "Service role can manage digest_history" ON digest_history;
DROP POLICY IF EXISTS "Service role can manage categories" ON categories;
DROP POLICY IF EXISTS "Service role can manage category_digest_history" ON category_digest_history;

-- =====================================================
-- Create policies that ONLY allow service role access
-- =====================================================
-- These policies block all anonymous/public access
-- while allowing your backend (using service key) to work normally

-- Articles table
CREATE POLICY "Service role can manage articles" ON articles
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Quotes table
CREATE POLICY "Service role can manage quotes" ON quotes
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Digest history table
CREATE POLICY "Service role can manage digest_history" ON digest_history
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Categories table
CREATE POLICY "Service role can manage categories" ON categories
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Category digest history table
CREATE POLICY "Service role can manage category_digest_history" ON category_digest_history
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- =====================================================
-- Verification query (run after applying changes)
-- =====================================================
-- Uncomment and run to verify RLS is enabled:
--
-- SELECT schemaname, tablename, rowsecurity
-- FROM pg_tables
-- WHERE schemaname = 'public'
-- AND tablename IN ('articles', 'quotes', 'digest_history', 'categories', 'category_digest_history');
