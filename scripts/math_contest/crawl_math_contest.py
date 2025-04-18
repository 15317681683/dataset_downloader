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

STORAGE_PATH_BASE = '.'
URLS = {'all_contests': 'https://artofproblemsolving.com/wiki/index.php/Category:Math_Contest_Problems'}
DEFAULT_CHROMEDRIVER_PATH = '/Users/anthonyf/Desktop/Tools/chromedriver/chromedriver'
DEFAULT_CHROMEDRIVER_VERSION = 133


class CrawlMathContests:
    def __init__(self, if_headless):
        self.if_headless = if_headless
        logger.info(f"Projects default if_headless={if_headless}")
        self.transcript_retriever = TranscriptRetrieve()

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

    def update_all_contests_list(self):
        xpath = "//*[@class='mw-category']//a[contains(@href, '/wiki')]"
        driver = self.create_driver()
        driver.get(URLS['all_contests'])
        all_contests_eles = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, xpath)))
        with open('all_contests_list.json', 'w', encoding='utf-8') as f:
            data = {i.get_attribute('title'): i.get_attribute('href') for i in all_contests_eles}
            json.dump(data, f, indent=2, ensure_ascii=False)
        return data

    @property
    def all_contests(self):
        if Path("all_contests_list.json").exists():
            with open("all_contests_list.json", 'r') as f:
                return json.load(f)
        logger.info("Starts to update all contests list")
        all_contests = self.update_all_contests_list()
        return all_contests

    def extract_element_text(self, soup):
        result = []
        for child in soup.children:
            if child.name is None:  # 如果是NavigableString类型，直接添加文本
                if child.strip().startswith('~'):
                    continue
                result.append(child.strip())
            elif child.name == 'img':  # 如果是img标签，添加其alt属性值
                alt = child.get('alt', '')
                if alt:
                    result.append(alt)
            else:  # 否则递归处理子元素
                result.append(self.extract_element_text(child))
        return ''.join(result)

    # DEPRECATED
    def get_youtube_transcript(self, youtube_url_str):
        regex_1 = 'https://youtu.be/(.+)'
        regex_2 = 'https://www.youtube.com/watch\?v=(.+)'
        regex_list = [regex_1, regex_2]
        youtube_id = None
        for regex in regex_list:
            match = re.search(regex, youtube_url_str)
            if match:
                logger.info(f"Match with {regex}")
                youtube_id = match.group(1)
        if not youtube_id:
            logger.error(f"Fail to get youtube id for {youtube_url_str}.")
            return None
        transcript = self.transcript_retriever.get_youtube_video_transcript(youtube_id, auto_switch=True)
        return transcript

    def extract_problem_page(self, problem_url, contest, year, problem_index):
        try:
            logger.info(f"Parsing Problem page: {problem_url}")
            hash_name = "_".join(problem_url.split('/'))
            dir_path = Path(STORAGE_PATH_BASE) / contest / year / problem_index
            os.makedirs(dir_path, exist_ok=True)
            problem_header_xpath = "//*[@class='mw-parser-output']//h2//*[text()='Problem']"
            solution_header_xpath = "//*[@class='mw-parser-output']//h2//*[contains(text(), 'Solution')]"
            driver = self.create_driver()
            driver.get(problem_url)
            # Parse basic structure
            try:
                main_body_ele = WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.XPATH, "//*[@class='mw-parser-output']")))
            except:
                logger.error("Failed to get whole QA part ele.")
                driver.quit()
                return None
            try:
                problem_header_ele = WebDriverWait(driver, 60).until(
                    EC.presence_of_element_located((By.XPATH, problem_header_xpath)))
            except:
                problem_header_xpath = "//*[@class='mw-parser-output']//h2//*[contains(text(), 'Problem')]"
                try:
                    problem_header_ele = WebDriverWait(driver, 60).until(
                        EC.presence_of_element_located((By.XPATH, problem_header_xpath)))
                except:
                    logger.error("Failed to get Problem Header.")
                    driver.quit()
                    return None
            try:
                solution_eles = WebDriverWait(driver, 60).until(
                    EC.presence_of_all_elements_located((By.XPATH, solution_header_xpath)))
            except:
                try:
                    solution_header_xpath = "//*[@class='mw-parser-output']//h3//*[contains(text(), 'Solution')]"
                    solution_eles = WebDriverWait(driver, 60).until(
                        EC.presence_of_all_elements_located((By.XPATH, solution_header_xpath)))
                except:
                    logger.error("Failed to get Solutions for current Problem.")
                    driver.quit()
                    return None

            if not solution_eles:
                logger.error("Failed to get even one solution for the Problem.")
                driver.quit()
                return None

            logger.success(f"Found {len(solution_eles)} solutions. \n[{[i.text for i in solution_eles]}]")
            # Cut parts
            page_parts = {}
            level_1_eles = main_body_ele.find_elements(By.XPATH, './*')
            current_part_name = None
            for ele in level_1_eles:
                if ele.tag_name == 'h2':
                    logger.success(f"Found one header element. Text: {ele.text}")
                    current_part_name = ele.text
                    if ele.text not in page_parts:
                        page_parts[ele.text] = []
                    continue
                elif ele.tag_name == 'h3':
                    logger.success(f"Found one header element. Text: {ele.text}")
                    current_part_name = ele.text
                    if ele.text not in page_parts:
                        page_parts[ele.text] = []
                    continue
                elif ele.tag_name == 'p':
                    if not current_part_name:
                        continue
                    page_parts[current_part_name].append(ele)
                else:
                    logger.warning("Not p or h2, skipped.")

            logger.success(f"Finished parsing. Maps: {page_parts}")
            page_parts_clean = {}
            for part_name in page_parts:
                part_elements = page_parts[part_name]
                if not part_elements:
                    continue
                # Get part screenshot
                # 分别对每个元素截图
                screenshots = []
                max_width = 0
                total_height = 0

                for index, element in enumerate(part_elements):
                    driver.execute_script("arguments[0].scrollIntoView(true);", element)
                    try:
                        WebDriverWait(driver, 60).until(
                            lambda d: d.execute_script('return document.readyState') == 'complete'
                        )
                    except:
                        logger.warning("Exceed 30 seconds. Screenshot anyways.")
                    screenshot_path = dir_path / f'{hash_name}_{part_name}_{index}.png'
                    element.screenshot(str(screenshot_path))
                    img = Image.open(screenshot_path)
                    screenshots.append(img)

                    # 更新最大宽度和总高度
                    max_width = max(max_width, img.width)
                    total_height += img.height

                # 创建一个新的空白图像用于合并所有截图
                merged_image = Image.new('RGB', (max_width, total_height))
                current_height = 0

                # 将每个截图粘贴到新图像上适当的位置
                for screenshot in screenshots:
                    merged_image.paste(screenshot, (0, current_height))
                    current_height += screenshot.height
                merged_image.save(dir_path / f'{hash_name}_{part_name}.png')
                if part_name not in page_parts_clean:
                    page_parts_clean[part_name] = {'screenshot': str(dir_path / f'{hash_name}_{part_name}.png'),
                                                   'content': []}
                for part_element in part_elements:
                    part_element_innerHTML = part_element.get_attribute('innerHTML')
                    soup = BeautifulSoup(part_element_innerHTML, 'html.parser')
                    merged_text = self.extract_element_text(soup)
                    page_parts_clean[part_name]['content'].append(merged_text)
            driver.quit()
            return page_parts_clean
        except:
            logger.error(f"Failed to extract: {problem_url}. LOGS: \n{traceback.print_exc()}")
            return None

    def explore_qa_pages_for_contest(self, contest):
        try:
            contest_page_url = self.all_contests.get(contest, None)
            if not contest_page_url:
                logger.error(f"Cannot find contest {contest}")
                return None
            driver = self.create_driver()
            driver.get(contest_page_url)
            try:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, "//*[@class='logo-img-link']")))
            except:
                logger.error(f"Failed to load page {contest_page_url}")
                return None
            year_18xx_contest_xpath = "//a[contains(text(), '18')]"
            year_19xx_contest_xpath = "//a[contains(text(), '19')]"
            year_20xx_contest_xpath = "//a[contains(text(), '20')]"
            year_contest_elements_candidates = (driver.find_elements(By.XPATH, year_19xx_contest_xpath)
                                                + driver.find_elements(By.XPATH, year_20xx_contest_xpath)
                                                + driver.find_elements(By.XPATH, year_18xx_contest_xpath))
            year_contests_urls = {}
            for candidate in year_contest_elements_candidates:
                ele_href = candidate.get_attribute('href')
                if not ele_href or '/wiki/index.php' not in ele_href:
                    logger.warning("No href or index.php in url. Skipped")
                    continue
                if "Problems" in ele_href:
                    logger.warning("Problems in url. Skipped")
                    continue
                ele_title = candidate.get_attribute('title')
                if not ele_title or '(page does not exist)' in ele_title:
                    logger.warning("Page doesnt exist")
                    continue
                year_match = re.search(r'\b(\d{4})\b', ele_title)
                if year_match:
                    year = year_match.group(1)
                    if year not in year_contests_urls:
                        year_contests_urls[year] = []
                    year_contests_urls[year].append(ele_href)
                    logger.success(f"Found {year} {contest}: {ele_href}")
            driver.quit()
            year_contest_problem_out = {}
            for year in tqdm.tqdm(year_contests_urls):
                logger.info(f"Working on {year} {contest}")
                driver = self.create_driver(True)
                for year_contest_candidate_url in year_contests_urls[year]:
                    driver.get(year_contest_candidate_url)
                    try:
                        WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.XPATH, "//*[@class='logo-img-link']")))
                    except:
                        logger.error(f"Failed to load page {contest_page_url}")
                        return None
                    problem_element_candidates = driver.find_elements(By.XPATH, "//*[contains(@href, 'Problem_')]")
                    for problem_element_candidate in problem_element_candidates:
                        ele_href = problem_element_candidate.get_attribute('href')
                        if not ele_href or not re.search(r'/Problem_(\d+)', ele_href):
                            logger.warning("href doesnt contain Problem_\d or not exist. Skipped")
                            continue
                        ele_title = problem_element_candidate.get_attribute('title')
                        if not ele_title or '(page does not exist)' in ele_title:
                            logger.warning("Page doesnt exist")
                            continue
                        problem_name = problem_element_candidate.text
                        problem_name_match = re.search('(Problem \d+)', problem_name)
                        if not problem_name_match:
                            logger.warning(f"Title not of format: Problem \d+ :{problem_name}")
                            continue
                        problem_name = problem_name_match.group(1)
                        if year not in year_contest_problem_out:
                            year_contest_problem_out[year] = {}
                        if problem_name not in year_contest_problem_out[year]:
                            year_contest_problem_out[year][problem_name] = []
                        logger.success(f"Found {year} {contest} {problem_name}: {ele_href}")
                        year_contest_problem_out[year][problem_name].append(ele_href)
                driver.quit()
            # Post process:
            for year in year_contest_problem_out:
                for problem_name in year_contest_problem_out[year]:
                    year_contest_problem_out[year][problem_name] = list(
                        set(year_contest_problem_out[year][problem_name]))
            with open(f'{contest}_year_problem_set.json', 'w', encoding='utf-8') as f:
                json.dump(year_contest_problem_out, f, indent=2, ensure_ascii=False)
            return year_contest_problem_out
        except:
            logger.error(f"{contest} Processing failed. Logs: \n{traceback.print_exc()}")
            return None

    def explore_all_contest(self, multiprocessing=False):
        out = {}
        if not multiprocessing:
            for contest in self.all_contests.keys():
                year_contest_problem_out = self.explore_qa_pages_for_contest(contest)
                if year_contest_problem_out:
                    out[contest] = year_contest_problem_out
                    logger.success(f"{contest} Finished.")
        else:
            contests = list(self.all_contests.keys())

            with Pool(processes=cpu_count()) as pool:
                results = pool.map(self.explore_qa_pages_for_contest, contests)

                for contest, year_contest_problem_out in zip(contests, results):
                    if year_contest_problem_out:
                        out[contest] = year_contest_problem_out
                        logger.success(f"{contest} Finished.")

        # 将结果保存到JSON文件
        with open("MathContestsOuts.json", "w") as outfile:
            json.dump(out, outfile, ensure_ascii=False, indent=4)

        return out

    def process_todo(self, todo):
        """处理单个任务的静态方法"""
        url, contest, year, problem_index = todo
        url_data = self.extract_problem_page(url, contest, year, problem_index)  # 注意：这里需要调整以支持静态方法
        return {'contest': contest,
                'year': year,
                'problem_index': problem_index,
                'url_path': url,
                'question': url_data}

    def crawl_all_tests(self, multiprocessing=False):
        with open('MathContestsOuts.json', 'r') as f:
            data = json.load(f)

        storage_path = Path(STORAGE_PATH_BASE) / 'final_delivery_part.json'
        if storage_path.exists():
            with open(storage_path, 'r') as f:
                outs = json.load(f)
        else:
            outs = []

        todo_list = []
        for contest in data:
            for year in data[contest]:
                for problem_index in data[contest][year]:
                    for url in data[contest][year][problem_index]:
                        if url in [i.get('url_path') for i in outs if i.get('question')]:
                            logger.success(f"{url} finished. Passed.")
                            continue
                        todo_list.append((url, contest, year, problem_index))

        if not multiprocessing:
            for todo in tqdm.tqdm(todo_list):
                result = self.process_todo(todo)  # 调整此处以适应静态方法
                outs.append(result)
                with open(storage_path, 'w') as f:
                    json.dump(outs, f, indent=2, ensure_ascii=False)
                logger.success(f"Added {json.dumps(result, indent=2, ensure_ascii=False)}")
        else:
            with Pool(processes=cpu_count()//2) as pool:
                results = list(
                    tqdm.tqdm(pool.imap_unordered(self.process_todo, todo_list), total=len(todo_list),
                              desc="Processing"))

                for result in results:
                    outs.append(result)

                with open(storage_path, 'w') as f:
                    json.dump(outs, f, indent=2, ensure_ascii=False)
                logger.success("All tasks completed and saved.")

    def clean_math_contest_result(self):
        pre_version = Path(STORAGE_PATH_BASE)/'contests_qa_delivery'
        # final_delivery_path = Path(STORAGE_PATH_BASE)/'final_delivery'
        final_delivery_path = Path(STORAGE_PATH_BASE)/'final_delivery_split_YS'
        with open(pre_version/'final_delivery_part.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        final_out = []
        final_final_out = []
        existing_contest = {}
        for entry in data:
            modified_content = copy.deepcopy(entry)
            question_part = entry['question']
            Question_found = False
            Solution_found = False
            modified_question = {}
            if not question_part:
                continue
            for key in question_part.keys():
                if 'See also' in key:
                    continue
                if 'See Also' in key:
                    continue

                if 'Problem' in key:
                    if question_part[key]:
                        Question_found = True
                elif 'Solution' in key:
                    if len(question_part[key]['content']) <= 10:
                        continue
                    if question_part[key]:
                        Solution_found = True

                modified_question[key] = question_part[key]
            modified_content['question'] = modified_question
            if not Solution_found or not Question_found:
                logger.error(f"Solution_Found: {Solution_found}. Question_Found: {Question_found}")
                continue
            final_out.append(modified_content)

        for entry in tqdm.tqdm(final_out):
            contest = entry['contest']
            if existing_contest.get(contest, 0) >=1:
                continue
            if contest not in existing_contest:
                existing_contest[contest] = 0
            question_part = entry['question']
            for key in question_part.keys():
                if 'screenshot' in question_part[key]:
                    file_path = Path(question_part[key]['screenshot'])
                    if 'Solution' in key:
                        question_part[key]['screenshot'] = None
                        continue
                    if file_path.exists():
                        target_file_path = Path(re.sub('https:__artofproblemsolving.com_wiki_index.php', 'GRAINED_AI', str(final_delivery_path/'/'.join(file_path.parts[1:]))))
                        os.makedirs(target_file_path.parent, exist_ok=True)
                        shutil.copy(file_path, target_file_path)
                        logger.success(f"{file_path} -> {target_file_path}")
                        question_part[key]['screenshot'] = str(target_file_path.relative_to(final_delivery_path.parent))
            modified_content = copy.deepcopy(entry)
            del modified_content['url_path']
            modified_content['question'] = question_part
            final_final_out.append(modified_content)
            existing_contest[contest] += 1
        # with open(Path(final_delivery_path) / 'final_delivery_part.json', 'w', encoding='utf-8') as f:
        #     json.dump(final_final_out, f, indent=2, ensure_ascii=False)
        with open(Path(final_delivery_path) / 'final_delivery_part.jsonl', 'w', encoding='utf-8') as f:
            for entry in final_final_out:
                json_line = json.dumps(entry, ensure_ascii=False)
                f.write(json_line + '\n')
            # json.dump(final_final_out, f, indent=2, ensure_ascii=False)
        with open('final_delivery_split/contest_summary.json', 'w', encoding='utf-8') as f:
            json.dump(existing_contest, f, ensure_ascii=False, indent=2)

    def examine_result(self):
        pre_version = Path(STORAGE_PATH_BASE)/'contests_qa_delivery'
        with open(pre_version/'final_delivery_part.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        summary = {}
        for entry in data:
            contest = entry['contest']
            year = entry['year']
            if contest not in summary:
                summary[contest] = {}
            if year not in summary[contest]:
                summary[contest][year] = 0

            summary[contest][year] += 1
        with open('Total_Summary_Math_Contest_QA.json', 'w') as f:
            json.dump(summary, f, ensure_ascii=False, indent=4)



if __name__ == "__main__":
    ins = CrawlMathContests(True)
    # ins.get_all_contests()
    # res = ins.extract_problem_page("https://artofproblemsolving.com/wiki/index.php/2005_Cyprus_Seniors_TST/Day_1/Problem_1")
    # print(json.dumps(res, indent=2, ensure_ascii=False))
    # res = ins.get_youtube_transcript("https://www.youtube.com/watch?v=i10tEEHq0sI&t=183s")
    # print(res)
    # ins.explore_qa_pages_for_contest('JBMO Problems and Solutions, with authors')
    # ins.explore_all_contest(True)
    # ins.crawl_all_tests(True)
    # ins.clean_math_contest_result()
    ins.examine_result()