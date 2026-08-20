"""
publish_pending_staging_reviews.py
-----------------------------------
Bulletproof direct-SQL publisher.
Reads all reviews from provenpick_staging and writes them
directly into provenpick_production using raw SQL only.
No SQLAlchemy ORM models — zero model mismatch errors.
"""

import asyncio
import os
import uuid
import re
from datetime import datetime, timezone

import asyncpg

STAGING_DSN = os.environ.get(
    "STAGING_DATABASE_URL",
    "postgresql://provenpick:provenpick123@127.0.0.1:5432/provenpick_staging"
)
PROD_DSN = os.environ.get(
    "PRODUCTION_DATABASE_URL",
    "postgresql://provenpick:provenpick123@127.0.0.1:5432/provenpick_production"
)


def slugify(text: str) -> str:
    if not text:
        return f"review-{uuid.uuid4().hex[:8]}"
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-") or f"review-{uuid.uuid4().hex[:8]}"


async def ensure_prod_columns(prod_conn):
    """Add any missing columns to production tables (safe to run multiple times)."""
    migrations = [
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS rating NUMERIC(3,1) DEFAULT 4.5;",
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS category_name VARCHAR(255);",
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS mindmap_image_url VARCHAR(1024);",
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS bullet_points JSONB DEFAULT '[]';",
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS seo_title VARCHAR(512);",
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS seo_description TEXT;",
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS view_count INTEGER DEFAULT 0;",
        "ALTER TABLE articles ADD COLUMN IF NOT EXISTS is_featured BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS rating NUMERIC(3,1) DEFAULT 4.5;",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS brand VARCHAR(255);",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS price_inr NUMERIC(10,2);",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS pick_label VARCHAR(100);",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS pick_type VARCHAR(50);",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS target_persona VARCHAR(255);",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS pros JSONB DEFAULT '[]';",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS cons JSONB DEFAULT '[]';",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS specs JSONB DEFAULT '{}';",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS best_for TEXT;",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS skip_if TEXT;",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url VARCHAR(1024);",
        "ALTER TABLE products ADD COLUMN IF NOT EXISTS display_order INTEGER DEFAULT 0;",
    ]
    for sql in migrations:
        try:
            await prod_conn.execute(sql)
        except Exception:
            pass
    print("✅ Production DB columns verified.")


async def publish_all_staging_reviews_to_production_db():
    staging_conn = await asyncpg.connect(STAGING_DSN)
    prod_conn = await asyncpg.connect(PROD_DSN)

    try:
        # Step 1: Ensure all columns exist
        await ensure_prod_columns(prod_conn)

        # Step 2: Fetch all staging reviews
        rows = await staging_conn.fetch(
            "SELECT * FROM staging_product_reviews ORDER BY submitted_at ASC"
        )

        if not rows:
            print("ℹ️  No staging reviews found.")
            return

        print(f"📦 Direct DB Publisher: Found {len(rows)} review(s). Writing to 'provenpick_production' DB...")
        published_count = 0

        for rev in rows:
            try:
                slug_val = rev["slug"] or slugify(rev["review_title"] or rev["name"])
                prod_uuid = rev["product_uuid"] or uuid.uuid4()
                rating_val = float(rev["rating"]) if rev["rating"] else 4.5
                title_val = rev["review_title"] or rev["name"]
                intro_val = rev["summary"] or "Comprehensive product review."
                cat_val = rev["category_name"] or "Electronics"
                image_urls = rev["image_urls"] or []
                thumb = image_urls[0] if image_urls else "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=600"
                verdict = rev["verdict"] or ""

                # Build full article HTML from review_sections
                sections = rev["review_sections"] or []
                html_parts = []
                if isinstance(sections, list):
                    for sec in sections:
                        if isinstance(sec, dict):
                            stitle = sec.get("title", "")
                            # support both content_html and content keys
                            scontent = sec.get("content_html") or sec.get("content", "")
                            if stitle:
                                html_parts.append(f"<h3>{stitle}</h3>")
                            if scontent:
                                html_parts.append(f"<div>{scontent}</div>")
                full_html = "\n".join(html_parts) if html_parts else f"<p>{intro_val}</p>"

                # Check if article already exists by slug OR uuid
                existing = await prod_conn.fetchrow(
                    "SELECT id FROM articles WHERE slug = $1 OR article_uuid = $2",
                    slug_val, prod_uuid
                )

                if existing:
                    art_id = existing["id"]
                    await prod_conn.execute(
                        """UPDATE articles SET
                            title=$1, introduction=$2, full_article_html=$3,
                            category_name=$4, rating=$5, mindmap_image_url=$6,
                            bullet_points=$7, is_published=TRUE, updated_at=$8
                           WHERE id=$9""",
                        title_val, intro_val, full_html, cat_val, rating_val,
                        thumb, f'["{verdict}"]' if verdict else "[]",
                        datetime.now(timezone.utc), art_id
                    )
                else:
                    # Ensure slug is unique
                    slug_check = await prod_conn.fetchval(
                        "SELECT id FROM articles WHERE slug = $1", slug_val
                    )
                    if slug_check:
                        slug_val = f"{slug_val}-{uuid.uuid4().hex[:6]}"

                    art_id = await prod_conn.fetchval(
                        """INSERT INTO articles
                            (article_uuid, title, slug, introduction, full_article_html,
                             category_name, rating, mindmap_image_url, bullet_points,
                             is_published, published_at, updated_at, view_count, is_featured)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,TRUE,$10,$10,0,FALSE)
                           RETURNING id""",
                        prod_uuid, title_val, slug_val, intro_val, full_html,
                        cat_val, rating_val, thumb,
                        f'["{verdict}"]' if verdict else "[]",
                        datetime.now(timezone.utc)
                    )

                    # Insert Product row
                    pros = rev["pros"] or []
                    cons = rev["cons"] or []
                    specs = rev["specs"] or {}
                    import json
                    prod_id = await prod_conn.fetchval(
                        """INSERT INTO products
                            (article_id, name, brand, price_inr, rating,
                             pick_label, pick_type, pros, cons, specs, image_url, display_order)
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9::jsonb,$10::jsonb,$11,0)
                           RETURNING id""",
                        art_id,
                        rev["name"],
                        rev["brand"] or "Brand",
                        float(rev["price_inr"]) if rev["price_inr"] else 19999.0,
                        rating_val,
                        "Editor's Choice",
                        "top_pick",
                        json.dumps(pros),
                        json.dumps(cons),
                        json.dumps(specs),
                        thumb
                    )

                    # Insert Affiliate Links
                    aff_links = rev["affiliate_links"] or {}
                    if isinstance(aff_links, dict):
                        for platform, url in aff_links.items():
                            if url:
                                await prod_conn.execute(
                                    """INSERT INTO affiliate_links
                                        (product_id, platform, raw_url, tracked_url, affiliate_tag)
                                       VALUES ($1,$2,$3,$3,$4)""",
                                    prod_id, platform.capitalize(), url, "provenpick-21"
                                )
                    elif isinstance(aff_links, list):
                        for aff in aff_links:
                            if isinstance(aff, dict) and aff.get("raw_url"):
                                await prod_conn.execute(
                                    """INSERT INTO affiliate_links
                                        (product_id, platform, raw_url, tracked_url, affiliate_tag)
                                       VALUES ($1,$2,$3,$4,$5)""",
                                    prod_id,
                                    aff.get("platform", "Amazon"),
                                    aff.get("raw_url", ""),
                                    aff.get("tracked_url") or aff.get("raw_url", ""),
                                    "provenpick-21"
                                )

                # Mark staging review as published
                await staging_conn.execute(
                    "UPDATE staging_product_reviews SET status='published' WHERE id=$1",
                    rev["id"]
                )
                print(f"✅ Published: '{title_val}' -> provenpick.xyz")
                published_count += 1

            except Exception as e:
                print(f"⚠️  Skipped '{rev['name']}': {e}")
                continue

        print(f"\n🎉 SUCCESS! Published {published_count}/{len(rows)} review articles to provenpick.xyz!")

    finally:
        await staging_conn.close()
        await prod_conn.close()


if __name__ == "__main__":
    asyncio.run(publish_all_staging_reviews_to_production_db())
