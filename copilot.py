from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import os
import time
import requests
from urllib.parse import urljoin, urlparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(levelname)s - %(message)s')

class PortalCrawler:
    def __init__(self, base_url):
        self.base_url = base_url
        self.domain = urlparse(base_url).netloc
        self.visited_urls = set()
        self.to_visit = set()
        self.driver = None
        self.output_dir = "crawled_data_copilot"
        
        # Create output directories
        self.create_directories()
        
    def create_directories(self):
        """Create necessary directories for storing crawled data"""
        for dir_name in ['html', 'css', 'js', 'images']:
            os.makedirs(os.path.join(self.output_dir, dir_name), exist_ok=True)
            
    def setup_driver(self):
        """Initialize Chrome WebDriver"""
        options = webdriver.ChromeOptions()
        service = Service()
        self.driver = webdriver.Chrome(service=service, options=options)
        
    def save_file(self, url, file_type):
        """Download and save a file"""
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                logging.warning(f"Failed to download {url}, status: {response.status_code}")
                return
                
            parsed_url = urlparse(url)
            filename = os.path.basename(parsed_url.path)
            
            # Handle empty filenames
            if not filename:
                filename = "index.html" if file_type == "html" else f"unknown.{file_type}"
                
            # Save file to appropriate directory
            file_path = os.path.join(self.output_dir, file_type, filename)
            with open(file_path, 'wb') as f:
                f.write(response.content)
            logging.info(f"Saved {file_type}: {filename}")
            
        except Exception as e:
            logging.error(f"Error downloading {url}: {e}")
    
    def save_current_page(self):
        """Save current page HTML"""
        current_url = self.driver.current_url
        parsed_url = urlparse(current_url)
        path = parsed_url.path.strip('/')
        
        # Create a filename based on the URL path
        if not path:
            filename = "index.html"
        else:
            filename = path.replace('/', '_')
            if not filename.endswith('.html'):
                filename += ".html"
        
        file_path = os.path.join(self.output_dir, 'html', filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(self.driver.page_source)
        logging.info(f"Saved page: {filename}")
        
    def extract_resources(self):
        """Extract and save CSS and JS resources from the current page"""
        # Get CSS files
        css_links = self.driver.find_elements(By.CSS_SELECTOR, "link[rel='stylesheet']")
        for link in css_links:
            href = link.get_attribute('href')
            if href:
                self.save_file(href, 'css')
        
        # Get JS files
        scripts = self.driver.find_elements(By.TAG_NAME, "script")
        for script in scripts:
            src = script.get_attribute('src')
            if src:
                self.save_file(src, 'js')
                
        # Get images
        images = self.driver.find_elements(By.TAG_NAME, "img")
        for img in images:
            src = img.get_attribute('src')
            if src:
                self.save_file(src, 'images')
    
    def find_links_in_hover_menus(self):
        """Find links inside hover/dropdown menus"""
        # Elements that might contain hover menus
        hover_selectors = [
            ".nav-item", 
            ".dropdown", 
            "[class*='menu']", 
            "li", 
            "[class*='nav']"
        ]
        
        links = set()
        
        # Try hovering over potential menu elements
        for selector in hover_selectors:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            for element in elements:
                try:
                    # Hover over element
                    actions = ActionChains(self.driver)
                    actions.move_to_element(element).perform()
                    time.sleep(0.5)  # Wait for submenu to appear
                    
                    # Find links that appeared
                    menu_links = self.driver.find_elements(By.TAG_NAME, "a")
                    for link in menu_links:
                        href = link.get_attribute('href')
                        if href and self.domain in href:
                            links.add(href)
                except:
                    continue
        
        return links
    
    def extract_all_links(self):
        """Extract all links from the current page including hover menus"""
        links = set()
        
        # First get regular links
        all_links = self.driver.find_elements(By.TAG_NAME, "a")
        for link in all_links:
            href = link.get_attribute('href')
            if href and self.domain in href:
                links.add(href)
        
        # Then get hover menu links
        hover_links = self.find_links_in_hover_menus()
        links.update(hover_links)
        
        return links
    
    def crawl(self):
        """Main crawling function"""
        self.setup_driver()
        
        try:
            # Open the login page and wait for manual login
            self.driver.get(self.base_url)
            logging.info("Please log in manually. Press Enter after successful login.")
            input()
            
            # Start crawling from the base URL
            self.driver.get(self.base_url)
            self.to_visit.add(self.base_url)
            
            while self.to_visit:
                url = self.to_visit.pop()
                if url in self.visited_urls:
                    continue
                    
                logging.info(f"Visiting: {url}")
                try:
                    self.driver.get(url)
                    
                    # Wait for page to load
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                    time.sleep(1)
                    
                    # Save current page and its resources
                    self.save_current_page()
                    self.extract_resources()
                    
                    # Find new links to visit
                    new_links = self.extract_all_links()
                    for link in new_links:
                        if link not in self.visited_urls:
                            self.to_visit.add(link)
                    
                    # Mark as visited
                    self.visited_urls.add(url)
                    
                    # Small delay to avoid overloading the server
                    time.sleep(1)
                    
                except Exception as e:
                    logging.error(f"Error processing {url}: {e}")
                    self.visited_urls.add(url)  # Mark as visited to avoid retrying
                    
            logging.info(f"Crawling completed. Visited {len(self.visited_urls)} URLs.")
            
        finally:
            if self.driver:
                self.driver.quit()

if __name__ == "__main__":
    crawler = PortalCrawler("https://portal.dieuquy.delivn.vn/")
    crawler.crawl()