create table if not exists users (
  id serial primary key,
  username text unique not null,
  password_hash text not null,
  role text not null check (role in ('customer','tech')),
  name text not null
);
create table if not exists vehicles (
  id serial primary key,
  user_id int not null references users(id),
  name text not null,
  kind text not null default 'ice'
);
create table if not exists service_history (
  id serial primary key,
  vehicle_id int not null references vehicles(id),
  note text not null,
  serviced_on date not null
);
create table if not exists parts (
  sku text primary key,
  name text not null,
  price_cents int not null,
  stock int not null default 0
);
create table if not exists tickets (
  id serial primary key,
  user_id int not null references users(id),
  vehicle_id int not null references vehicles(id),
  text text not null,
  status text not null,
  risk text not null,
  confidence real not null,
  escalate_reason text not null default '',
  analysis jsonb not null,
  quote jsonb not null,
  created_at timestamptz not null default now()
);
create table if not exists appointments (
  id serial primary key,
  ticket_id int not null references tickets(id),
  slot text not null,
  created_at timestamptz not null default now()
);
create table if not exists reviews (
  id serial primary key,
  ticket_id int not null references tickets(id),
  tech_id int not null references users(id),
  decision text not null,
  note text not null default '',
  created_at timestamptz not null default now()
);
create table if not exists notifications (
  id serial primary key,
  user_id int not null references users(id),
  ticket_id int references tickets(id),
  message text not null,
  created_at timestamptz not null default now()
);
create table if not exists audit_logs (
  id serial primary key,
  ts timestamptz not null default now(),
  actor text not null,
  event text not null,
  ticket_id int,
  detail text not null default ''
);

alter table tickets add column if not exists agent_request_id text;
