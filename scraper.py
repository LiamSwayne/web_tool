import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from fake_useragent import UserAgent
import os
import random
import concurrent.futures

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
URLS_TO_PROCESS = 3000
MAX_WORKERS = 20

def get_github_urls(repo_url):
    owner, repo = repo_url.split('/')[-2:]
    urls = [f"{repo_url}/archive/refs/heads/main.zip", f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/main"]
    
    if GITHUB_TOKEN:
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        api_endpoints = [
            (f"https://api.github.com/repos/{owner}/{repo}/releases", 'assets', 'browser_download_url'),
            (f"https://api.github.com/repos/{owner}/{repo}/issues", None, 'html_url'),
            (f"https://api.github.com/repos/{owner}/{repo}/pulls", None, 'html_url')
        ]
        
        for api_url, asset_key, url_key in api_endpoints:
            try:
                response = requests.get(api_url, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                if isinstance(data, list):
                    for item in data:
                        if asset_key:
                            for asset in item.get(asset_key, []):
                                urls.append(asset[url_key])
                        else:
                            urls.append(item[url_key])
            except Exception:
                pass
    
    return sorted(set(urls))

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
            lego_urls.add(lego_url[:-6] + "webp" if lego_url.endswith("/legacy") else lego_url)
            start_index = end_index
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        links = {urljoin(url, a['href']) for a in soup.find_all('a', href=True) if urljoin(url, a['href']).startswith('http')}
        github_repos = {link for link in links if urlparse(link).netloc == 'github.com' and len(urlparse(link).path.split('/')) == 3}
        for repo in github_repos:
            links.update(get_github_urls(repo))
        
        images = {urljoin(url, img['src']) for img in soup.find_all('img', src=True) if urljoin(url, img['src']).startswith('http')}
        
        other_urls = {v for tag in soup.find_all() for v in tag.attrs.values() if isinstance(v, str) and v.startswith('http')}
        
        return sorted(links.union(images).union(other_urls).union(lego_urls))
    
    except Exception:
        return []

def needs_archive(url):
    try:
        response = requests.get(f"http://archive.org/wayback/available?url={url}", timeout=10)
        return response.json()['archived_snapshots'] == {}
    except Exception as e:
        print(e)
        return False

def process_url(url):
    all_urls = fetch_urls(url)
    all_urls.append(url)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        archive_results = list(executor.map(needs_archive, all_urls))
    
    return sorted({url for url, needs_archive in zip(all_urls, archive_results) if needs_archive})

def append_urls_to_output(new_urls):
    output_file = "output_urls.txt"
    existing_urls = set()

    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            existing_urls = set(line.strip() for line in f)

    unique_new_urls = set(new_urls) - existing_urls
    existing_urls.update(unique_new_urls)

    with open(output_file, 'w') as f:
        print(sorted(existing_urls[:100]))
        for url in sorted(existing_urls):
            if needs_archive(url):
                print("need archive for"+str(url))
                f.write(f"{url}\n")

    # print(f"Added {len(unique_new_urls)} new unarchived URLs to output_urls.txt")

with open("source_urls.txt", "r") as f:
    source_urls = sorted(set(f.read().splitlines()))

source_urls_to_process = random.sample(source_urls, min(URLS_TO_PROCESS, len(source_urls)))

all_urls_to_archive = set()
processed_source_urls = set()

with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    results = list(executor.map(process_url, source_urls_to_process))
    for source_url, urls_to_archive in zip(source_urls_to_process, results):
        all_urls_to_archive.update(urls_to_archive)
        processed_source_urls.add(source_url)
        if source_url not in urls_to_archive:
            all_urls_to_archive.add(source_url)

append_urls_to_output(sorted(all_urls_to_archive))

with open("source_urls.txt", "w") as f:
    remaining_urls = sorted(set(source_urls) - processed_source_urls)
    f.write("\n".join(remaining_urls))
