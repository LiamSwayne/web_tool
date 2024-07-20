import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from fake_useragent import UserAgent
import os
import random

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
URLS_TO_PROCESS = 50

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

def remove_urls_from_file(urls, filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    with open(filename, 'w') as f:
        for line in lines:
            if line.strip() not in urls:
                f.write(line)

def append_urls_to_output(urls):
    output_file = "output_urls.txt"
    existing_urls = set()

    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            existing_urls = set(line.strip() for line in f)

    all_urls = existing_urls.union(urls)

    with open(output_file, 'w') as f:
        for url in all_urls:
            f.write(f"{url}\n")

    print(f"Updated {output_file} with {len(all_urls)} unique URLs")

# Read source URLs
with open("source_urls.txt", "r") as f:
    source_urls = f.read().splitlines()

# Choose random source URLs
source_urls_to_process = random.sample(source_urls, min(URLS_TO_PROCESS, len(source_urls)))

urls_to_archive = set()
processed_source_urls = set()

for source_url in source_urls_to_process:
    print(f"Processing source URL: {source_url}")

    # Fetch URLs from the source
    all_urls = fetch_urls(source_url)
    all_urls.add(source_url)  # Add the source URL itself

    total_urls = len(all_urls)
    print(f"Found {total_urls} URLs. Processing...")

    for i, url in enumerate(all_urls, 1):
        print(f"Processing URL {i} of {total_urls}")
        
        if not check_archive_status(url):
            print(f"Would archive: {url}")
            urls_to_archive.add(url)
        else:
            print(f"Already archived: {url}")

    processed_source_urls.add(source_url)
    print(f"Completed processing source URL: {source_url}")

print(f"Process complete. Found {len(urls_to_archive)} URLs to archive.")

# Append the URLs to the output file
append_urls_to_output(urls_to_archive)

# Remove the processed source URLs
remove_urls_from_file(processed_source_urls, "source_urls.txt")
print(f"Removed {len(processed_source_urls)} processed URLs from source_urls.txt")
