import json
import multiprocessing
import random
import time
import traceback
from pathlib import Path
from filelock import FileLock
from loguru import logger
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
from loguru import logger

STORAGE_PATH_BASE = 'storage'
URLS = {}
DEFAULT_CHROMEDRIVER_PATH = '/Users/anthonyf/Desktop/Tools/chromedriver/chromedriver'
DEFAULT_CHROMEDRIVER_VERSION = 133


class ZipcodeQueryCrawl:
    def __init__(self, if_headless=True, base_save_dir=None):

        if isinstance(base_save_dir, str):
            self.base_save_dir = Path(base_save_dir)
        elif isinstance(base_save_dir, Path):
            self.base_save_dir = base_save_dir
        else:
            self.base_save_dir = Path(STORAGE_PATH_BASE)

        self.if_headless = if_headless
        self.driver = None
        self.state_abbreviations = [
            'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
            'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
            'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
            'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
            'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY'
        ]


    def create_driver(self, if_headless=None):
        if not if_headless:
            if_headless = self.if_headless
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
        # # 设置文件下载路径
        # prefs = {
        #     "download.default_directory": str(self.base_save_dir),
        #     "download.prompt_for_download": False,  # 不提示保存对话框
        #     "download.directory_upgrade": True,  # 启用新的下载目录管理
        #     "safebrowsing.enabled": False,  # 禁用安全浏览功能
        #     "profile.default_content_setting_values.automatic_downloads": 1  # 允许自动下载
        # }
        # chrome_options.add_experimental_option("prefs", prefs)
        driver = uc.Chrome(options=chrome_options,
                           driver_executable_path=DEFAULT_CHROMEDRIVER_PATH,
                           version_main=DEFAULT_CHROMEDRIVER_VERSION
                           )
        driver.execute_cdp_cmd(
            "Network.setUserAgentOverride",
            {
                "userAgent": driver.execute_script(
                    "return navigator.userAgent"
                ).replace("Headless", "")
            },
        )
        return driver

    def get_state_random_address(self, state_abbr: str):
        driver = self.create_driver()
        try:
            url = f'https://{state_abbr.lower()}.postcodebase.com/randomaddress'
            driver.get(url)
            time.sleep(1)
            driver.get(url)
            all_address_ele_list = WebDriverWait(driver, 40).until(
                EC.presence_of_all_elements_located((By.XPATH, "//*[@class='list_bg']//span")))
            all_address_list = [i.get_attribute('data-clipboard-text') for i in all_address_ele_list]
            driver.quit()
            logger.success(f"Get {all_address_list}")
            return all_address_list
        except Exception as e:
            logger.error(f"Failed to fetch: {traceback.print_exc()}")
            driver.quit()
            return []

    def fetch_addresses_for_state(self, state_target):
        state, target_num = state_target
        existing_data = self.load_existing_data()
        addresses = existing_data.get(state, [])
        while len(addresses) < target_num:
            logger.info(f"Fetching more addresses for {state}. Current count: {len(addresses)}")
            new_addresses = self.get_state_random_address(state)
            addresses.extend(new_addresses)
            # 更新进度
            self.save_data({state: addresses}, state)
        logger.success(f"Completed fetching addresses for {state}")
        return state, addresses

    def load_existing_data(self, storage_file='addresses.json'):
        if Path(storage_file).exists():
            with open(storage_file, 'r') as f:
                return json.load(f)
        return {}

    def save_data(self, data, state, storage_file='addresses.json'):
        lock = FileLock(f"{storage_file}.lock")
        with lock:
            try:
                existing_data = self.load_existing_data(storage_file)
            except json.JSONDecodeError:
                existing_data = {}
            existing_data[state] = data.get(state, [])
            with open(storage_file, 'w') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)

    def main(self, target_num=9, states=None):
        existing_data = self.load_existing_data()
        states_to_fetch = self.state_abbreviations if not states else states
        random.shuffle(states_to_fetch)
        with multiprocessing.Pool(processes=8) as pool:
            results = pool.map(self.fetch_addresses_for_state, [(state, target_num) for state in states_to_fetch])

        final_data = {state: addresses for state, addresses in results}

        # 合并新旧数据
        for state, addresses in existing_data.items():
            if state not in final_data:
                final_data[state] = addresses

        self.save_data(final_data, None)  # 保存最终完整数据
        return final_data


if __name__ == "__main__":
    ins = ZipcodeQueryCrawl(if_headless=True)
    ins.main(3000)
