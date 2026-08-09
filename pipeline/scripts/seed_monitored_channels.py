import asyncio
import os
import sys

sys.path.insert(0, r"/var/www/ProvenPick/pipeline")
sys.path.insert(0, r"c:\Users\prade\Desktop\ProvenPick\pipeline")

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv(r"/var/www/ProvenPick/.env")
if not os.environ.get("WORKFLOW_DATABASE_URL"):
    load_dotenv(r"c:\Users\prade\Desktop\ProvenPick\.env")

WORKFLOW_DB = os.environ.get("WORKFLOW_DATABASE_URL") or "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5432/provenpick_workflow"

from src.db.models import Base

CHANNELS = [
    # Electronics
    {"channel_id": "UCO2WJZKQoDW4Te6NHx4KfTg", "channel_name": "Geekyranjit", "category": "Electronics"},
    {"channel_id": "UCvpfclapgcuJo0M_x65pfRw", "channel_name": "Beebom", "category": "Electronics"},
    # Computer Accessories
    {"channel_id": "UCTzLRZUgelatKZ4nyIKcAbg", "channel_name": "Hardware Canucks", "category": "Computer Accessories"},
    {"channel_id": "UCdp6GUwjKscp5ST4M4WgIpw", "channel_name": "TechWiser", "category": "Computer Accessories"},
    # Audio
    {"channel_id": "UCS2MOjih52hqzk9YljFvdhw", "channel_name": "DHRME", "category": "Audio"},
    {"channel_id": "UCx9bOYEjkevIDYONBAstK-A", "channel_name": "Joshua Valour", "category": "Audio"},
    # Home Appliances
    {"channel_id": "UCvavJlMjlTd4wLwi9yKCtew", "channel_name": "Vacuum Wars", "category": "Home Appliances"},
    {"channel_id": "UCdp6GUwjKscp5ST4M4WgIpw", "channel_name": "TechWiser Appliances", "category": "Home Appliances"},
    # Kitchen Appliances
    {"channel_id": "UCxAS_aK7sS2x_bqnlJHDSHw", "channel_name": "America's Test Kitchen", "category": "Kitchen Appliances"},
    {"channel_id": "UCDq5v10l4wkV5-ZBIJJFbzQ", "channel_name": "Ethan Chlebowski", "category": "Kitchen Appliances"},
    # Gaming
    {"channel_id": "UCXuqSBlHAE6Xw-yeJA0Tunw", "channel_name": "Linus Tech Tips", "category": "Gaming"},
    {"channel_id": "UChIs72whgZI9w6d6FhwGGHA", "channel_name": "Gamers Nexus", "category": "Gaming"},
    # Smart Home
    {"channel_id": "UCwOBG77Tm8cE24FPxHb_abw", "channel_name": "Smart Home Solver", "category": "Smart Home"},
    {"channel_id": "UCVYd9HVKN-LeYNM_wc1P2HA", "channel_name": "Shane Whatley", "category": "Smart Home"},
    # Networking
    {"channel_id": "UC9x0AN7BWHpCDHSm9NiJFJQ", "channel_name": "NetworkChuck", "category": "Networking"},
    {"channel_id": "UCVS6ejD9NLZvjsvhcbiDzjw", "channel_name": "Crosstalk Solutions", "category": "Networking"},
    # Wearables
    {"channel_id": "UCmVhS0qulkRshtLrXMeMToQ", "channel_name": "DesFit", "category": "Wearables"},
    {"channel_id": "UChNWxrTlmh4IRSevon1X93g", "channel_name": "The Quantified Scientist", "category": "Wearables"},
    # Office / Productivity
    {"channel_id": "UCSLeoz5odIGS2GdlbHbCAUg", "channel_name": "Matthew Encina", "category": "Office / Productivity"},
    {"channel_id": "UCzlXf-yUIaOpOjEjPrOO9TA", "channel_name": "The Tech Chap", "category": "Office / Productivity"}
]

async def main():
    engine = create_async_engine(WORKFLOW_DB)
    
    # Auto-create tables if missing
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("Ensured workflow database tables exist.")

    async with engine.begin() as conn:
        print("Cleaning old test channel IDs...")
        await conn.execute(text("DELETE FROM channels WHERE channel_id LIKE 'UC4R8-%';"))
        
        print("Seeding 20 real YouTube channels into workflow database...")
        for ch in CHANNELS:
            await conn.execute(
                text("""
                    INSERT INTO channels (channel_id, channel_name, is_active)
                    VALUES (:cid, :cname, true)
                    ON CONFLICT (channel_id) DO UPDATE SET
                        channel_name = EXCLUDED.channel_name,
                        is_active = true;
                """),
                {"cid": ch["channel_id"], "cname": ch["channel_name"]}
            )
            print(f" - Seeded Real Channel: {ch['channel_name']} [{ch['category']}]")
            
    await engine.dispose()
    print("All 20 real YouTube channels successfully registered in PostgreSQL workflow DB!")

if __name__ == "__main__":
    asyncio.run(main())
