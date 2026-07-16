create extension if not exists pgcrypto;

create table if not exists exam_sessions (
    id uuid primary key default gen_random_uuid(),
    session_id text unique not null,
    exam_id text not null,
    exam_name text,
    subject text,
    starts_at timestamptz default now(),
    ends_at timestamptz,
    status text default 'active',
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists camera_streams (
    id uuid primary key default gen_random_uuid(),
    camera_id text unique not null,
    session_id text references exam_sessions(session_id) on delete set null,
    rtsp_url text,
    location text,
    resolution jsonb default '[1280,720]'::jsonb,
    fps int default 30,
    status text default 'offline',
    connected_peers int default 0,
    students_tracked int default 0,
    last_frame_time timestamptz,
    health_score numeric default 1.0,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists students (
    id uuid primary key default gen_random_uuid(),
    student_id text unique not null,
    session_id text references exam_sessions(session_id) on delete cascade,
    name text,
    roll_number text,
    email text,
    seat text,
    seat_x numeric,
    seat_y numeric,
    camera_id text references camera_streams(camera_id) on delete set null,
    tracking_id int,
    identity_embedding_ref text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create table if not exists risk_scores (
    id uuid primary key default gen_random_uuid(),
    student_id text references students(student_id) on delete cascade,
    session_id text references exam_sessions(session_id) on delete cascade,
    camera_id text references camera_streams(camera_id) on delete set null,
    tracking_id int,
    risk_score numeric not null,
    risk_level text not null,
    components jsonb default '{}'::jsonb,
    behaviors jsonb default '[]'::jsonb,
    created_at timestamptz default now()
);

create table if not exists alerts (
    id uuid primary key default gen_random_uuid(),
    alert_id text unique not null,
    student_id text references students(student_id) on delete cascade,
    session_id text references exam_sessions(session_id) on delete cascade,
    camera_id text references camera_streams(camera_id) on delete set null,
    tracking_id int,
    alert_type text not null,
    severity text not null,
    risk_score numeric not null,
    behaviors jsonb default '[]'::jsonb,
    reason text,
    gemini_explanation text,
    recommendation text,
    evidence_captured boolean default false,
    created_at timestamptz default now()
);

create table if not exists evidence (
    id uuid primary key default gen_random_uuid(),
    evidence_id text unique not null,
    alert_id text references alerts(alert_id) on delete cascade,
    student_id text references students(student_id) on delete cascade,
    session_id text references exam_sessions(session_id) on delete cascade,
    camera_id text references camera_streams(camera_id) on delete set null,
    tracking_id int,
    event text not null,
    original_frame_path text,
    annotated_frame_path text,
    clip_manifest_path text,
    metadata_path text,
    confidence numeric,
    risk_score numeric,
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz default now()
);

create table if not exists behavior_history (
    id uuid primary key default gen_random_uuid(),
    student_id text references students(student_id) on delete cascade,
    session_id text references exam_sessions(session_id) on delete cascade,
    camera_id text references camera_streams(camera_id) on delete set null,
    behavior text not null,
    confidence numeric,
    duration_ms numeric,
    signals jsonb default '{}'::jsonb,
    created_at timestamptz default now()
);

create table if not exists reports (
    id uuid primary key default gen_random_uuid(),
    report_id text unique not null,
    session_id text references exam_sessions(session_id) on delete cascade,
    exam_id text,
    pdf_path text,
    summary jsonb default '{}'::jsonb,
    gemini_summary jsonb default '{}'::jsonb,
    generated_at timestamptz default now(),
    created_at timestamptz default now()
);

create index if not exists idx_students_session on students(session_id);
create index if not exists idx_alerts_session_created on alerts(session_id, created_at desc);
create index if not exists idx_alerts_student_created on alerts(student_id, created_at desc);
create index if not exists idx_risk_scores_student_created on risk_scores(student_id, created_at desc);
create index if not exists idx_evidence_student_created on evidence(student_id, created_at desc);
create index if not exists idx_behavior_student_created on behavior_history(student_id, created_at desc);
create index if not exists idx_camera_session on camera_streams(session_id);
