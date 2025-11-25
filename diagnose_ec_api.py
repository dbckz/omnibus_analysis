#!/usr/bin/env python3
"""
Diagnostic script to test the EC Have Your Say API and discover its current structure.
Run this first to see what the API returns.
"""

import json
import requests
from pprint import pprint

PUBLICATION_ID = "20401"
BASE_URL = "https://ec.europa.eu/info/law/better-regulation/"

# All possible API endpoints to test
ENDPOINTS_TO_TEST = [
    ("api/allFeedback", {"publicationId": PUBLICATION_ID}),
    ("api/allFeedback", {"publicationId": PUBLICATION_ID, "page": 0}),
    ("api/allFeedback", {"publicationId": PUBLICATION_ID, "page": 0, "size": 10}),
    ("brpapi/feedback", {"publicationId": PUBLICATION_ID}),
    ("brpapi/feedback", {"publicationId": PUBLICATION_ID, "page": 0, "size": 10}),
    ("api/feedback", {"publicationId": PUBLICATION_ID}),
    ("api/v1/feedback", {"publicationId": PUBLICATION_ID}),
    ("api/shortTitleByPublicationId", {"publicationId": PUBLICATION_ID}),
]

def test_endpoint(endpoint, params):
    """Test an API endpoint and report results."""
    url = BASE_URL + endpoint
    
    print(f"\n{'='*70}")
    print(f"Testing: {endpoint}")
    print(f"Params: {params}")
    print(f"Full URL: {url}?{'&'.join(f'{k}={v}' for k,v in params.items())}")
    print("-" * 70)
    
    try:
        headers = {
            "Accept": "application/json, */*",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
        response = requests.get(url, params=params, headers=headers, timeout=30)
        
        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                # Show structure
                if isinstance(data, dict):
                    print(f"\nResponse Type: dict")
                    print(f"Top-level keys: {list(data.keys())}")
                    
                    # Check for common structures
                    if "page" in data:
                        print(f"\nPagination info ('page'):")
                        pprint(data["page"])
                    
                    if "totalPages" in data:
                        print(f"totalPages: {data['totalPages']}")
                    
                    if "totalElements" in data:
                        print(f"totalElements: {data['totalElements']}")
                    
                    if "_embedded" in data:
                        print(f"\n_embedded keys: {list(data['_embedded'].keys())}")
                        for key in data["_embedded"]:
                            items = data["_embedded"][key]
                            print(f"  {key}: {len(items)} items")
                            if items:
                                print(f"  First item keys: {list(items[0].keys())[:10]}")
                    
                    if "content" in data:
                        print(f"\ncontent: {len(data['content'])} items")
                        if data["content"]:
                            print(f"First item keys: {list(data['content'][0].keys())[:10]}")
                    
                    if "feedbacks" in data:
                        print(f"\nfeedbacks: {len(data['feedbacks'])} items")
                    
                    # Show first 500 chars of raw JSON for debugging
                    print(f"\nFirst 500 chars of response:")
                    print(json.dumps(data, indent=2)[:500])
                    
                elif isinstance(data, list):
                    print(f"\nResponse Type: list with {len(data)} items")
                    if data:
                        print(f"First item keys: {list(data[0].keys())[:10] if isinstance(data[0], dict) else 'not a dict'}")
                else:
                    print(f"\nResponse Type: {type(data)}")
                    print(f"Value: {data}")
                
                return True, data
                
            except json.JSONDecodeError:
                print(f"Response is not JSON:")
                print(response.text[:500])
                return False, None
        else:
            print(f"Error response:")
            print(response.text[:500])
            return False, None
            
    except requests.exceptions.Timeout:
        print("Request timed out")
        return False, None
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return False, None

def main():
    print("=" * 70)
    print("EC Have Your Say API Diagnostic Tool")
    print(f"Publication ID: {PUBLICATION_ID}")
    print("=" * 70)
    
    working_endpoints = []
    
    for endpoint, params in ENDPOINTS_TO_TEST:
        success, data = test_endpoint(endpoint, params)
        if success:
            working_endpoints.append((endpoint, params, data))
    
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    
    if working_endpoints:
        print(f"Found {len(working_endpoints)} working endpoint(s):")
        for endpoint, params, data in working_endpoints:
            print(f"  - {endpoint}")
            if isinstance(data, dict):
                if "_embedded" in data and "feedback" in data["_embedded"]:
                    print(f"    → Contains {len(data['_embedded']['feedback'])} feedbacks in _embedded.feedback")
                elif "content" in data:
                    print(f"    → Contains {len(data['content'])} items in content")
    else:
        print("No working endpoints found!")
        print("\nPossible issues:")
        print("1. The EC has changed their API structure")
        print("2. Network/firewall issues")
        print("3. API rate limiting")
        print("\nTry opening this URL in your browser:")
        print(f"  {BASE_URL}api/allFeedback?publicationId={PUBLICATION_ID}")
        print("\nAnd check the Network tab in browser dev tools to see the actual API calls.")
    
    # Save results
    if working_endpoints:
        with open("api_diagnostic_results.json", "w") as f:
            results = []
            for endpoint, params, data in working_endpoints:
                results.append({
                    "endpoint": endpoint,
                    "params": params,
                    "data_preview": json.dumps(data)[:2000]
                })
            json.dump(results, f, indent=2)
        print("\nDiagnostic results saved to: api_diagnostic_results.json")

if __name__ == "__main__":
    main()
