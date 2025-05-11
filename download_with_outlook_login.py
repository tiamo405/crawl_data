from selenium import webdriver
from pywebcopy import save_webpage
import time
import os

options = webdriver.ChromeOptions()
# Tuỳ chọn: giữ trình duyệt mở sau khi script kết thúc
options.add_experimental_option("detach", True)

driver = webdriver.Chrome(options=options)
driver.get("https://tinhte.vn/")  # 👉 thay bằng trang bạn muốn tải

print("⏳ Hãy đăng nhập thủ công và nhấn Enter khi hoàn tất...")
input()

time.sleep(3)  # đợi trang load kỹ
url = driver.current_url
folder = os.path.join(os.getcwd(), "saved_site")

# Tải toàn bộ trang web hiện tại
save_webpage(
    url=url,
    project_folder=folder,
    open_in_browser=False,
    delay=1,
)

print(f"✅ Trang đã được lưu vào {folder}")
