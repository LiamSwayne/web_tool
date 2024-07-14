import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from fake_useragent import UserAgent

def is_github_repo(url):
    parsed = urlparse(url)
    parts = parsed.path.split('/')
    return parsed.netloc == 'github.com' and len(parts) == 3

def get_github_archive_urls(repo_url):
    owner, repo = repo_url.split('/')[-2:]
    return [
        f"{repo_url}/archive/refs/heads/main.zip",
        f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/main"
    ]

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
                # Check if it's a GitHub repo and add archive URLs
                if is_github_repo(link):
                    links.update(get_github_archive_urls(link))
        
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

# Check archive status and write archived URLs to output file
with open("output_urls.txt", "w") as f:
    for url in sorted(all_urls):
        if check_archive_status(url):
            f.write(f"{url}\n")
            print(f"Archived: {url}")
        else:
            print(f"Not archived: {url}")

print(f"Processed {len(all_urls)} unique URLs. Archived URLs written to output_urls.txt")