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
'https://www.weatherbug.com/traffic-cam/shanghai-shanghai-ch'
STORAGE_PATH_BASE = 'D:\datasets\earthcam'
URLS = {'halloffame': 'https://www.earthcam.com/halloffame/',
        'all_locations': 'https://www.earthcam.com/network/'}
DEFAULT_CHROMEDRIVER_PATH = '/Users/anthonyf/Downloads/chromedriver-mac-x64/chromedriver'
DEFAULT_CHROMEDRIVER_VERSION = 131


class EarthCamCrawl:
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
    @staticmethod
    def download_image(url, save_path):
        """
        从指定的URL下载图像并保存到本地。

        参数:
        - url (str): 图像的URL地址。
        - save_path (str): 保存图像的本地路径，包括文件名和扩展名。

        返回:
        - None
        """
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()  # 检查请求是否成功

            # 打开图像
            image = Image.open(BytesIO(response.content))

            # 获取原始尺寸
            width, height = image.size
            logger.success(f"原始尺寸: {width}x{height}")

            # 裁剪掉右边10%
            new_width = int(width * 0.86)
            cropped_image = image.crop((0, 0, new_width, height))  # (左, 上, 右, 下)

            # 确保保存路径的目录存在
            os.makedirs(os.path.dirname(save_path), exist_ok=True)

            # 保存裁剪后的图像
            cropped_image.save(save_path)
            logger.success(f"图像已成功裁剪并保存到 {save_path}")
        except requests.exceptions.RequestException as e:
            logger.error(f"下载图像时出错: {e}")
        except Exception as e:
            logger.error(f"保存图像时出错: {e}")

    def get_halloffame_from_all_locations(self):
        if (Path(__file__).parent / 'out.json').exists():
            with open(Path(__file__).parent / 'out.json', 'r', encoding='utf-8') as f:
                out = json.load(f)
        else:
            out = {}
        for location_name in tqdm.tqdm(out):
            location_urls = out[location_name]
            for url in location_urls:
                logger.info(f"Working on {url}")
                try:
                    self.get_halloffame_by_location(url)
                    time.sleep(random.randint(1,5))
                except:
                    logger.error("Failed to download")
                    continue

    def get_halloffame_by_location(self, location='https://www.earthcam.com/usa/arizona/fountainhills/'):
        location_name = '_'.join(location.split('/')[3:])
        if (Path(__file__).parent / 'image' / location_name).exists():
            logger.success("Already Finished location")
            return
        self.driver.get(location)
        self.driver.execute_script("var q=document.documentElement.scrollTop=100000")
        time.sleep(random.randint(1, 5))
        camera_eles = WebDriverWait(self.driver, 50).until(
            EC.presence_of_all_elements_located((By.XPATH, "//*[@class='pic']")))
        hrefs = [i.find_element(By.XPATH, './/img').get_attribute('src') for i in camera_eles]
        for url in tqdm.tqdm(hrefs[:10]):
            save_path = Path(__file__).parent/'image'/location_name/(str(time.time()*1000) + '.jpg')
            os.makedirs(save_path.parent, exist_ok=True)
            self.download_image(url, save_path)

    def get_all_locations(self):
        self.driver.get(URLS.get("all_locations"))
        if (Path(__file__).parent/'out.json').exists():
            with open(Path(__file__).parent/'out.json', 'r', encoding='utf-8') as f:
                out = json.load(f)
        else:
            out = {}
        camera_xpath = "//*[@class=' listContainer row']//a[@class='listImg']"
        countries_xpath = "//*[@class='location']"
        # time.sleep(5)
        WebDriverWait(self.driver, 50).until(EC.presence_of_element_located((By.XPATH, countries_xpath)))
        eles = self.driver.find_elements(By.XPATH, countries_xpath)
        logger.info(len(eles))
        for location, href in tqdm.tqdm([(i.text, i.find_element(By.XPATH, './/a').get_attribute('href')) for i in eles]):
            # location= ele.text
            #
            # href = ele.find_element(By.XPATH, './/a').get_attribute('href')
            logger.info(location)
            if out.get(location):
                logger.success("Crawled. Skipped.")
                continue
            self.driver.get(href)


            logger.info("Clicked")
            time.sleep(2)
            try:
                camera_eles = WebDriverWait(self.driver, 50).until(EC.presence_of_all_elements_located((By.XPATH, camera_xpath)))
                hrefs = [i.get_attribute('href') for i in camera_eles]
            except:
                self.driver.refresh()
                logger.error("HERE")
                time.sleep(10)
                camera_eles2 = WebDriverWait(self.driver, 50).until(
                    EC.presence_of_all_elements_located((By.XPATH, camera_xpath)))
                hrefs = [i.get_attribute('href') for i in camera_eles2]
            out[location] = hrefs
            logger.info(hrefs)
            with open("out.json", 'w', encoding='utf-8') as f:
                json.dump(out, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    ins = EarthCamCrawl(False)
    ins.get_halloffame_from_all_locations()