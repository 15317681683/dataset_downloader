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
from hypothesis.configuration import storage_directory

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
    'main': "https://tildes.net/"
}

DEFAULT_CHROMEDRIVER_PATH = '/Users/anthonyf/Desktop/Tools/chromedriver/chromedriver'
DEFAULT_CHROMEDRIVER_VERSION = 133


class CrawlTildes:
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

    def get_post_res(self, driver, url):
        driver.get(url)
        body_ele = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//body')))
        text = body_ele.text
        return text

    def get_page_all_urls(self, driver):
        topics = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, "//article[@class='topic']")))
        outs = []
        for topic in topics:
            url = topic.find_element(By.XPATH, './/*[@class="topic-info-comments"]/*').get_attribute('href')
            content = topic.text
            outs.append({'url': url,
                         'content_summary': content})
        return outs

    def main(self):
        driver = self.create_driver()
        driver.get(URLS['main'])
        storage_path = Path(STORAGE_PATH_BASE)/'tildes_urls.json'
        if storage_path.exists():
            with open(storage_path, 'r') as f:
                outs = json.load(f)
        else:
            outs = []
        while 1:
            cur_outs = self.get_page_all_urls(driver)
            outs.extend(cur_outs)
            with open(storage_path, 'w') as f:
                json.dump(outs, f, indent=2, ensure_ascii=False)
            logger.success(f"Already crawled {len(outs)} outs.")
            if len(outs) >= 3000:
                logger.warning("Hit 3000 urls. Finished.")
                break
            try:
                next_btn = WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.XPATH, "//a[text()='Next']")))
                next_btn.click()
                logger.info("Next page")
            except:
                logger.warning("No next page.")
                break

    def crawl_all_url_content(self):
        driver = self.create_driver()
        storage_path = Path(STORAGE_PATH_BASE) / 'tildes_urls.json'
        with open(storage_path, 'r') as f:
            items = json.load(f)
        final_outs = []
        storage_path_2 = Path(STORAGE_PATH_BASE) / 'tildes_final.json'

        for item in items:
            url = item['url']
            content = self.get_post_res(driver, url)
            item['content'] = content
            final_outs.append(item)
            with open(storage_path_2, 'w') as f:
                json.dump(final_outs, f, indent=2, ensure_ascii=False)
            logger.success(f"Already crawled {len(final_outs)} outs.")

    def refine_datasets(self):
        Tildes_final = Path("/Users/anthonyf/Desktop/GrainedAI/Datasets/PII/social_media/tildes_final.json")
        new_out = Path("/Users/anthonyf/Desktop/GrainedAI/Datasets/PII/social_media/tildes_final_new.json")
        with open(Tildes_final, 'r') as f:
            data = json.load(f)
        driver = self.create_driver(if_headless=False)
        out = []
        for entry in tqdm.tqdm(data):
            url = entry['url']
            driver.get(url)
            piis = []
            try:
                media_title = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//header/h1'))).text
                piis.append({
                    "pii_content": media_title,
                    "pii_class": "media_title"
                })
            except:
                logger.error("No title")

            try:
                time_contents_eles = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, "//span[contains(@class, 'time')]")))
                time_contents = [i.text for i in time_contents_eles]
                for i in time_contents:
                    piis.append({
                        "pii_content": i,
                        "pii_class": "timestamp"
                    })
            except:
                logger.error("No time_contents")

            try:
                users_eles = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, "//*[@class='link-user']")))
                users_contents = [i.text for i in users_eles]
                for i in users_contents:
                    piis.append({
                        "pii_content": i,
                        "pii_class": "nickname"
                    })
            except:
                logger.error("No users_eles")

            try:
                url = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[contains(@class, "full-link")]'))).text
                piis.append({
                    "pii_content": url,
                    "pii_class": "url"
                })
            except:
                logger.error("No title")

            try:
                url = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, '//*[contains(@class, "form-input input-sm")]'))).get_attribute("value")
                piis.append({
                    "pii_content": url,
                    "pii_class": "url"
                })
                piis.append({
                    "pii_content": re.search("https://tild\.es/(.*)", url).group(1),
                    "pii_class": "post_id"
                })
            except Exception as e:
                logger.error(f"No url: {str(e)}")

            entry['piis'] = piis
            out.append(entry)
            logger.success(piis)
            with open(new_out, 'w') as f:
                json.dump(out, f, ensure_ascii=False, indent=4)
        # driver = self.login()
        # for key in URLS.keys():
        #     if key in ['main']:
        #         continue
        #     logger.info(f"Working on {key}")
        #     try:
        #         self.get_hashtag_posts(driver, key)
        #     except:
        #         logger.error(f"{key} failed")
        #         continue

    # def crawl_user_abouts(self):
    #     all_data = glob.glob(str(Path('/Users/anthonyf/projects/grainedAI/dataset_downloader/scripts/social_media_crawl/storage')/'*_res.json'))
    #     users = []
    #     for data_file in all_data:
    #         with open(data_file, 'r') as f:
    #             d = json.load(f)
    #         users.extend(d['users'])
    #     users = list(set(users))
    #     driver = self.login()
    #     storage_path = Path(STORAGE_PATH_BASE)/'user_abouts.json'
    #     if storage_path.exists():
    #         with open(storage_path, 'r') as f:
    #             user_details = json.load(f)
    #     else:
    #         user_details = {}
    #
    #     for user in tqdm.tqdm(users):
    #         if user in user_details:
    #             logger.success(f"{user} crawled.")
    #             continue
    #         try:
    #             res = self.get_user_pages(driver, user)
    #             cur_input = {user: res}
    #             user_details.update(cur_input)
    #             with open(storage_path, 'w') as f:
    #                 json.dump(user_details, f, indent=2, ensure_ascii=False)
    #             logger.success(user)
    #         except:
    #             logger.error(user)

if __name__ == "__main__":
    ins = CrawlTildes(False)
    # ins.main()
    # ins.main()
    # ins.crawl_all_url_content()
    ins.refine_datasets()