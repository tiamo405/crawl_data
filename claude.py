import os
import time
import requests
import urllib.parse
import re
import json
from urllib.parse import urljoin
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from bs4 import BeautifulSoup

class WebCrawler:
    def __init__(self, base_url, output_dir):
        self.base_url = base_url
        self.output_dir = output_dir
        self.visited_urls = set()
        self.pending_urls = set()
        self.failed_urls = set()
        self.cookies = {}
        self.page_data = {}  # Store raw page data for staticalization
        
        # Ensure output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        # Initialize the Chrome driver
        chrome_options = Options()
        chrome_options.add_argument("--window-size=1920,1080")
        # Uncomment the next line if you want to run headless (without UI)
        # chrome_options.add_argument("--headless")
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.actions = ActionChains(self.driver)
        
    def wait_for_login(self):
        """Wait for user to manually login and capture cookies"""
        self.driver.get(self.base_url)
        print("Please login manually...")
        input("Press Enter when logged in successfully...")
        print("Continuing with crawling...")
        
        # Save cookies after login
        selenium_cookies = self.driver.get_cookies()
        for cookie in selenium_cookies:
            self.cookies[cookie['name']] = cookie['value']
            
        print(f"Captured {len(self.cookies)} cookies")
        
    def get_filename_from_url(self, url, content_type=None):
        """Generate a filename from URL"""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        
        # If path is empty or just a slash, use index.html
        if not path or path == '/':
            return 'index.html'
            
        # Remove leading and trailing slashes
        path = path.strip('/')
        
        # If path ends with a slash, append index.html
        if path.endswith('/'):
            path = path + 'index.html'
        elif '.' not in os.path.basename(path):
            # If path doesn't have an extension, add appropriate one
            if content_type:
                if 'text/html' in content_type:
                    path = path + '.html'
                elif 'text/css' in content_type:
                    path = path + '.css'
                elif 'javascript' in content_type:
                    path = path + '.js'
                elif 'image/' in content_type:
                    ext = content_type.split('/')[-1]
                    path = path + '.' + ext
            else:
                # Default to html if content type is unknown
                path = path + '.html'
                
        # Replace special characters that might be problematic in filenames
        path = path.replace('?', '_').replace('&', '_').replace('=', '-')
        
        return path
    
    def save_file(self, url, content, content_type):
        """Save content to file"""
        # Get appropriate path for the file
        file_path = self.get_filename_from_url(url, content_type)
        
        # Create directory structure if needed
        dir_path = os.path.dirname(file_path)
        if dir_path:
            full_dir_path = os.path.join(self.output_dir, dir_path)
            if not os.path.exists(full_dir_path):
                os.makedirs(full_dir_path)
        
        # Full path to save the file
        full_path = os.path.join(self.output_dir, file_path)
        
        # Save the file
        with open(full_path, 'wb') as f:
            f.write(content)
            
        print(f"Saved: {full_path}")
        return file_path
    
    def is_same_domain(self, url):
        """Check if URL belongs to the same domain"""
        parsed_base = urllib.parse.urlparse(self.base_url)
        parsed_url = urllib.parse.urlparse(url)
        return parsed_url.netloc == parsed_base.netloc
    
    def normalize_url(self, url):
        """Normalize URL"""
        # Handle relative URLs
        if not url.startswith(('http://', 'https://')):
            if url.startswith('/'):
                base_parts = urllib.parse.urlparse(self.base_url)
                url = f"{base_parts.scheme}://{base_parts.netloc}{url}"
            else:
                url = urllib.parse.urljoin(self.base_url, url)
                
        # Remove fragments
        url = url.split('#')[0]
        
        # Ensure URL ends with / if it's a directory
        if not url.split('?')[0].split('#')[0].endswith('/') and '.' not in url.split('/')[-1]:
            url += '/'
            
        return url
    
    def download_resource(self, url):
        """Download a resource (CSS, JS, images)"""
        try:
            if url in self.visited_urls:
                return None
                
            # Normalize URL
            url = self.normalize_url(url)
            
            # Only download resources from the same domain
            if not self.is_same_domain(url):
                return None
                
            # Download the resource with cookies
            response = requests.get(url, cookies=self.cookies, timeout=10)
            content_type = response.headers.get('Content-Type', '')
            
            # Save the file
            local_path = self.save_file(url, response.content, content_type)
            
            # Mark as visited
            self.visited_urls.add(url)
            
            return local_path
            
        except Exception as e:
            print(f"Error downloading resource {url}: {e}")
            self.failed_urls.add(url)
            return None
            
    def process_pages_to_static(self):
        """Process all pages to create a static version without login requirement"""
        print("\nProcessing pages to create static versions...")
        
        # First, extract all JavaScript and add to a list to be included in all pages
        all_js_files = set()
        for url, data in self.page_data.items():
            for resource in data['resources']:
                if resource['local_path'].endswith('.js'):
                    all_js_files.add(resource['local_path'])
        
        # Also create a list of all CSS files
        all_css_files = set()
        for url, data in self.page_data.items():
            for resource in data['resources']:
                if resource['local_path'].endswith('.css'):
                    all_css_files.add(resource['local_path'])
        
        # Process each page to make it static
        for url, data in self.page_data.items():
            try:
                html = data['html']
                local_path = data['local_path']
                file_path = os.path.join(self.output_dir, local_path)
                
                # Parse HTML
                soup = BeautifulSoup(html, 'html.parser')
                
                # Remove any login forms or authentication scripts
                self.remove_auth_elements(soup)
                
                # Fix all relative URLs in the page
                self.fix_relative_urls(soup, url)
                
                # Ensure all JS files are included
                self.ensure_all_scripts_included(soup, all_js_files)
                
                # Ensure all CSS files are included
                self.ensure_all_css_included(soup, all_css_files)
                
                # Remove any script that contains 'login', 'auth', 'authentication', etc.
                self.remove_auth_scripts(soup)
                
                # Save the processed HTML
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(str(soup))
                    
                print(f"Processed static version of {local_path}")
                
            except Exception as e:
                print(f"Error processing static version of {url}: {e}")
                
    def remove_auth_elements(self, soup):
        """Remove authentication-related elements"""
        # Remove forms that might be login forms
        for form in soup.find_all('form'):
            form_html = str(form).lower()
            if any(keyword in form_html for keyword in ['login', 'signin', 'sign in', 'username', 'password']):
                form.decompose()
        
        # Remove elements with IDs or classes related to login
        for element in soup.find_all(class_=lambda c: c and any(keyword in c.lower() for keyword in ['login', 'signin', 'auth'])):
            element.decompose()
            
        for element in soup.find_all(id=lambda i: i and any(keyword in i.lower() for keyword in ['login', 'signin', 'auth'])):
            element.decompose()
            
    def remove_auth_scripts(self, soup):
        """Remove scripts related to authentication"""
        for script in soup.find_all('script'):
            if script.string:
                script_text = script.string.lower()
                if any(keyword in script_text for keyword in ['login', 'auth', 'token', 'jwt', 'session']):
                    script.decompose()
                    
    def fix_relative_urls(self, soup, base_url):
        """Fix all relative URLs in the page"""
        # Fix links (a tags)
        for a in soup.find_all('a', href=True):
            href = a['href']
            if not href.startswith(('http://', 'https://', '#', 'javascript:')):
                a['href'] = urljoin(base_url, href)
                
                # Convert to local file path if it's in our visited URLs
                local_url = self.normalize_url(a['href'])
                if local_url in self.visited_urls:
                    local_path = self.get_filename_from_url(local_url)
                    a['href'] = '/' + local_path
        
        # Fix images
        for img in soup.find_all('img', src=True):
            src = img['src']
            if not src.startswith(('http://', 'https://', 'data:', '#')):
                img['src'] = urljoin(base_url, src)
                
        # Fix css links
        for link in soup.find_all('link', href=True):
            href = link['href']
            if not href.startswith(('http://', 'https://', '#')):
                link['href'] = urljoin(base_url, href)
                
        # Fix scripts
        for script in soup.find_all('script', src=True):
            src = script['src']
            if not src.startswith(('http://', 'https://', '#')):
                script['src'] = urljoin(base_url, src)
                
    def ensure_all_scripts_included(self, soup, js_files):
        """Ensure all JavaScript files are included in the page"""
        head = soup.find('head')
        if not head:
            head = soup.find('html')
            if not head:
                return
        
        # Add all JS files
        for js_file in js_files:
            # Check if the script is already included
            already_included = False
            for script in soup.find_all('script', src=True):
                if js_file in script['src']:
                    already_included = True
                    break
                    
            if not already_included:
                new_script = soup.new_tag('script')
                new_script['src'] = '/' + js_file
                head.append(new_script)
                
    def ensure_all_css_included(self, soup, css_files):
        """Ensure all CSS files are included in the page"""
        head = soup.find('head')
        if not head:
            head = soup.new_tag('head')
            html = soup.find('html')
            if html:
                html.insert(0, head)
            else:
                return
        
        # Add all CSS files
        for css_file in css_files:
            # Check if the CSS is already included
            already_included = False
            for link in soup.find_all('link', rel="stylesheet"):
                if css_file in link.get('href', ''):
                    already_included = True
                    break
                    
            if not already_included:
                new_link = soup.new_tag('link')
                new_link['rel'] = 'stylesheet'
                new_link['href'] = '/' + css_file
                head.append(new_link)
    
    def get_page_resources(self, html, page_url):
        """Extract CSS, JS and image resources from HTML"""
        soup = BeautifulSoup(html, 'html.parser')
        resources = []
        
        # Extract CSS
        for link in soup.find_all('link', rel='stylesheet'):
            if 'href' in link.attrs:
                href = link['href']
                if href and not href.startswith(('data:', 'javascript:')):
                    resources.append(href)
                    
        # Extract JS
        for script in soup.find_all('script'):
            if 'src' in script.attrs:
                src = script['src']
                if src and not src.startswith(('data:', 'javascript:')):
                    resources.append(src)
                    
        # Extract images
        for img in soup.find_all('img'):
            if 'src' in img.attrs:
                src = img['src']
                if src and not src.startswith(('data:', 'javascript:')):
                    resources.append(src)
                    
        # Extract resources from style attributes
        for tag in soup.find_all(style=True):
            style = tag['style']
            urls = self.extract_urls_from_style(style)
            resources.extend(urls)
            
        # Extract resources from inline style tags
        for style in soup.find_all('style'):
            urls = self.extract_urls_from_style(style.string)
            resources.extend(urls)
            
        # Normalize URLs
        normalized_resources = []
        for resource in resources:
            normalized = self.normalize_url(resource)
            normalized_resources.append(normalized)
            
        return normalized_resources
    
    def extract_urls_from_style(self, style_text):
        """Extract URLs from CSS style text"""
        if not style_text:
            return []
            
        urls = []
        # Extract URLs from url() functions
        import re
        url_pattern = r'url\([\'"]?([^\'"]+)[\'"]?\)'
        matches = re.findall(url_pattern, style_text)
        urls.extend(matches)
        
        return urls
    
    def hover_menu_items(self, url):
        """Find and hover over menu items to reveal dropdowns"""
        try:
            # Wait for page to load
            time.sleep(2)
            
            # Find all potential menu items
            menu_items = self.driver.find_elements(By.CSS_SELECTOR, 
                '.nav-link, .menu-item, .dropdown-toggle, .navbar-item, li.nav-item, .has-dropdown')
            
            for item in menu_items:
                try:
                    # Move to element to trigger dropdown
                    self.actions.move_to_element(item).perform()
                    time.sleep(0.5)
                    
                    # Look for dropdown menus that appear
                    dropdowns = self.driver.find_elements(By.CSS_SELECTOR, 
                        '.dropdown-menu, .submenu, .dropdown-content, .sub-menu')
                    
                    for dropdown in dropdowns:
                        if dropdown.is_displayed():
                            # Find all links in the dropdown
                            links = dropdown.find_elements(By.TAG_NAME, 'a')
                            for link in links:
                                href = link.get_attribute('href')
                                if href and self.is_same_domain(href):
                                    self.pending_urls.add(href)
                                    print(f"Found dropdown link: {href}")
                except StaleElementReferenceException:
                    continue
                except Exception as e:
                    print(f"Error hovering menu item: {e}")
                    
        except Exception as e:
            print(f"Error handling dropdowns: {e}")
    
    def crawl_page(self, url):
        """Crawl a single page"""
        if url in self.visited_urls:
            return
            
        try:
            print(f"Crawling: {url}")
            self.driver.get(url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Get page source
            html = self.driver.page_source
            
            # Store in page_data for post-processing
            self.page_data[url] = {
                'html': html,
                'title': self.driver.title,
                'resources': []
            }
            
            # Extract resources
            resources = self.get_page_resources(html, url)
            resource_map = {}  # Map original URLs to local paths
            
            for resource in resources:
                local_path = self.download_resource(resource)
                if local_path:
                    resource_map[resource] = local_path
                    self.page_data[url]['resources'].append({
                        'url': resource,
                        'local_path': local_path
                    })
            
            # Save the page after resources are downloaded
            saved_path = self.save_file(url, html.encode('utf-8'), 'text/html')
            self.page_data[url]['local_path'] = saved_path
            
            # Mark as visited
            self.visited_urls.add(url)
                
            # Find links on the page
            links = self.driver.find_elements(By.TAG_NAME, 'a')
            for link in links:
                try:
                    href = link.get_attribute('href')
                    if href and self.is_same_domain(href) and href not in self.visited_urls:
                        self.pending_urls.add(href)
                except Exception as e:
                    print(f"Error processing link: {e}")
                    
            # Handle dropdown menus
            self.hover_menu_items(url)
            
        except Exception as e:
            print(f"Error crawling {url}: {e}")
            self.failed_urls.add(url)
    
    def crawl(self):
        """Main crawling process"""
        try:
            # Wait for manual login
            self.wait_for_login()
            
            # Start with the base URL
            self.pending_urls.add(self.base_url)
            
            # Crawl while there are pending URLs
            while self.pending_urls:
                url = self.pending_urls.pop()
                if url not in self.visited_urls:
                    self.crawl_page(url)
                    # Sleep to avoid overloading the server
                    time.sleep(1)
                    
            print(f"Crawling complete. Visited {len(self.visited_urls)} pages.")
            print(f"Failed to crawl {len(self.failed_urls)} pages.")
            
        finally:
            # Cleanup
            self.driver.quit()
            
def create_web_server_file(output_dir):
    """Create a Python script to serve the downloaded website locally"""
    server_script = '''
import http.server
import socketserver
import os
import sys

# Get port from command line or use default
if len(sys.argv) > 1:
    try:
        PORT = int(sys.argv[1])
    except ValueError:
        PORT = 8000
else:
    PORT = 8000

class MyHttpRequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS to allow cross-origin requests
        self.send_header('Access-Control-Allow-Origin', '*')
        http.server.SimpleHTTPRequestHandler.end_headers(self)
        
    def do_GET(self):
        # Special case for root URL
        if self.path == '/' or self.path == '':
            self.path = '/index.html'
            
        # Remove any query parameters
        self.path = self.path.split('?')[0]
        
        # Try to serve the file
        return http.server.SimpleHTTPRequestHandler.do_GET(self)

# Change to the directory of this script
os.chdir(os.path.dirname(os.path.abspath(__file__)))

Handler = MyHttpRequestHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"Serving at http://localhost:{PORT}")
    print("Press Ctrl+C to stop the server")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\\nServer stopped.")
        httpd.shutdown()
'''
    
    # Save the server script
    server_file_path = os.path.join(output_dir, 'serve_website.py')
    with open(server_file_path, 'w') as f:
        f.write(server_script)
    
    print(f"Created web server script at {server_file_path}")
    print("To run the local web server, navigate to the 'crawled_data' directory and run:")
    print("    python serve_website.py")
    print("Then open http://localhost:8000 in your web browser")
    
def create_site_map(output_dir, page_data):
    """Create a site map HTML file"""
    sitemap_html = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trang web tĩnh - Site Map</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
        }
        ul {
            padding-left: 20px;
        }
        li {
            margin-bottom: 10px;
        }
        a {
            color: #0066cc;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <h1>Sitemap - Trang web tĩnh</h1>
    <p>Danh sách các trang web đã tải về:</p>
    <ul>
'''
    
    # Add each page to the site map
    for url, data in page_data.items():
        title = data.get('title', url)
        local_path = data.get('local_path', '')
        sitemap_html += f'        <li><a href="/{local_path}">{title}</a></li>\n'
    
    sitemap_html += '''
    </ul>
    <p>Để xem trang web, hãy chạy file <code>serve_website.py</code> và truy cập <code>http://localhost:8000</code>.</p>
</body>
</html>
'''
    
    # Save the site map
    sitemap_path = os.path.join(output_dir, 'sitemap.html')
    with open(sitemap_path, 'w', encoding='utf-8') as f:
        f.write(sitemap_html)
    
    print(f"Created site map at {sitemap_path}")

if __name__ == "__main__":
    base_url = "https://portal.dieuquy.delivn.vn/"
    output_dir = "crawled_data"
    
    crawler = WebCrawler(base_url, output_dir)
    crawler.crawl()
    
    # Process pages to create static versions
    crawler.process_pages_to_static()
    
    # Create site map
    create_site_map(output_dir, crawler.page_data)
    
    # Create web server file
    create_web_server_file(output_dir)
