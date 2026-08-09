import asyncio
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv(r"/var/www/ProvenPick/.env")
if not os.environ.get("PRODUCTION_DATABASE_URL"):
    load_dotenv(r"c:\Users\prade\Desktop\ProvenPick\.env")

PROD_DB = os.environ.get("PRODUCTION_DATABASE_URL") or "postgresql+asyncpg://provenpick:provenpick123@127.0.0.1:5432/provenpick_production"

TAXONOMY = [
    {
        "l1_name": "Electronics",
        "l1_slug": "electronics",
        "icon": "",
        "l2_categories": [
            {"l2_name": "Smartphones", "l2_slug": "smartphones", "l3": ["Android Phones", "iPhones", "Foldable Phones"]},
            {"l2_name": "Laptops", "l2_slug": "laptops", "l3": ["Gaming Laptops", "Business Laptops", "Student Laptops", "Ultrabooks"]},
            {"l2_name": "Tablets", "l2_slug": "tablets", "l3": ["Android Tablets", "iPads"]},
            {"l2_name": "Monitors", "l2_slug": "monitors", "l3": ["Gaming Monitors", "4K Monitors", "Ultrawide Monitors"]},
            {"l2_name": "TVs", "l2_slug": "tvs", "l3": ["OLED TVs", "QLED TVs", "Mini LED TVs"]},
            {"l2_name": "Cameras", "l2_slug": "cameras", "l3": ["DSLR Cameras", "Mirrorless Cameras", "Action Cameras"]},
            {"l2_name": "Printers", "l2_slug": "printers", "l3": ["Inkjet Printers", "Laser Printers"]}
        ]
    },
    {
        "l1_name": "Computer Accessories",
        "l1_slug": "computer-accessories",
        "icon": "",
        "l2_categories": [
            {"l2_name": "Keyboard", "l2_slug": "keyboard", "l3": ["Mechanical Keyboards", "Wireless Keyboards", "Ergonomic Keyboards"]},
            {"l2_name": "Mouse", "l2_slug": "mouse", "l3": ["Gaming Mice", "Wireless Mice", "Ergonomic Mice"]},
            {"l2_name": "Storage", "l2_slug": "storage", "l3": ["Internal SSDs", "External SSDs", "HDDs", "NAS Drives"]},
            {"l2_name": "Webcam", "l2_slug": "webcam", "l3": ["1080p Webcams", "4K Webcams"]},
            {"l2_name": "Docking Stations", "l2_slug": "docking-stations", "l3": ["USB-C Docks", "Thunderbolt Docks"]}
        ]
    },
    {
        "l1_name": "Audio",
        "l1_slug": "audio",
        "icon": "",
        "l2_categories": [
            {"l2_name": "Headphones", "l2_slug": "headphones", "l3": ["Over Ear", "On Ear"]},
            {"l2_name": "Earbuds", "l2_slug": "earbuds", "l3": ["True Wireless", "Neckband"]},
            {"l2_name": "Speakers", "l2_slug": "speakers", "l3": ["Bluetooth Speakers", "Smart Speakers", "Bookshelf Speakers"]},
            {"l2_name": "Microphones", "l2_slug": "microphones", "l3": ["USB Microphones", "XLR Microphones"]},
            {"l2_name": "Soundbars", "l2_slug": "soundbars", "l3": ["Dolby Atmos Soundbars", "Budget Soundbars"]}
        ]
    },
    {
        "l1_name": "Home Appliances",
        "l1_slug": "home-appliances",
        "icon": "",
        "l2_categories": [
            {"l2_name": "Refrigerators", "l2_slug": "refrigerators", "l3": ["Single Door", "Double Door", "Side by Side"]},
            {"l2_name": "Washing Machines", "l2_slug": "washing-machines", "l3": ["Front Load", "Top Load"]},
            {"l2_name": "Air Conditioners", "l2_slug": "air-conditioners", "l3": ["Split ACs", "Window ACs"]},
            {"l2_name": "Air Purifiers", "l2_slug": "air-purifiers", "l3": ["HEPA Purifiers"]},
            {"l2_name": "Water Purifiers", "l2_slug": "water-purifiers", "l3": ["RO Purifiers", "UV Purifiers"]},
            {"l2_name": "Vacuum Cleaners", "l2_slug": "vacuum-cleaners", "l3": ["Robot Vacuum", "Stick Vacuum"]}
        ]
    },
    {
        "l1_name": "Kitchen Appliances",
        "l1_slug": "kitchen-appliances",
        "icon": "",
        "l2_categories": [
            {"l2_name": "Mixer Grinder", "l2_slug": "mixer-grinder", "l3": ["Heavy Duty Mixers", "Compact Mixers"]},
            {"l2_name": "Microwave", "l2_slug": "microwave", "l3": ["Solo Microwaves", "Grill Microwaves", "Convection Microwaves"]},
            {"l2_name": "Air Fryer", "l2_slug": "air-fryer", "l3": ["Basket Style Fryers", "Oven Style Fryers"]},
            {"l2_name": "Coffee Makers", "l2_slug": "coffee-makers", "l3": ["Drip Coffee", "Espresso Machines"]},
            {"l2_name": "Electric Kettle", "l2_slug": "electric-kettle", "l3": ["Stainless Steel Kettles", "Glass Kettles"]},
            {"l2_name": "Rice Cooker", "l2_slug": "rice-cooker", "l3": ["Standard Cookers", "Digital Cookers"]}
        ]
    },
    {
        "l1_name": "Gaming",
        "l1_slug": "gaming",
        "icon": "",
        "l2_categories": [
            {"l2_name": "Consoles", "l2_slug": "consoles", "l3": ["PlayStation", "Xbox", "Nintendo Switch"]},
            {"l2_name": "Gaming PCs", "l2_slug": "gaming-pcs", "l3": ["Prebuilt Gaming PCs", "Custom Rig Components"]},
            {"l2_name": "Gaming Chairs", "l2_slug": "gaming-chairs", "l3": ["Ergonomic Gaming Chairs", "Leatherette Chairs"]},
            {"l2_name": "Controllers", "l2_slug": "controllers", "l3": ["Wireless Gamepads", "Pro Controllers"]},
            {"l2_name": "VR", "l2_slug": "vr", "l3": ["Standalone VR", "PC VR Headsets"]}
        ]
    },
    {
        "l1_name": "Smart Home",
        "l1_slug": "smart-home",
        "icon": "",
        "l2_categories": [
            {"l2_name": "Smart Lights", "l2_slug": "smart-lights", "l3": ["Smart Bulbs", "Light Strips"]},
            {"l2_name": "Security Cameras", "l2_slug": "security-cameras", "l3": ["Indoor Cameras", "Outdoor Weatherproof Cameras"]},
            {"l2_name": "Smart Locks", "l2_slug": "smart-locks", "l3": ["Fingerprint Locks", "Keypad Locks"]},
            {"l2_name": "Doorbells", "l2_slug": "doorbells", "l3": ["Video Doorbells"]},
            {"l2_name": "Plugs", "l2_slug": "plugs", "l3": ["Smart Wi-Fi Plugs"]}
        ]
    },
    {
        "l1_name": "Networking",
        "l1_slug": "networking",
        "icon": "",
        "l2_categories": [
            {"l2_name": "Routers", "l2_slug": "routers", "l3": ["Wi-Fi 6 Routers", "Wi-Fi 7 Routers", "Gaming Routers"]},
            {"l2_name": "Mesh Systems", "l2_slug": "mesh-systems", "l3": ["Dual-Band Mesh", "Tri-Band Mesh"]},
            {"l2_name": "Switches", "l2_slug": "switches", "l3": ["Gigabit Switches", "PoE Switches"]}
        ]
    },
    {
        "l1_name": "Wearables",
        "l1_slug": "wearables",
        "icon": "",
        "l2_categories": [
            {"l2_name": "Smartwatches", "l2_slug": "smartwatches", "l3": ["Apple Watches", "Android Smartwatches", "Sports Watches"]},
            {"l2_name": "Fitness Bands", "l2_slug": "fitness-bands", "l3": ["Activity Trackers"]},
            {"l2_name": "Smart Rings", "l2_slug": "smart-rings", "l3": ["Health Tracking Rings"]}
        ]
    },
    {
        "l1_name": "Office / Productivity",
        "l1_slug": "office-productivity",
        "icon": "",
        "l2_categories": [
            {"l2_name": "Chairs", "l2_slug": "chairs", "l3": ["Ergonomic Office Chairs", "Mesh Chairs"]},
            {"l2_name": "Standing Desks", "l2_slug": "standing-desks", "l3": ["Motorized Standing Desks", "Manual Desks"]},
            {"l2_name": "Desk Lamps", "l2_slug": "desk-lamps", "l3": ["LED Monitor Light Bars", "Smart Desk Lamps"]}
        ]
    }
]

async def main():
    engine = create_async_engine(PROD_DB)
    async with engine.begin() as conn:
        print("Clearing and re-seeding full category taxonomy (No Emojis)...")
        await conn.execute(text("TRUNCATE TABLE l3_categories, l2_categories, l1_categories RESTART IDENTITY CASCADE;"))
        
        for l1_item in TAXONOMY:
            res_l1 = await conn.execute(
                text("INSERT INTO l1_categories (name, slug, icon) VALUES (:name, :slug, :icon) RETURNING id;"),
                {"name": l1_item["l1_name"], "slug": l1_item["l1_slug"], "icon": l1_item["icon"]}
            )
            l1_id = res_l1.scalar_one()
            print(f"L1 Category: {l1_item['l1_name']} (ID {l1_id})")
            
            for l2_item in l1_item["l2_categories"]:
                res_l2 = await conn.execute(
                    text("INSERT INTO l2_categories (l1_id, name, slug) VALUES (:l1_id, :name, :slug) RETURNING id;"),
                    {"l1_id": l1_id, "name": l2_item["l2_name"], "slug": l2_item["l2_slug"]}
                )
                l2_id = res_l2.scalar_one()
                
                for l3_name in l2_item["l3"]:
                    l3_slug = f"{l2_item['l2_slug']}-{l3_name.lower().replace(' ', '-')}"
                    await conn.execute(
                        text("INSERT INTO l3_categories (l2_id, name, slug) VALUES (:l2_id, :name, :slug);"),
                        {"l2_id": l2_id, "name": l3_name, "slug": l3_slug}
                    )
                    
    await engine.dispose()
    print("Taxonomy successfully seeded without emojis!")

if __name__ == "__main__":
    asyncio.run(main())
