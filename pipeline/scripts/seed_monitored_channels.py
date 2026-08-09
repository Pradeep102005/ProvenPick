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
    {"channel_id": "UCgWi34h4-6s5JbJd_U601qA", "channel_name": "Geekyranjit", "category": "Electronics"},
    {"channel_id": "UCp1q4i1WcZ8J-Cj-rXp4Z7A", "channel_name": "Beebom", "category": "Electronics"},
    # Computer Accessories
    {"channel_id": "UCosNW_a1tP89qZpP2N4Z8XA", "channel_name": "Hardware Canucks", "category": "Computer Accessories"},
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2g", "channel_name": "TechWiser", "category": "Computer Accessories"},
    # Audio
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2h", "channel_name": "DHRME", "category": "Audio"},
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2i", "channel_name": "Joshua Valour", "category": "Audio"},
    # Home Appliances
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2j", "channel_name": "Vacuum Wars", "category": "Home Appliances"},
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2k", "channel_name": "Just A Dad Videos", "category": "Home Appliances"},
    # Kitchen Appliances
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2l", "channel_name": "America's Test Kitchen", "category": "Kitchen Appliances"},
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2m", "channel_name": "Ethan Chlebowski", "category": "Kitchen Appliances"},
    # Gaming
    {"channel_id": "UCXuqSBlHAE6Xw-yeJA0Tunw", "channel_name": "Linus Tech Tips", "category": "Gaming"},
    {"channel_id": "UCl2mFZoRqjw_ELbB45zpGZQ", "channel_name": "Gamers Nexus", "category": "Gaming"},
    # Smart Home
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2n", "channel_name": "Smart Home Solver", "category": "Smart Home"},
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2o", "channel_name": "Shane Whatley", "category": "Smart Home"},
    # Networking
    {"channel_id": "UCg9bLg2w-P1-X7y_V4_8h9A", "channel_name": "NetworkChuck", "category": "Networking"},
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2p", "channel_name": "Crosstalk Solutions", "category": "Networking"},
    # Wearables
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2q", "channel_name": "DesFit", "category": "Wearables"},
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2r", "channel_name": "The Quantified Scientist", "category": "Wearables"},
    # Office / Productivity
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2s", "channel_name": "Matthew Encina", "category": "Office / Productivity"},
    {"channel_id": "UC4R8-N8kQ1cZ2X1N1_p8A2t", "channel_name": "The Tech Chap", "category": "Office / Productivity"}
]

async def main():
    engine = create_async_engine(WORKFLOW_DB)
    
    # Auto-create tables if missing
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("Ensured workflow database tables exist.")

    async with engine.begin() as conn:
        print("Seeding 20 YouTube channels into workflow database...")
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
            print(f" - Seeded Channel: {ch['channel_name']} [{ch['category']}]")
            
    await engine.dispose()
    print("All 20 channels successfully registered in PostgreSQL workflow DB!")

if __name__ == "__main__":
    asyncio.run(main())
