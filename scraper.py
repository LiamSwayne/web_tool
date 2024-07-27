import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from fake_useragent import UserAgent
import os
import random
import concurrent.futures

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
URLS_TO_PROCESS = 3000
MAX_WORKERS = 20  # Adjust based on system capabilities

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
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        
        # Get releases
        try:
            api_url = f"https://api.github.com/repos/{owner}/{repo}/releases"
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            releases = response.json()
            
            if isinstance(releases, list):
                for release in releases:
                    if isinstance(release, dict) and 'assets' in release:
                        for asset in release['assets']:
                            if isinstance(asset, dict) and 'browser_download_url' in asset:
                                urls.append(asset['browser_download_url'])
            else:
                print(f"Unexpected response format for releases: {releases}")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching releases: {e}")
        except Exception as e:
            print(f"Unexpected error fetching releases: {e}")
        
        # Get issues
        try:
            api_url = f"https://api.github.com/repos/{owner}/{repo}/issues"
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            issues = response.json()
            
            if isinstance(issues, list):
                for issue in issues:
                    if isinstance(issue, dict) and 'html_url' in issue:
                        urls.append(issue['html_url'])
            else:
                print(f"Unexpected response format for issues: {issues}")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching issues: {e}")
        except Exception as e:
            print(f"Unexpected error fetching issues: {e}")
        
        # Get pull requests
        try:
            api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            pulls = response.json()
            
            if isinstance(pulls, list):
                for pull in pulls:
                    if isinstance(pull, dict) and 'html_url' in pull:
                        urls.append(pull['html_url'])
            else:
                print(f"Unexpected response format for pulls: {pulls}")
        except requests.exceptions.RequestException as e:
            print(f"Error fetching pull requests: {e}")
        except Exception as e:
            print(f"Unexpected error fetching pull requests: {e}")
    
    return urls

def fetch_urls(url):
    ua = UserAgent()
    headers = {'User-Agent': ua.random}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
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
    
    except Exception:
        return set()

def check_archive_status(url):
    api_url = f"http://archive.org/wayback/available?url={url}"
    try:
        response = requests.get(api_url, timeout=10)
        data = response.json()
        return data['archived_snapshots'] != {}
    except Exception:
        return False

def remove_urls_from_file(urls, filename):
    with open(filename, 'r') as f:
        lines = f.readlines()
    with open(filename, 'w') as f:
        for line in lines:
            if line.strip() not in urls:
                f.write(line)

def append_urls_to_output(new_urls):
    output_file = "output_urls.txt"
    existing_urls = set()

    # Read existing URLs
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            existing_urls = set(line.strip() for line in f)

    # Find truly new URLs
    unique_new_urls = set(new_urls) - existing_urls

    # Check archive status of new URLs and update existing_urls
    urls_added = 0
    for url in unique_new_urls:
        if not check_archive_status(url):
            existing_urls.add(url)
            urls_added += 1
            print(f"Added new URL: {url}")  # Print each new URL as it's added

    # Write all unique URLs to the file
    with open(output_file, 'w') as f:
        for url in sorted(existing_urls):
            f.write(f"{url}\n")

    print(f"Added {urls_added} new unarchived URLs to output_urls.txt")
    print(f"Total unique URLs in output_urls.txt: {len(existing_urls)}")

def process_url(url):
    all_urls = fetch_urls(url)
    all_urls.add(url)
    print(f"Found {len(all_urls)} URLs in {url}")
    
    urls_to_archive = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        archive_results = executor.map(check_archive_status, all_urls)
        urls_to_archive = set(url for url, needs_archive in zip(all_urls, archive_results) if not needs_archive)
    
    return urls_to_archive

with open("source_urls.txt", "r") as f:
    source_urls = f.read().splitlines()

source_urls_to_process = random.sample(source_urls, min(URLS_TO_PROCESS, len(source_urls)))

all_urls_to_archive = set()
processed_source_urls = set()

with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    results = executor.map(process_url, source_urls_to_process)
    for source_url, urls_to_archive in zip(source_urls_to_process, results):
        all_urls_to_archive.update(urls_to_archive)
        processed_source_urls.add(source_url)
        if source_url not in urls_to_archive:
            all_urls_to_archive.add(source_url)
            print(f"Added source URL: {source_url}")  # Print each source URL as it's added

append_urls_to_output(all_urls_to_archive)
remove_urls_from_file(processed_source_urls, "source_urls.txt")
