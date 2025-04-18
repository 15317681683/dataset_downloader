import json
import os
import random
import time
from PIL import Image
from io import BytesIO

import requests
import tqdm
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
from loguru import logger
from webdriver_manager.chrome import ChromeDriverManager
STORAGE_PATH_BASE = '/Users/anthonyf/projects/grainedAI/dataset_downloader/scripts/pdfpro/storage'
URLS = {'main': 'https://pdfpro.us/app/designs/new'}
DEFAULT_CHROMEDRIVER_PATH = '/Users/anthonyf/Downloads/chromedriver-mac-x64/chromedriver'
DEFAULT_CHROMEDRIVER_VERSION = 131


class PDFProCrawl:
    def __init__(self, if_headless=True, base_save_dir=None):

        if isinstance(base_save_dir, str):
            self.base_save_dir = Path(base_save_dir)
        elif isinstance(base_save_dir, Path):
            self.base_save_dir = base_save_dir
        else:
            self.base_save_dir = Path(STORAGE_PATH_BASE)

        logger.warning("Will create a default driver instance.")
        chrome_options = Options()
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--lang=zh_CN.UTF-8")
        chrome_options.add_argument("--disable-dev-shm-usage")
        if if_headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument("--disable-popup-blocking")
        # chrome_options.add_argument('--blink-settings=imagesEnabled=false')  # 禁用图片
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')  # 禁用自动化控制特征
        # chrome_options.add_experimental_option('prefs', {'profile.managed_default_content_settings.javascript': 2})  # 禁用JavaScript
        chrome_options.add_argument('--incognito')  # 无痕模式
        chrome_options.page_load_strategy = 'eager'  # 设置页面加载策略
        # # 设置文件下载路径
        # prefs = {
        #     "download.default_directory": str(self.base_save_dir),
        #     "download.prompt_for_download": False,  # 不提示保存对话框
        #     "download.directory_upgrade": True,  # 启用新的下载目录管理
        #     "safebrowsing.enabled": False,  # 禁用安全浏览功能
        #     "profile.default_content_setting_values.automatic_downloads": 1  # 允许自动下载
        # }
        # chrome_options.add_experimental_option("prefs", prefs)
        self.driver = uc.Chrome(options=chrome_options,
                                driver_executable_path=DEFAULT_CHROMEDRIVER_PATH,
                                version_main=DEFAULT_CHROMEDRIVER_VERSION
                                )
        self.driver.execute_cdp_cmd(
            "Network.setUserAgentOverride",
            {
                "userAgent": self.driver.execute_script(
                    "return navigator.userAgent"
                ).replace("Headless", "")
            },
        )

    def login(self):
        self.driver.get(URLS['main'])
        while 1:
            # time.sleep(10)
            try:
                WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located((By.XPATH, '//*[contains(text(), "Login")]')))
            except:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located((By.XPATH, '//*[contains(text(), "Choose Template")]')))
                    logger.info("Login success")
                    break
                except:
                    raise Exception("Fail to load to login page.")

            email_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@id='email']")))
            password_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@id='password']")))
            email_input.send_keys('anthonyfanhaodi@gmail.com')
            password_input.send_keys('833020fan')
            submit = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Submit')]")))
            submit.click()
            logger.info("Try login")

    def get_all_templates(self):
        all_urls = []
        while 1:
            cur_page_idx = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//*[@tabindex='-1']"))).text
            logger.info(f"Currently on page {cur_page_idx}")
            logger.success(f"Crawled {len(all_urls)} urls")
            template_href_eles = WebDriverWait(self.driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@href, 'template')]")))
            template_hrefs = [i.get_attribute('href') for i in template_href_eles]
            all_urls.extend(template_hrefs)
            if cur_page_idx == '5':
                logger.success("Finished.")
                break
            next_page_btn = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//a[@rel='next']")))
            next_page_btn.click()
            time.sleep(3)
        return all_urls

    @staticmethod
    def download_image(image_url, storage_path):
        try:
            # 发送 GET 请求以获取图片数据
            response = requests.get(image_url, stream=True)
            response.raise_for_status()  # 检查响应是否成功
            with open(storage_path, "wb") as file:
                for chunk in response.iter_content(1024):
                    file.write(chunk)
            print(f"Image successfully downloaded to {storage_path}")
        except requests.exceptions.RequestException as e:
            print(f"Failed to download image: {e}")

    def crawl_image(self, url):
        template_name = url.split('/')[-1]
        storage_path = Path(STORAGE_PATH_BASE)/f"{template_name}.png"
        self.driver.get(url)
        image_ele = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, "//*[@class='detail-main']//*[@class='border-image']")))
        image_url = image_ele.get_attribute('src')
        self.download_image(image_url, storage_path)


    def main(self):
        self.login()
        all_urls = self.get_all_templates()
        for url in tqdm.tqdm(all_urls):
            self.crawl_image(url)
        # self.driver.get(URLS['main'])

if __name__ == "__main__":
    ins = PDFProCrawl(if_headless=False)
    ins.main()