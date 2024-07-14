import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from fake_useragent import UserAgent
import os
import datetime

# Use environment variable for GitHub token
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

def check_archive_status(url):
    api_url = f"http://archive.org/wayback/available?url={url}"
    response = requests.get(api_url)
    data = response.json()
    return data['archived_snapshots'] != {}

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
                # Check if it's a GitHub repo and add .git and release asset URLs
                if is_github_repo(link):
                    links.update(get_github_urls(link))
        
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

# Generate timestamp for filename
timestamp = datetime.datetime.now().strftime("%Y_%m_%d_%H_%M")
output_filename = f"output_urls_{timestamp}.txt"

# Check archive status and write archived URLs to output file
with open(output_filename, "w") as f:
    for url in sorted(all_urls):
        if check_archive_status(url):
            f.write(f"{url}\n")
            print(f"Archived: {url}")
        else:
            print(f"Not archived: {url}")

print(f"Processed {len(all_urls)} unique URLs. Archived URLs written to {output_filename}")