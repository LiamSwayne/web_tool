import requests
import os
import time
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
from internetarchive import upload
from bs4 import BeautifulSoup

def fetch_url(url):
    try:
        response = requests.get(url, timeout=30)
        return response.content
    except Exception as e:
        print(f"Error fetching {url}: {str(e)}")
        return None

def fetch_resources(url):
    content = fetch_url(url)
    if content is None:
        return None

    resources = {
        'html': content,
        'resources': {}
    }

    soup = BeautifulSoup(content, 'html.parser')
    for tag in soup.find_all(['img', 'script', 'link']):
        src = tag.get('src') or tag.get('href')
        if src and src.startswith(('http://', 'https://')):
            resource_content = fetch_url(src)
            if resource_content:
                resources['resources'][src] = resource_content

    return resources

def package_for_archive(url, resources):
    if resources is None:
        return None

    domain = urlparse(url).netloc
    timestamp = int(time.time())
    dir_name = f"{domain}_{timestamp}"
    os.makedirs(dir_name, exist_ok=True)

    with open(f"{dir_name}/index.html", 'wb') as f:
        f.write(resources['html'])

    for resource_url, content in resources['resources'].items():
        filename = os.path.basename(urlparse(resource_url).path)
        with open(f"{dir_name}/{filename}", 'wb') as f:
            f.write(content)

    return dir_name

def submit_to_archive(package_dir):
    try:
        r = upload(package_dir, files=[f"{package_dir}/{f}" for f in os.listdir(package_dir)],
                   metadata={"collection": "web", "mediatype": "web"})
        print(f"Submitted {package_dir} to Internet Archive")
        return r
    except Exception as e:
        print(f"Error submitting {package_dir} to Internet Archive: {str(e)}")
        return None

def process_url(url):
    resources = fetch_resources(url)
    if resources:
        package_dir = package_for_archive(url, resources)
        if package_dir:
            submit_to_archive(package_dir)

# Read URLs from file
with open('selected_urls.txt', 'r') as f:
    urls = f.read().splitlines()

# Process up to 100 URLs
urls_to_process = urls[:100]

# Process URLs in parallel
with ThreadPoolExecutor(max_workers=5) as executor:
    executor.map(process_url, urls_to_process)
