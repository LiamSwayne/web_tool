import requests
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from fake_useragent import UserAgent

def check_archive_status(url):
    api_url = f"http://archive.org/wayback/available?url={url}"
    response = requests.get(api_url)
    data = response.json()
    hasSnapshot = data['archived_snapshots'] != {}
    return hasSnapshot

def archive_url(url):
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    
    if check_archive_status(url):
        print(f"Already archived: {url}")
        return

    archive_url = f"https://web.archive.org/save/{url}"
    
    while True:
        try:
            response = requests.get(archive_url, headers=headers)
            if response.status_code == 429:
                print(f"Rate limited. Waiting 3 minutes before retrying to archive {url}")
                time.sleep(180)  # Wait for 3 minutes
            else:
                print(f"Archived: {url}")
                break
        except Exception as e:
            print(f"Error archiving {url}: {str(e)}")
            break

def fetch_urls(url):
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    
    try:
        response = requests.get(url, headers=headers)
        html_content = response.text
        
        # Find all URLs starting with the specific substring
        lego_urls = set()
        start_string = "https://ideascdn.lego.com/media/generate/lego_ci/"
        start_index = 0
        while True:
            start_index = html_content.find(start_string, start_index)
            if start_index == -1:
                break
            end_index = html_content.find('"', start_index)
            if end_index == -1:
                end_index = html_content.find("'", start_index)
            if end_index == -1:
                break
            lego_url = html_content[start_index:end_index]
            if lego_url.endswith("/legacy"):
                lego_urls.add(lego_url[:-6] + "webp")
            else:
                lego_urls.add(lego_url)
            start_index = end_index
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all links
        links = set()
        for a_tag in soup.find_all('a', href=True):
            link = urljoin(url, a_tag['href'])
            if link.startswith('http'):
                links.add(link)
        
        # Find all image sources
        images = set()
        for img_tag in soup.find_all('img', src=True):
            img_src = urljoin(url, img_tag['src'])
            if img_src.startswith('http'):
                images.add(img_src)
        
        # Find any other URLs in the page content
        other_urls = set()
        for tag in soup.find_all():
            for attribute in tag.attrs:
                value = tag.attrs[attribute]
                if isinstance(value, str) and value.startswith('http'):
                    other_urls.add(value)
        
        return links.union(images).union(other_urls).union(lego_urls)
    
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return set()

# Read source URLs
with open("source_urls.txt", "r") as f:
    source_urls = f.read().splitlines()

all_urls = set()

# Process each source URL
for url in source_urls:
    print(f"Processing: {url}")
    fetched_urls = fetch_urls(url)
    all_urls.add(url)  # Add the original URL
    all_urls.update(fetched_urls)

# Archive if no snapshots currently exist and write all URLs to output file
with open("output_urls.txt", "w") as f:
    for url in sorted(all_urls):
        archive_url(url)
        f.write(f"{url}\n")

print(f"Found {len(all_urls)} unique URLs. Results written to output_urls.txt")