import httpx
import uuid
import sys

BASE_URL = "http://localhost:8001/api/reviews"

def test_staging_workflow():
    print("=== Starting Staging API End-to-End Workflow Test ===")
    
    # 1. Generate unique Job UUID to simulate a pipeline run
    job_id = str(uuid.uuid4())
    print(f"Generated test job_uuid: {job_id}")
    
    # 2. Define mock payload (Zebronics Review with multi-page sections)
    payload = {
        "job_uuid": job_id,
        "name": "Zebronics Thunder",
        "brand": "Zebronics",
        "price_inr": 1199.00,
        "l3_category_id": 12,
        "category_name": "Over-Ear Headphones",
        "review_title": "Zebronics Thunder Review: High Bass at a Rock-Bottom Price",
        "slug": "zebronics-thunder-review",
        "summary": "An ultra-budget over-ear headphone focusing heavily on booming bass.",
        "verdict": "Great for bass lovers on a tight budget, but build quality is cheap plastic.",
        "rating": 4.10,
        "review_sections": [
            {
                "page_index": 1,
                "title": "Introduction & Design",
                "content_html": "<p>Zebronics is known for aggressive pricing. The Thunder offers wireless audio for under 1500...</p><h3>Design</h3><p>Built entirely out of plastic with soft ear cushioning...</p>"
            },
            {
                "page_index": 2,
                "title": "Audio Performance & Battery",
                "content_html": "<h3>Sound Quality</h3><p>Heavy, boomy bass which overrides the mids and highs. Audiophiles should steer clear.</p><h3>Battery</h3><p>Offers about 9 hours of playback on a single charge.</p>"
            },
            {
                "page_index": 3,
                "title": "Verdict",
                "content_html": "<h3>Final Verdict</h3><p>At 1199, it is hard to complain. It delivers wireless connectivity and high volume, making it suitable for casual music listening.</p>"
            }
        ],
        "specs": {
            "Driver Size": "40mm",
            "Connectivity": "Bluetooth 5.0 / Aux",
            "Playback Time": "9 Hours",
            "ANC": "No"
        },
        "pros": [
            {"text": "Extremely affordable price", "weight": 5},
            {"text": "Strong bass output", "weight": 4}
        ],
        "cons": [
            {"text": "Cheap plastic construction", "weight": 5},
            {"text": "Muddy sound signature", "weight": 4}
        ],
        "affiliate_links": {
            "amazon": "https://amazon.in/dp/mock-zebronics",
            "flipkart": "https://flipkart.com/mock-zebronics"
        },
        "image_urls": [
            "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500"
        ],
        "mindmap_mermaid": "graph TD\nZebronics --> Pros\nZebronics --> Cons",
        "sources": [
            {
                "video_url": "https://youtube.com/watch?v=mock1",
                "video_title": "Zebronics Thunder Gaming Review",
                "channel_name": "TechTester"
            },
            {
                "video_url": "https://youtube.com/watch?v=mock2",
                "video_title": "Is Zebronics Thunder Worth Rs.1199?",
                "channel_name": "UnboxManiac"
            }
        ]
    }

    # 3. Test POST /submit
    print("\n--- Test 1: Submitting Draft Review ---")
    try:
        resp = httpx.post(f"{BASE_URL}/submit", json=payload)
    except httpx.ConnectError:
        print("ERROR: Could not connect to Staging API. Is the server running on port 8001?")
        sys.exit(1)
        
    if resp.status_code != 201:
        print(f"FAILED to submit review: {resp.status_code} - {resp.text}")
        sys.exit(1)
    
    review_data = resp.json()
    product_uuid = review_data["product_uuid"]
    print(f"SUCCESS! Staging review created with product_uuid: {product_uuid}")
    print(f"Status: {review_data['status']}")
    print(f"Saved sections count: {len(review_data['review_sections'])}")
    
    # 4. Test GET / (List Reviews)
    print("\n--- Test 2: Listing Pending Reviews ---")
    resp = httpx.get(BASE_URL, params={"status": "pending"})
    if resp.status_code != 200:
        print(f"FAILED to list reviews: {resp.status_code}")
        sys.exit(1)
    
    pending_list = resp.json()
    found = any(r["product_uuid"] == product_uuid for r in pending_list)
    if found:
        print("SUCCESS! Submitted review found in 'pending' list.")
    else:
        print("FAILED: Submitted review was NOT found in 'pending' list.")
        sys.exit(1)

    # 5. Test PATCH /reject (Human reviewer actions)
    print("\n--- Test 3: Rejecting Review (Human feedback) ---")
    reject_comment = "Add warning about battery life degradation over time and muddy treble."
    resp = httpx.patch(f"{BASE_URL}/{product_uuid}/reject", json={"editor_comments": reject_comment})
    if resp.status_code != 200:
        print(f"FAILED to reject review: {resp.status_code} - {resp.text}")
        sys.exit(1)
    
    rejected_data = resp.json()
    print(f"SUCCESS! Review rejected. Status is now: {rejected_data['status']}")
    print(f"Editor Comments stored: '{rejected_data['editor_comments']}'")
    print(f"Rejection Count: {rejected_data['rejection_count']}")

    # 6. Test POST /submit again (AI rewrite resubmission)
    print("\n--- Test 4: AI Resubmitting Refactored Review ---")
    # Update verdict and a section content with mock editor changes
    payload["verdict"] += " treble is muddy and battery degrades after 6 months."
    payload["review_sections"][1]["content_html"] += "<p>Note: Treble is severely rolled off.</p>"
    
    resp = httpx.post(f"{BASE_URL}/submit", json=payload)
    if resp.status_code not in (200, 201):
        print(f"FAILED: Resubmission failed: {resp.status_code} - {resp.text}")
        sys.exit(1)
    
    updated_data = resp.json()
    print(f"SUCCESS! Review resubmitted and merged. Status reset to: {updated_data['status']}")
    print(f"Updated Verdict: {updated_data['verdict']}")
    print(f"Rejection count preserved: {updated_data['rejection_count']}")

    # 7. Test GET /by-job (Pipeline polling check)
    print("\n--- Test 5: Polling by Job UUID ---")
    resp = httpx.get(f"{BASE_URL}/by-job/{job_id}")
    if resp.status_code != 200:
        print(f"FAILED to query by job_uuid: {resp.status_code}")
        sys.exit(1)
    print(f"SUCCESS! Polling found review status is: {resp.json()['status']}")

    # 8. Test PATCH /approve
    print("\n--- Test 6: Approving Review ---")
    resp = httpx.patch(f"{BASE_URL}/{product_uuid}/approve", json={"category_name": "Over-Ear Bluetooth Headphones"})
    if resp.status_code != 200:
        print(f"FAILED: Approval failed: {resp.status_code}")
        sys.exit(1)
    
    approved_data = resp.json()
    print(f"SUCCESS! Review approved. Status is now: {approved_data['status']}")
    print(f"Updated Category Name: {approved_data['category_name']}")

    print("\n=== All 6 workflow tests passed successfully! Staging API backend is fully operational. ===")

if __name__ == "__main__":
    test_staging_workflow()
