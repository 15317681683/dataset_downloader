import json
import os
import random
import time
import pickle

import requests
import tqdm
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
from loguru import logger

STORAGE_PATH_BASE = 'D:\datasets\hyperai'
URL = 'https://hyper.ai/datasets'
DEFAULT_CHROMEDRIVER_PATH = 'W:\Personal_Project\grained_ai\projects\paper_doi_helper\src\chromedriver.exe'
DEFAULT_CHROMEDRIVER_VERSION = 129
TOPIC_URL = 'https://www.reddit.com/search/?q=datasets&cId=4ddb93bc-c10c-4b12-a9c2-96f5bee530c6'


def if_flag_element_exists(driver_instance, flag_element_xpath, endpoint=None, timeout=30):
    if endpoint:
        driver_instance.get(endpoint)
    try:
        WebDriverWait(driver_instance, timeout, 0.1).until(
            EC.presence_of_element_located((By.XPATH, flag_element_xpath))
        )
        return True
    except:
        return False


class RedditTopic:
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
                                version_main=DEFAULT_CHROMEDRIVER_VERSION)
        self.driver.execute_cdp_cmd(
            "Network.setUserAgentOverride",
            {
                "userAgent": self.driver.execute_script(
                    "return navigator.userAgent"
                ).replace("Headless", "")
            },
        )

    def save_cookies(self, file_path='reddit_cookies'):
        """
        保存当前浏览器会话的 cookies 到指定文件
        :param file_path: 保存 cookies 的文件路径
        """
        try:
            cookies = self.driver.get_cookies()
            with open(file_path, 'wb') as file:
                pickle.dump(cookies, file)
            print(f"Cookies 已保存到 {file_path}")
        except Exception as e:
            print(f"保存 cookies 时发生错误: {e}")

    def load_cookies(self, file_path='reddit_cookies'):
        """
        从指定文件加载 cookies 到当前浏览器会话
        :param file_path: 保存 cookies 的文件路径
        """
        try:
            with open(file_path, 'rb') as file:
                cookies = pickle.load(file)
            for cookie in cookies:
                # 注意：有些 cookies 可能包含 'expiry' 键，但不是所有浏览器都支持，所以这里删除它
                if 'expiry' in cookie:
                    del cookie['expiry']
                self.driver.add_cookie(cookie)
            print(f"Cookies 已从 {file_path} 加载")
        except Exception as e:
            print(f"加载 cookies 时发生错误: {e}")

    def crawl_url(self, url, maximum_num=10000):
        self.driver.get(url)
        self.load_cookies()
        self.driver.get(url)
        last_id = 0
        all_cards_details = {}
        if_stop = False
        while 1:
            logger.info("Starts to scroll down.")
            self.driver.execute_script("var q=document.documentElement.scrollTop=100000")
            time.sleep(random.randint(1, 5))
            current_cards = self.driver.find_elements(By.XPATH, '//*[@data-testid="search-post"]')
            if not current_cards:
                logger.debug("No more current card on page. Break")
                break
            if if_flag_element_exists(self.driver, "//*[text()='无更多结果']", timeout=10):
                logger.debug("Hit end of the page. Break")
                break
            for card in tqdm.tqdm(current_cards[last_id:]):
                try:
                    card_details = card.text
                    card_href = card.find_element(By.XPATH, './/a').get_attribute('href')
                    all_cards_details[card_href] = card_details
                except:
                    logger.error("Failed to get card details")

                last_id += 1
                if maximum_num and len(all_cards_details.keys()) >= maximum_num:
                    logger.debug(f"Reach maximum card number. Current card num: {len(current_cards)}")
                    if_stop = True
                    break
                if last_id > len(current_cards):
                    logger.debug("No more current card on page. Break")
                    if_stop = True
                    break

            with open('topic_results.json', 'w', encoding='utf-8') as f:
                json.dump(all_cards_details, f, indent=2, ensure_ascii=False)
            if if_stop:
                logger.debug(f"Reach maximum card number. Current card num: {len(current_cards)}")
                break

        print("HERE")


if __name__ == "__main__":
    ins = RedditTopic(False)
    ins.crawl_url(TOPIC_URL)
