-- SmartTDS — Supabase setup
-- Voer dit uit in de Supabase SQL editor (Dashboard → SQL Editor)

-- 1. Zorg dat pgvector extensie actief is
create extension if not exists vector;

-- 2. Maak de documenten tabel (of voeg kolommen toe als die al bestaat)
create table if not exists documenten (
    id          bigserial primary key,
    bestandsnaam text,
    product_naam text,
    markt        text,       -- NL of BE
    segment      text,       -- DIY of PROF
    merk         text,       -- Sikkens, Flexa, Dulux, etc.
    categorie    text,       -- verf-prof, verf-diy, houtbeits, etc.
    producttype  text,       -- muurverf, grondverf, lak, etc.
    toepassing   text,       -- binnen, buiten, binnen+buiten
    ondergrond   text,       -- hout, metaal, beton, etc.
    basis        text,       -- watergedragen, oplosmiddel, epoxy, PU
    verfsysteem  text,       -- grondlaag, tussenlaag, eindlaag
    datum        text,       -- datum uit bestandsnaam
    inhoud       text,
    embedding    vector(384) -- all-MiniLM-L6-v2 geeft 384 dimensies
);

-- 3. Voeg nieuwe kolommen toe als de tabel al bestaat (veilig om opnieuw te draaien)
alter table documenten add column if not exists markt        text;
alter table documenten add column if not exists segment      text;
alter table documenten add column if not exists merk         text;
alter table documenten add column if not exists categorie    text;
alter table documenten add column if not exists producttype  text;
alter table documenten add column if not exists toepassing   text;
alter table documenten add column if not exists ondergrond   text;
alter table documenten add column if not exists basis        text;
alter table documenten add column if not exists verfsysteem  text;
alter table documenten add column if not exists datum        text;

-- 4. Index voor sneller zoeken
create index if not exists documenten_embedding_idx
    on documenten using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

create index if not exists documenten_markt_idx on documenten (markt);
create index if not exists documenten_merk_idx  on documenten (merk);

-- 5. Zoekfunctie met optionele metadata filters
create or replace function zoek_documenten(
    query_embedding vector(384),
    aantal          int     default 6,
    filter_markt    text    default null,
    filter_segment  text    default null,
    filter_merk     text    default null
)
returns table (
    id           bigint,
    bestandsnaam text,
    product_naam text,
    markt        text,
    segment      text,
    merk         text,
    categorie    text,
    producttype  text,
    toepassing   text,
    ondergrond   text,
    basis        text,
    inhoud       text,
    similarity   float
)
language plpgsql
as $$
begin
    return query
    select
        d.id,
        d.bestandsnaam,
        d.product_naam,
        d.markt,
        d.segment,
        d.merk,
        d.categorie,
        d.producttype,
        d.toepassing,
        d.ondergrond,
        d.basis,
        d.inhoud,
        1 - (d.embedding <=> query_embedding) as similarity
    from documenten d
    where
        (filter_markt   is null or d.markt   = filter_markt)
        and (filter_segment is null or d.segment = filter_segment)
        and (filter_merk    is null or d.merk    = filter_merk)
    order by d.embedding <=> query_embedding
    limit aantal;
end;
$$;
