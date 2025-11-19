import requests
from bs4 import BeautifulSoup
from typing import List, Dict

class TextScraper:
    """
    A ComfyUI node that scrapes news headlines from a given URL and outputs them as formatted text.
    """
    
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # 修改：改為單一的字串輸入框
                # ComfyUI 前端通常會保留此欄位上次輸入的值，且支援原生的數值管理功能
                "url": ("STRING", {
                    "default": "https://news.ycombinator.com",
                    "multiline": False
                }),
            }
        }

    RETURN_TYPES = ("STRING",)
    # 修復：將原本錯誤的 "scrape_text" 修正為正確的函數名稱 "scrape_news"
    FUNCTION = "scrape_news"
    CATEGORY = "Text Processor"

    def scrape_headlines(self, url: str) -> List[Dict[str, str]]:
        """
        Scrapes headlines from a given URL.
        Helper function containing the scraping logic.
        """
        try:
            # Fetch the webpage
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(url, headers=headers, timeout=10) # Added timeout for safety
            response.raise_for_status()
            
            # Parse the HTML content
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find headlines using various common patterns
            # Method 1: Look for common headline tags
            headline_tags = soup.find_all(['h1', 'h2', 'h3', 'h4'])
            
            # Method 2: Look for elements with common headline classes
            headline_classes = soup.find_all(class_=lambda x: x and any(c in str(x).lower() for c in ['title', 'headline', 'heading']))
            
            # Method 3: Look for article titles
            article_titles = soup.find_all('a', class_=lambda x: x and any(c in str(x).lower() for c in ['title', 'headline', 'link']))
            
            # Combine all findings
            all_potential_headlines = headline_tags + headline_classes + article_titles
            
            # Process each headline
            results = []
            seen_headlines = set()  # To avoid duplicates
            
            for tag in all_potential_headlines:
                # Get the headline text and clean it
                headline = tag.get_text().strip()
                
                # Skip if headline is too short or we've seen it before
                if not headline or len(headline) < 10 or headline in seen_headlines:
                    continue
                    
                seen_headlines.add(headline)
                results.append({
                    'headline': headline
                })
                
                # Limit to top 10 headlines to avoid overwhelming output
                if len(results) >= 10:
                    break
            
            return results
        
        except Exception as e:
            print(f"An error occurred while scraping: {str(e)}")
            return []

    def scrape_news(self, url: str):
        """
        Main function that processes the URL and returns formatted text output.
        """
        # 簡單的防呆檢查
        if not url.strip():
             return ("Please enter a valid URL.",)
        
        # 如果沒有 http 前綴，嘗試自動補全（可選，視需求而定，這裡建議嚴謹一點比較好，但為了方便先不做強制轉換，只做檢查）
        if not url.startswith(("http://", "https://")):
            # 為了使用者體驗，若忘記打協定，自動補上 https
            url = "https://" + url

        headlines = self.scrape_headlines(url)
        
        if not headlines:
            return (f"No headlines found at {url}. The website might be blocking scraping attempts or the structure is complex.",)
        
        # Format the output text
        output_text = ""
        for item in headlines:
            output_text += f"{item['headline']}.\n"
                    
        return (output_text,)

NODE_CLASS_MAPPINGS = {
    "TextScraper": TextScraper
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "TextScraper": "Text Scraper Node"
}