import json
import os
import time
import traceback

import requests
import tqdm
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from pathlib import Path
from loguru import logger
STORAGE_PATH_BASE = 'storage'
URLS = {'order_confirmation': 'https://app.mailcharts.com/lists/57',
        'shipping_confirmation': 'https://app.mailcharts.com/lists/687',
        'login': 'https://app.mailcharts.com/',
        'main': 'https://app.mailcharts.com/'}
DEFAULT_CHROMEDRIVER_PATH = '/Users/anthonyf/Desktop/Tools/chromedriver/chromedriver'
DEFAULT_CHROMEDRIVER_VERSION = 133


class MailChartsCrawl:
    def __init__(self, if_headless=True, base_save_dir=None):

        if isinstance(base_save_dir, str):
            self.base_save_dir = Path(base_save_dir)
        elif isinstance(base_save_dir, Path):
            self.base_save_dir = base_save_dir
        else:
            self.base_save_dir = Path(STORAGE_PATH_BASE)

        self.if_headless = if_headless
        self.driver = None

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
        # chrome_options.add_argument('--blink-settings=imagesEnabled=false')  # 禁用图片
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')  # 禁用自动化控制特征
        # chrome_options.add_experimental_option('prefs', {'profile.managed_default_content_settings.javascript': 2})  # 禁用JavaScript
        # chrome_options.add_argument('--incognito')  # 无痕模式
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

    def check_if_login(self, driver):
        try:
            WebDriverWait(driver, 60).until(EC.visibility_of_element_located((By.XPATH, "//*[@alt='Haodi Fan']")))
            logger.success("Login success")
            return True, driver
        except:
            logger.error("Not yet logined.")
            return False, driver

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

    def login(self, driver):
        # COOKIES_PATH = Path('__COOKIES__.json')
        driver = self.create_driver() if not driver else driver
        # driver.get(URLS['main'])
        # if COOKIES_PATH.exists():
        #     self.load_cookies(driver, COOKIES_PATH)
        #     if_login, driver = self.check_if_login(driver)
        #     if if_login:
        #         logger.success(f"Login success.")
        #         self.save_cookies(driver, COOKIES_PATH)
        #         return driver
        #     else:
        #         logger.error(f"Failed to login.")
        #         return None

        driver.get(URLS['main'])
        email_ele = WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.XPATH, "//input[@type='email']")))
        password_ele = WebDriverWait(driver, 30).until(EC.visibility_of_element_located((By.XPATH, "//input[@type='password']")))
        email_ele.send_keys('anthonyfanhaodi@gmail.com')
        password_ele.send_keys('833020Fan!@#')
        send_ele = driver.find_element(By.XPATH, "//button[@id='1-submit']")
        send_ele.click()
        if_login, driver = self.check_if_login(driver)
        if if_login:
            logger.success(f"Login success.")
            # self.save_cookies(driver, COOKIES_PATH)
            return driver
        else:
            logger.error(f"Failed to login.")
            return None

    def get_all_links(self, subject):
        self.driver = self.create_driver()
        is_login = self.login(self.driver)
        if not is_login:
            logger.error("Login failed.")
            return
        self.driver.get(URLS[subject])
        while 1:
            self.driver.execute_script("var q=document.documentElement.scrollTop=100000")
            try:
                next_page_btn = WebDriverWait(self.driver, 20).until(EC.visibility_of_element_located((By.XPATH, "//a[text()='click here']")))
                next_page_btn.click()
                WebDriverWait(self.driver, 5).until(EC.visibility_of_element_located((By.XPATH, "//*[@alt='Haodi Fan']")))
            except:
                logger.info("Hit bottom")
                break

        all_img_eles = self.driver.find_elements(By.XPATH, "//a[@class='css-11gsmua' and contains(@href, 'emails')]")
        img_src_paths = [i.get_attribute('href') for i in all_img_eles]
        return img_src_paths

    def get_link_html(self, link):
        if not self.driver:
            self.driver = self.create_driver()
            self.login(self.driver)
        self.driver.get(link)
        xpath = "//*[text()='Desktop']"
        ele = WebDriverWait(self.driver, 30).until(EC.visibility_of_element_located((By.XPATH, xpath)))
        ele.click()
        xpath_2 = "//*[text()='HTML']"
        ele = WebDriverWait(self.driver, 30).until(EC.visibility_of_element_located((By.XPATH, xpath_2)))
        ele.click()
        # 等待iframe变为可用并切换到它
        try:
            iframe = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "iframe"))
            )
            self.driver.switch_to.frame(iframe)

            # 现在我们在iframe内，等待<pre>元素变为可见
            pre_element = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.TAG_NAME, "pre"))
            )

            # 获取<pre>里的文本
            text = pre_element.text
            return text
        except:
            logger.error(f"Failed to extract: {link}\n{traceback.format_exc()}")
            return None

    def main(self, subject):
        if Path(f'{subject}_links.json').exists():
            with open(f'{subject}_links.json', 'r') as f:
                links = json.load(f)
        else:
            links = self.get_all_links(subject)
            with open(f'{subject}_links.json', 'w') as f:
                json.dump(links, f, indent=2, ensure_ascii=False)
        # driver = self.create_driver()
        # is_login = self.login(driver)
        # if not is_login:
        #     logger.error("Login failed.")
        #     return
        for link in tqdm.tqdm(links):
            link_name = link.split('/')[-1].split('?')[0]
            out_path = Path(STORAGE_PATH_BASE)/subject/f'{link_name}.html'

            if out_path.exists():
                logger.warning(f"{out_path} exists. Skipped.")
                continue
            try:
                res = self.get_link_html(link)
            except:
                logger.error(f"{link} is None. Skipped.")
                continue
            if not res:
                logger.error(f"{link} is None. Skipped.")
                continue
            os.makedirs(out_path.parent, exist_ok=True)

            with open(out_path, 'w') as f:
                f.write(res)
            logger.success(f"Stored to {out_path}")
if __name__ == "__main__":
    ins = MailChartsCrawl(if_headless=False)
    ins.main('shipping_confirmation')
