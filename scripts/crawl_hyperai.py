import json
import os
import random
import time

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

    def set_download_directory(self, new_download_dir):
        """
        动态设置下载目录
        :param new_download_dir: 新的下载目录路径
        """
        if not isinstance(new_download_dir, Path):
            new_download_dir = Path(new_download_dir)

        # 执行 CDP 命令来设置新的下载目录
        self.driver.execute_cdp_cmd(
            "Browser.setDownloadBehavior",
            {
                "behavior": "allow",
                "downloadPath": str(new_download_dir)
            }
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
        current_page = self.get_current_page()
        next_page = current_page + 1
        logger.info(f"Next page: {next_page}")
        next_page_btn = WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.XPATH, f"//button[text()='{next_page}']")))
        next_page_btn.click()
        current_page = self.get_current_page()
        if current_page == next_page:
            return True
        raise Exception(f"Failed to turn page {next_page}")

    def get_all_links(self):
        self.driver.get(URL)
        out = {}
        while 1:
            if_on_dataset_page = self.if_on_dataset_page()
            if not if_on_dataset_page:
                logger.error("Failed to get to page. Need to refresh.")
                self.driver.refresh()
                time.sleep(10)
                continue
            current_page = self.get_current_page()
            logger.info(f"Currently on {current_page}")
            datasets_infos = self.get_dataset_blocks()
            logger.info(json.dumps(datasets_infos, indent=2, ensure_ascii=False))
            out.update(datasets_infos)
            with open(self.base_save_dir / 'hyperai_dataset.json', 'w', encoding='utf-8') as f:
                json.dump(out, f, indent=2, ensure_ascii=False)
            for _ in range(5):
                try:
                    logger.info(f"Attempt {_}")
                    flag = self.next_page()
                    if flag:
                        break
                except:
                    continue

    def get_link_dataset(self, url, dir_path: Path):
        self.driver.get(url)
        res = requests.get(url)
        res_data = res.text
        html_path = dir_path/'main.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(res_data)

        self.set_download_directory(dir_path)

        if_downloaded = False
        torrent_href = None
        torrent_path = None
        if self.driver.find_elements(By.XPATH, "//span[text()='数据集下载']"):
            logger.info("Starts to download dataset.")
            torrent_href = self.driver.find_element(By.XPATH, "//span[text()='数据集下载']").find_element(By.XPATH, '../..').get_attribute('href')
            torrent_path = dir_path/'dataset.torrent'
            response = requests.get(torrent_href, stream=True)
            response.raise_for_status()  # 检查请求是否成功

            # 确保保存路径的目录存在
            save_path = torrent_path
            save_path.parent.mkdir(parents=True, exist_ok=True)

            # 保存文件
            with open(save_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            if save_path.exists():
                logger.success("Downloaded.")
                if_downloaded = True
            else:
                logger.error("Failed to download.")

        page_upper_body_xpath = '//*[@id="__next"]/div/div[1]/div/div/div[1]'
        try:
            ele = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, page_upper_body_xpath)))
            page_upper_body = ele.text
        except:
            page_upper_body = None
        page_body_xpath = "//div[contains(@class, 'page-body_content')]"
        try:
            ele = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, page_body_xpath)))
            page_body = ele.text
        except:
            page_body = None
        file_tree_xpath = '//*[@id="__next"]/div/div[1]/div/div/div[2]/div/div[3]/div[2]'
        try:
            ele = WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.XPATH, file_tree_xpath)))
            file_tree = ele.text
        except:
            file_tree = None
        return {'html_path': str(html_path),
                'page_upper_body': page_upper_body,
                'page_body': page_body,
                'file_tree': file_tree,
                'if_clicked_download': if_downloaded,
                'torrent_href': str(torrent_href),
                'torrent_path': str(torrent_path)}

    def main(self):
        with open("D:\datasets\hyperai\hyperai_dataset.json", 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        final_res = {}
        outpath = Path(rf"D:\datasets\hyperai\final_datasets.json")
        if outpath.exists():
            with open(outpath, 'r', encoding='utf-8') as f:
                final_res = json.load(f)

        for url in tqdm.tqdm(raw_data.keys()):
            logger.info(f"Working on {url}")
            dataset_description = '_'.join(raw_data[url].split('\n')[:-1])
            if url in final_res:
                logger.success("Already finished.")
                continue

            try:
                dataset_dir = Path(STORAGE_PATH_BASE) / dataset_description
                os.makedirs(dataset_dir, exist_ok=True)
                data = self.get_link_dataset(url, dataset_dir)
            except:
                logger.error("Failed to get link dataset")
                continue
            final_res[url] = {}
            final_res[url]['dir_path'] = str(dataset_dir)
            final_res[url]['first_page'] = raw_data[url]
            final_res[url]['detailed_page'] = data
            with open(outpath, 'w', encoding='utf-8') as f:
                json.dump(final_res, f, ensure_ascii=False, indent=4)
            logger.info(json.dumps(data, indent=2, ensure_ascii=False))
            logger.success(f'{url} finished.')


if __name__ == "__main__":
    ins = HyperAiCrawl(False)
    ins.main()
