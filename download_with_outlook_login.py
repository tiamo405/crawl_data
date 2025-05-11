from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import time
import os
import urllib.parse

# Cấu hình trình duyệt
chrome_options = Options()
chrome_options.add_argument("--start-maximized")  # mở toàn màn hình

driver = webdriver.Chrome(service=Service(), options=chrome_options)

# 1. Mở trang cần đăng nhập
target_url = "https://portal.dieuquy.delivn.vn/"
driver.get(target_url)

print(">>> Vui lòng tự đăng nhập trong trình duyệt rồi nhấn Enter trong terminal khi xong...")
input(">>> Đã đăng nhập? Nhấn Enter để tiếp tục...")

# 2. Tìm tất cả liên kết nội bộ trên trang
anchors = driver.find_elements(By.TAG_NAME, "a")
internal_links = set()

for a in anchors:
    href = a.get_attribute("href")
    if href and target_url in href:  # lọc link nội bộ
        internal_links.add(href)

print(f"✅ Tìm thấy {len(internal_links)} trang nội bộ để tải.")

# 3. Tạo thư mục lưu
os.makedirs("downloaded_pages", exist_ok=True)

# 4. Tải từng trang HTML và lưu với tên URL
for link in internal_links:
    try:
        driver.get(link)
        time.sleep(2)  # đợi trang load

        html = driver.page_source
        parsed = urllib.parse.urlparse(link)

        # Lấy tên file từ đường dẫn (bỏ http:// hoặc https://)
        file_path = parsed.path.strip("/").replace("/", "_")  # thay thế dấu / bằng _
        filename = f"{file_path}.html" if file_path else "index.html"  # nếu file_path rỗng, đặt tên là index.html

        # Lưu HTML vào file
        with open(os.path.join("downloaded_pages", filename), "w", encoding="utf-8") as f:
            f.write(html)

        print(f"✔ Đã lưu {filename} từ {parsed.path}")
    except Exception as e:
        print(f"⚠️ Lỗi với {link}: {e}")

# Đóng trình duyệt
driver.quit()
print("✅ Hoàn tất tải các trang HTML.")
