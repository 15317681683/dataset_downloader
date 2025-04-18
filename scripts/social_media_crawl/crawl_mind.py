import glob
import json
import os
import random
import re
import shutil
import time
import pickle
import traceback
import copy
from PIL import Image
import io
import requests
import tqdm
from modules.youtube.retrieve_transcript import TranscriptRetrieve
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
from loguru import logger
from multiprocessing import Pool, cpu_count

STORAGE_PATH_BASE = 'storage'

URLS = {
    'main': "https://www.minds.com/newsfeed/subscriptions/for-you",
        "furry": "https://www.minds.com/discovery/search?q=%23furry&f=top&t=all",
        'gay': 'https://www.minds.com/discovery/search?q=%23gay&f=top&t=all',
        # 'elonmusk': "https://www.minds.com/discovery/search?q=%23elonmusk&f=top&t=all",
        'commercial': "https://www.minds.com/search?q=%23commercial&f=top&t=all",
        'friend': "https://www.minds.com/search?q=%23friend&f=top&t=all",
        'socialmedia': 'https://www.minds.com/search?q=%23socialmedia&f=top&t=all',
        'happy': 'https://www.minds.com/search?q=%23happy&f=top&t=all'
}

DEFAULT_CHROMEDRIVER_PATH = '/Users/anthonyf/Desktop/Tools/chromedriver/chromedriver'
DEFAULT_CHROMEDRIVER_VERSION = 133


class CrawlMind:
    def __init__(self, if_headless):
        self.if_headless = if_headless
        logger.info(f"Projects default if_headless={if_headless}")
        self.transcript_retriever = TranscriptRetrieve()

    def create_driver(self, if_headless=None):
        if not if_headless:
            if_headless = self.if_headless
        logger.warning("Will create a default driver instance.")
        chrome_options = Options()
        # chrome_options.add_argument("--disable-gpu")
        # chrome_options.add_argument("--lang=zh_CN.UTF-8")
        # chrome_options.add_argument("--disable-dev-shm-usage")
        if if_headless:
            chrome_options.add_argument('--headless')
        # chrome_options.add_argument("--disable-popup-blocking")
        # chrome_options.add_argument('--blink-settings=imagesEnabled=false')  # 禁用图片
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')  # 禁用自动化控制特征
        # chrome_options.add_argument('--incognito')  # 无痕模式
        # chrome_options.page_load_strategy = 'eager'  # 设置页面加载策略
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

    @staticmethod
    def save_cookies(driver, file_path):
        """
        将当前driver的cookies保存到指定路径的JSON文件中。

        :param driver: Selenium WebDriver实例
        :param file_path: Cookies保存的目标文件路径
        """
        # 获取所有cookies
        cookies = driver.get_cookies()

        # 将cookies写入到指定的文件中
        with open(file_path, 'w') as file:
            json.dump(cookies, file)
        logger.success(f"Cookies have been saved to {file_path}")

    @staticmethod
    def load_cookies(driver, file_path):
        """
        从指定路径的JSON文件中读取cookies并加载到当前driver中。

        :param driver: Selenium WebDriver实例
        :param file_path: 存储cookies的JSON文件路径
        """
        # 确保在加载cookies之前访问了相应的网站域
        driver.get(URLS['main'])  # 替换为目标网站

        # 从文件中读取cookies
        with open(file_path, 'r') as file:
            cookies = json.load(file)

        for cookie in cookies:
            # 检查并删除可能导致问题的键
            if 'expiry' in cookie:
                del cookie['expiry']  # 删除expiry键，因为有时它会导致问题

            try:
                driver.add_cookie(cookie)
            except Exception as e:
                logger.error(f"Error loading cookie: {cookie}")
                logger.error(e)
        logger.success(f"Cookies have been loaded from {file_path}")

    def if_login(self, driver):
        logger.info("Checking if logged in")
        try:
            driver.refresh()
            flag_ele = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//*[@class='minds-avatar']")))
            logger.success("Login success")
            return True

        except:
            logger.error("Failed to login")
            return False

    def login(self, driver_ins=None):
        if not driver_ins:
            driver_ins = self.create_driver()
        driver_ins.get(URLS['main'])
        # if Path("__cookies.json").exists():
        #     self.load_cookies(driver_ins, "__cookies.json")
        #     res = self.if_login(driver_ins)
        #     if not res:
        #         raise Exception("Failed to login after loaded cookies.")
        #     else:
        #         return driver_ins
        username_input = WebDriverWait(driver_ins, 20).until(EC.presence_of_element_located((By.XPATH, r'//input[@id="username"]')))
        password_input = WebDriverWait(driver_ins, 20).until(EC.presence_of_element_located((By.XPATH, r'//input[@id="password"]')))
        username_input.send_keys('anthonyfan')
        password_input.send_keys("833020Fan!")
        send_btn_ele = WebDriverWait(driver_ins, 20).until(EC.presence_of_element_located((By.XPATH, r'//*[text()="Login"]')))
        time.sleep(5)
        send_btn_ele.click()
        time.sleep(2)
        res = self.if_login(driver_ins)
        if not res:
            raise Exception("Failed to login")
        else:
            self.save_cookies(driver_ins, '__cookies.json')
            return driver_ins

    def get_user_pages(self, driver, user_url):
        driver.get(user_url+"/about")
        body_part = WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.XPATH, "//m-channel__about")))
        text = body_part.text
        return text


    def get_hashtag_posts(self, driver, hashtag):
        driver.get(URLS[hashtag])
        posts = WebDriverWait(driver, 60).until(EC.presence_of_all_elements_located((By.XPATH, "//*[@class='m-discoveryFeeds__feed']//*[@class='m-activity__top ng-star-inserted']")))
        storage_path = Path(STORAGE_PATH_BASE) / f'{hashtag}_res.json'
        if storage_path.exists():
            logger.success(f'{hashtag} already finished.')
            return
        while 1:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            try:
                next_page_btn = WebDriverWait(driver, 3).until(EC.visibility_of_element_located((By.XPATH, "//div[text()='Nothing more to load']")))
                logger.success("Hit end.")
                break
            except:
                posts = WebDriverWait(driver, 30).until(EC.presence_of_all_elements_located(
                    (By.XPATH, "//*[@class='m-discoveryFeeds__feed']//*[@class='m-activity__top ng-star-inserted']")))
                logger.info(f"We got {len(posts)} Posts")
                users = []
                outs = []
                os.makedirs(storage_path.parent, exist_ok=True)
                for post in tqdm.tqdm(posts):
                    user_url = post.find_element(By.XPATH, './/*[@class="ng-star-inserted"]/*/*/*').get_attribute(
                        'href')
                    users.append(user_url)
                    more_comments = post.find_elements(By.XPATH, './/*[contains(text(), "View")]')
                    if more_comments:
                        logger.info("Got view more comments button. Hit.")
                        more_comments[0].click()
                    text = post.text
                    outs.append(text)
                    with open(storage_path, 'w') as f:
                        json.dump({"users": users, "outs": outs}, f, indent=2, ensure_ascii=False)
                    logger.success(f"Stored {len(outs)} outs. {len(users)} users")

    def main(self):
        driver = self.login()
        for key in URLS.keys():
            if key in ['main']:
                continue
            logger.info(f"Working on {key}")
            try:
                self.get_hashtag_posts(driver, key)
            except:
                logger.error(f"{key} failed")
                continue

    def crawl_user_abouts(self):
        all_data = glob.glob(str(Path('/Users/anthonyf/projects/grainedAI/dataset_downloader/scripts/social_media_crawl/storage')/'*_res.json'))
        users = []
        for data_file in all_data:
            with open(data_file, 'r') as f:
                d = json.load(f)
            users.extend(d['users'])
        users = list(set(users))
        driver = self.login()
        storage_path = Path(STORAGE_PATH_BASE)/'user_abouts.json'
        if storage_path.exists():
            with open(storage_path, 'r') as f:
                user_details = json.load(f)
        else:
            user_details = {}

        for user in tqdm.tqdm(users):
            if user in user_details:
                logger.success(f"{user} crawled.")
                continue
            try:
                res = self.get_user_pages(driver, user)
                cur_input = {user: res}
                user_details.update(cur_input)
                with open(storage_path, 'w') as f:
                    json.dump(user_details, f, indent=2, ensure_ascii=False)
                logger.success(user)
            except:
                logger.error(user)

    def refine_user_abouts(self):
        #### Trim Minds User about
        delivery_file_path = Path(
            "/Users/anthonyf/Desktop/GrainedAI/Datasets/PII/FinalDelivery/SocialMedia/raw_data/SocialMedia.json")
        new_delivery_file_path = delivery_file_path.parent / ("trimmed_" + delivery_file_path.name)
        user_about_path = Path("/Users/anthonyf/Desktop/GrainedAI/Datasets/PII/social_media/user_abouts.json")
        with open(new_delivery_file_path, 'r') as f:
            data = json.load(f)

        with open(user_about_path, 'r') as f:
            mapping = json.load(f)
        driver = self.login()
        for entry in data:
            if entry.get("piis"):
                continue
            for url in mapping:
                content = mapping[url]
                if content.replace('minds', '') == entry['content']:
                    driver.get(url+"/about")

                    break


if __name__ == "__main__":
    ins = CrawlMind(False)
    # ins.main()
    ins.crawl_user_abouts()