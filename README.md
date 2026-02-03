# Research Article Bookmarks

A semantic search-powered research article bookmarking system.

## Setup

### 1. Supabase Database Setup

Go to your Supabase project's SQL Editor and run this SQL:

```sql
-- Enable vector extension
create extension if not exists vector;

-- Create articles table
create table articles (
  id uuid primary key default gen_random_uuid(),
  url text unique not null,
  title text,
  clean_text text,
  summary text,
  embedding vector(1536),
  domain text,
  created_at timestamptz default now()
);

-- Create index for fast vector similarity search
create index on articles using ivfflat (embedding vector_cosine_ops) with (lists = 100);

-- Create function for semantic search
create or replace function search_articles(query_embedding vector(1536), match_count int default 10)
returns table (
  id uuid,
  url text,
  title text,
  summary text,
  domain text,
  created_at timestamptz,
  similarity float
)
language plpgsql
as $$
begin
  return query
  select
    articles.id,
    articles.url,
    articles.title,
    articles.summary,
    articles.domain,
    articles.created_at,
    1 - (articles.embedding <=> query_embedding) as similarity
  from articles
  order by articles.embedding <=> query_embedding
  limit match_count;
end;
$$;
```

### 2. Install Python Dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure Environment

The `.env` file is already configured with your API keys.

### 4. Run the Backend

```bash
cd backend
uvicorn main:app --reload
```

The API will be available at http://localhost:8000

### 5. Open the Frontend

Open `frontend/index.html` in your browser, or serve it with:

```bash
cd frontend
python -m http.server 3000
```

Then visit http://localhost:3000

## API Endpoints

- `POST /articles` - Save a new article by URL
- `GET /articles` - List all saved articles
- `GET /articles/{id}` - Get a single article
- `POST /search` - Semantic search (body: `{"query": "...", "limit": 10}`)

## Usage

1. Paste an article URL and click "Save Article"
2. The system will extract content, generate a summary, and create embeddings
3. Search by concept (e.g., "machine learning in healthcare") to find relevant articles
