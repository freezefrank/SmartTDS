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
alter table documenten add column if not exists inhoud_tsv   tsvector;

-- 4. Indexes voor sneller zoeken
create index if not exists documenten_embedding_idx
    on documenten using ivfflat (embedding vector_cosine_ops)
    with (lists = 100);

create index if not exists documenten_markt_idx on documenten (markt);
create index if not exists documenten_merk_idx  on documenten (merk);
create index if not exists documenten_tsv_idx   on documenten using gin(inhoud_tsv);

-- 5. Vul de tsvector kolom (eenmalig voor bestaande rijen)
update documenten
set inhoud_tsv = to_tsvector('dutch',
    coalesce(inhoud, '') || ' ' ||
    coalesce(product_naam, '') || ' ' ||
    coalesce(merk, '') || ' ' ||
    coalesce(producttype, '') || ' ' ||
    coalesce(ondergrond, '')
)
where inhoud_tsv is null;

-- 6. Trigger: houdt inhoud_tsv automatisch bij na insert/update
create or replace function update_inhoud_tsv()
returns trigger as $$
begin
    new.inhoud_tsv := to_tsvector('dutch',
        coalesce(new.inhoud, '') || ' ' ||
        coalesce(new.product_naam, '') || ' ' ||
        coalesce(new.merk, '') || ' ' ||
        coalesce(new.producttype, '') || ' ' ||
        coalesce(new.ondergrond, '')
    );
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_update_inhoud_tsv on documenten;
create trigger trg_update_inhoud_tsv
    before insert or update on documenten
    for each row execute function update_inhoud_tsv();

-- 7. Hybrid zoekfunctie: vector + full-text met Reciprocal Rank Fusion (RRF)
create or replace function zoek_documenten(
    query_embedding    vector(384),
    query_tekst        text    default null,  -- voor full-text zoeken
    aantal             int     default 12,
    rrf_k              int     default 60,    -- RRF constante (hoger = meer gewicht aan lage ranks)
    filter_markt       text    default null,
    filter_segment     text    default null,
    filter_merk        text    default null,
    filter_producttype text    default null,
    filter_ondergrond  text    default null
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
language plpgsql as $$
declare
    kandidaten int := aantal * 4;  -- ophalen meer kandidaten voor betere RRF fusie
begin
    return query
    with
    -- ── Vector search ──────────────────────────────────────────────────────────
    vector_hits as (
        select
            d.id,
            row_number() over (order by d.embedding <=> query_embedding) as rnk,
            1.0 - (d.embedding <=> query_embedding)                       as vscore
        from documenten d
        where
            (filter_markt       is null or d.markt       = filter_markt)
            and (filter_segment     is null or d.segment     = filter_segment)
            and (filter_merk        is null or d.merk        = filter_merk)
            and (filter_producttype is null or d.producttype ilike '%' || filter_producttype || '%')
            and (filter_ondergrond  is null or d.ondergrond  ilike '%' || filter_ondergrond  || '%')
        order by d.embedding <=> query_embedding
        limit kandidaten
    ),

    -- ── Full-text search (alleen als query_tekst meegegeven is) ────────────────
    fts_hits as (
        select
            d.id,
            row_number() over (
                order by ts_rank_cd(d.inhoud_tsv,
                    websearch_to_tsquery('dutch', query_tekst), 32) desc
            ) as rnk
        from documenten d
        where
            query_tekst is not null
            and d.inhoud_tsv @@ websearch_to_tsquery('dutch', query_tekst)
            and (filter_markt       is null or d.markt       = filter_markt)
            and (filter_segment     is null or d.segment     = filter_segment)
            and (filter_merk        is null or d.merk        = filter_merk)
            and (filter_producttype is null or d.producttype ilike '%' || filter_producttype || '%')
            and (filter_ondergrond  is null or d.ondergrond  ilike '%' || filter_ondergrond  || '%')
        limit kandidaten
    ),

    -- ── RRF fusie ──────────────────────────────────────────────────────────────
    rrf as (
        select
            coalesce(v.id, f.id)                                             as id,
            coalesce(1.0 / (rrf_k + v.rnk), 0.0)
            + coalesce(1.0 / (rrf_k + f.rnk), 0.0)                         as rrf_score,
            coalesce(v.vscore, 0.0)                                          as vscore
        from vector_hits v
        full outer join fts_hits f on v.id = f.id
    )

    -- ── Finale resultaten ──────────────────────────────────────────────────────
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
        r.rrf_score::float as similarity
    from rrf r
    join documenten d on d.id = r.id
    order by r.rrf_score desc
    limit aantal;
end;
$$;
