create table if not exists students (id text primary key, seat text, created_at timestamptz default now());
create table if not exists alerts (id uuid primary key default gen_random_uuid(), student_id text, risk int, created_at timestamptz default now());
create table if not exists evidence (id uuid primary key default gen_random_uuid(), alert_id uuid, metadata jsonb, created_at timestamptz default now());
