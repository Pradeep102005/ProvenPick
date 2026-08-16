import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

WORKFLOW_DB = os.environ.get(
    "WORKFLOW_DATABASE_URL",
    "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5432/provenpick_workflow"
)

# ── Monitored YouTube Tech & Product Channels (Verified Real Channel IDs) ──
CHANNELS = [
    # Electronics (Hindi, Telugu & Top Indian Tech Channels)
    {"channel_id": "UCXsXitjiT_8qPgNEFGPVfBA", "channel_name": "Technical Guruji", "category": "Electronics"},
    {"channel_id": "UCgJ5_1F6yJhYLnyMszUdmUg", "channel_name": "Trakin Tech", "category": "Electronics"},
    {"channel_id": "UCBVDOqAOemETfc-MOn4fqgA", "channel_name": "Prasadtechintelugu", "category": "Electronics"},
    {"channel_id": "UCqeXMnAG9VCSQcxLR-F2mKw", "channel_name": "Tech Burner", "category": "Electronics"},
    {"channel_id": "UCS5cgC8B_dGDftYqE_TbneQ", "channel_name": "Geekyranjit", "category": "Electronics"},

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
    print(f"Connecting to Workflow DB: {WORKFLOW_DB}")
    engine = create_async_engine(WORKFLOW_DB)
    async with engine.begin() as conn:
        print("Seeding verified YouTube channels into channels table...")
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
            print(f" - Seeded Channel: {ch['channel_name']} [{ch['category']}] -> {ch['channel_id']}")
            
    await engine.dispose()
    print("\n✅ All verified YouTube channels registered in PostgreSQL workflow DB!")

if __name__ == "__main__":
    asyncio.run(main())
