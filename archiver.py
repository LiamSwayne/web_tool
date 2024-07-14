import requests
import time
from fake_useragent import UserAgent

def archive_url(url, ua):
    headers = {'User-Agent': ua.random}
    archive_url = f"https://web.archive.org/save/{url}"
    
    try:
        response = requests.get(archive_url, headers=headers, timeout=30)
        if response.status_code == 429:
            print(f"Rate limited. Waiting 5 minutes before retrying to archive {url}")
            time.sleep(300)  # Wait for 5 minutes
            return archive_url(url, ua)  # Retry
        elif response.status_code == 200:
            print(f"Successfully archived: {url}")
            return True
        else:
            print(f"Failed to archive {url}: Status code {response.status_code}")
            return False
    except Exception as e:
        print(f"Error archiving {url}: {str(e)}")
        return False

ua = UserAgent()

# Read URLs from output_urls.txt
with open("output_urls.txt", "r") as f:
    urls = f.read().splitlines()

total_urls = len(urls)
archived_urls = 0

print(f"Starting to archive {total_urls} URLs...")

for i, url in enumerate(urls, 1):
    print(f"Processing URL {i} of {total_urls}")
    if archive_url(url, ua):
        archived_urls += 1
    
    # Add a small delay between requests to be polite
    time.sleep(2)

print(f"Archiving complete. Successfully archived {archived_urls} out of {total_urls} URLs.")