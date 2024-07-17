import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from fake_useragent import UserAgent
import os
import time
import random

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

def is_github_repo(url):
    parsed = urlparse(url)
    parts = parsed.path.split('/')
    return parsed.netloc == 'github.com' and len(parts) == 3

def get_github_urls(repo_url):
    owner, repo = repo_url.split('/')[-2:]
    urls = [
        f"{repo_url}/archive/refs/heads/main.zip",
        f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/main"
    ]
    
    if GITHUB_TOKEN:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        
        try:
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            releases = response.json()
            
            for release in releases:
                for asset in release['assets']:
                    urls.append(asset['browser_download_url'])
            
        except Exception as e:
            print(f"Error fetching GitHub releases for {repo_url}: {str(e)}")
    else:
        print(f"Skipping GitHub API request for {repo_url} (no token provided)")
    
    return urls

def fetch_urls(url):
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    
    try:
        response = requests.get(url, headers=headers)
        html_content = response.text
        
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
        
        links = set()
        for a_tag in soup.find_all('a', href=True):
            link = urljoin(url, a_tag['href'])
            if link.startswith('http'):
                links.add(link)
                if is_github_repo(link):
                    links.update(get_github_urls(link))
        
        images = set()
        for img_tag in soup.find_all('img', src=True):
            img_src = urljoin(url, img_tag['src'])
            if img_src.startswith('http'):
                images.add(img_src)
        
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

def check_archive_status(url):
    api_url = f"http://archive.org/wayback/available?url={url}"
    response = requests.get(api_url)
    data = response.json()
    return data['archived_snapshots'] != {}

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

def remove_url_from_file(url, filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    with open(filename, 'w') as f:
        for line in lines:
            if line.strip() != url:
                f.write(line)

ua = UserAgent()

# Read source URLs
with open("source_urls.txt", "r") as f:
    source_urls = f.read().splitlines()

# Choose a random source URL
source_url = random.choice(source_urls)
print(f"Processing source URL: {source_url}")

# Fetch URLs from the source
all_urls = fetch_urls(source_url)
all_urls.add(source_url)  # Add the source URL itself

total_urls = len(all_urls)
archived_urls = 0
all_archived = True

print(f"Found {total_urls} URLs. Starting to process...")

for i, url in enumerate(all_urls, 1):
    print(f"Processing URL {i} of {total_urls}")
    
    if not check_archive_status(url):
        print(f"Archiving: {url}")
        if archive_url(url, ua):
            archived_urls += 1
        else:
            all_archived = False
    else:
        print(f"Already archived: {url}")
    
    # Add a small delay between requests to be polite
    time.sleep(2)

print(f"Process complete. Archived {archived_urls} new URLs out of {total_urls} total URLs.")

# Remove the source URL from source_urls.txt if all URLs were successfully archived
if all_archived:
    remove_url_from_file(source_url, "source_urls.txt")
    print(f"Removed {source_url} from source_urls.txt")
else:
    print(f"Not all URLs were archived successfully. Keeping {source_url} in source_urls.txt")
