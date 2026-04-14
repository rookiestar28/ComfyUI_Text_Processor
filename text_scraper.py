import ipaddress
import socket
import sys
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("[TextScraper] Error: Missing dependencies. Please run 'pip install requests beautifulsoup4'")
    pass

from typing import List, Dict


BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain"}


def _is_blocked_ip(address):
    ip = ipaddress.ip_address(address)
    return any([
        ip.is_private,
        ip.is_loopback,
        ip.is_link_local,
        ip.is_multicast,
        ip.is_reserved,
        ip.is_unspecified,
    ])

class TextScraper:
    """
    A ComfyUI node that scrapes news headlines from a given URL.
    Includes a 'seed' mechanism to force updates even if the URL hasn't changed.
    """
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "url": ("STRING", {
                    "default": "https://news.ycombinator.com",
                    "multiline": False
                }),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "scrape_news"
    CATEGORY = "ComfyUI Text Processor"

    def normalize_and_validate_url(self, url: str):
        url = url.strip()
        if not url:
            return None, "Please enter a valid URL."

        if "://" not in url:
            url = "https://" + url

        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return None, "Blocked URL: only http and https URLs are allowed."

        hostname = parsed.hostname
        if not hostname:
            return None, "Please enter a valid URL."

        normalized_host = hostname.rstrip(".").lower()
        if normalized_host in BLOCKED_HOSTNAMES:
            return None, "Blocked URL: private or local network addresses are not allowed."

        # CRITICAL: validate workflow-controlled URLs before requests.get to reduce SSRF exposure.
        try:
            try:
                if _is_blocked_ip(normalized_host):
                    return None, "Blocked URL: private or local network addresses are not allowed."
                return url, None
            except ValueError:
                pass

            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            resolved = socket.getaddrinfo(normalized_host, port, type=socket.SOCK_STREAM)
        except (OSError, ValueError) as e:
            return None, f"URL validation error: {str(e)}"

        for entry in resolved:
            address = entry[4][0]
            try:
                if _is_blocked_ip(address):
                    return None, "Blocked URL: private or local network addresses are not allowed."
            except ValueError:
                return None, "URL validation error: unresolved address."

        return url, None

    def scrape_headlines(self, url: str) -> List[Dict[str, str]]:
        """
        Scrapes headlines from a given URL.
        """
        if 'requests' not in sys.modules or 'bs4' not in sys.modules:
            return [{'headline': "Error: Please install 'requests' and 'beautifulsoup4' in your Python environment."}]

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            headline_tags = soup.find_all(['h1', 'h2', 'h3'])
            
            keywords = ['title', 'headline', 'heading', 'story-link', 'article-title']
            headline_classes = soup.find_all(class_=lambda x: x and any(c in str(x).lower() for c in keywords))
            
            article_titles = soup.find_all('a', class_=lambda x: x and any(c in str(x).lower() for c in keywords))
            
            all_potential_headlines = headline_tags + headline_classes + article_titles
            
            results = []
            seen_headlines = set()
            
            for tag in all_potential_headlines:
                text = tag.get_text().strip()
                
                text = " ".join(text.split())
                
                if not text or len(text) < 15 or text in seen_headlines:
                    continue
                    
                seen_headlines.add(text)
                results.append({'headline': text})
                
                if len(results) >= 15:
                    break
            
            return results
        
        except requests.exceptions.RequestException as e:
            return [{'headline': f"Network Error: {str(e)}"}]
        except Exception as e:
            return [{'headline': f"Scraping Error: {str(e)}"}]

    def scrape_news(self, url: str, seed: int):
        """
        Main function. 'seed' is used purely to force execution on each run.
        """
        url, validation_error = self.normalize_and_validate_url(url)
        if validation_error:
             return (validation_error,)

        print(f"[TextScraper] Scraping {url} (Run ID: {seed})")

        headlines = self.scrape_headlines(url)
        
        if not headlines:
            return (f"No headlines found at {url}. The site might use JavaScript rendering (SPA) or block bots.",)
        
        output_text = ""
        for item in headlines:
            output_text += f"{item['headline']}\n" 
                    
        return (output_text,)
