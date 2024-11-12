import json
import random
import time

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
from loguru import logger

STORAGE_PATH_BASE = 'D:\datasets\corvee'
URL = 'https://corvee.com/tax-planning-strategies/?utm_source=google&utm_medium=search&utm_campaign=brandedcorvee'
DEFAULT_CHROMEDRIVER_PATH = 'W:\Personal_Project\grained_ai\projects\paper_doi_helper\src\chromedriver.exe'
DEFAULT_CHROMEDRIVER_VERSION = 129


class HyperAiCrawl:
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
        chrome_options.add_argument('--blink-settings=imagesEnabled=false')  # 禁用图片
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')  # 禁用自动化控制特征
        # chrome_options.add_experimental_option('prefs', {'profile.managed_default_content_settings.javascript': 2})  # 禁用JavaScript
        chrome_options.add_argument('--incognito')  # 无痕模式
        chrome_options.page_load_strategy = 'eager'  # 设置页面加载策略

        self.driver = uc.Chrome(options=chrome_options,
                                driver_executable_path=DEFAULT_CHROMEDRIVER_PATH,
                                version_main=DEFAULT_CHROMEDRIVER_VERSION)
        self.driver.execute_cdp_cmd(
            "Network.setUserAgentOverride",
            {
                "userAgent": self.driver.execute_script(
                    "return navigator.userAgent"
                ).replace("Headless", "")
            },
        )

    def if_on_dataset_page(self):
        try:
            WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[@id="__next"]')))
            return True
        except:
            return False

    def get_current_page(self):
        page_element = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH,
                                                                                            "//button[contains(@class, 'hyperai-Pagination-control') and @data-active='true' and @aria-current='page']")))
        return int(page_element.text)

    def get_dataset_blocks(self):
        time.sleep(random.randint(5, 10))
        WebDriverWait(self.driver, 10).until(EC.presence_of_all_elements_located((By.XPATH,
                                                                                  "//a[contains(@class, 'hyperai-Card-root') and contains(@class, 'link')]")))
        block_elements = self.driver.find_elements(By.XPATH,
                                                   "//a[contains(@class, 'hyperai-Card-root') and contains(@class, 'link')]")
        datasets_infos = {i.get_attribute('href'): i.text for i in block_elements}
        return datasets_infos

    def next_page(self):
        next_page_btn = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//*[@class='load-text']")))
        next_page_btn.click()

    def get_titles(self):
        self.driver.get(URL)
        while 1:
            try:
                self.next_page()
                time.sleep(random.randint(1, 5))
            except:
                break
        blocks = self.driver.find_elements(By.XPATH, "//li[@class='strategy']")
        res = [i.text for i in blocks]
        with open('corvee_all_raw.json', 'w', encoding='utf-8') as f:
            json.dump(res, indent=2, ensure_ascii=False)

    def main(self):
        pass



if __name__ == "__main__":
    ins = HyperAiCrawl(False)
    ins.main()
