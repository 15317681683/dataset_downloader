STORAGE_PATH_BASE = 'D:\datasets\earthcam'
URLS = {'halloffame': 'https://www.earthcam.com/halloffame/',
        'all_locations': 'https://www.earthcam.com/network/'}

from DrissionPage import Chromium, ChromiumOptions

co = ChromiumOptions().auto_port()
# co.no_imgs(True).mute(True)

tab = Chromium(addr_or_opts=co).latest_tab

tab.get(URLS.get('all_locations'))

camera_xpath = "//*[@class=' listContainer row']//a[@class='listImg']"
countries_xpath = "//*[@class='country']"

eles = tab.eles(f'xpath:{countries_xpath}')
for ele in eles:
    ele.click()
    print('click here')
    cameras = tab.eles(f"xpath:{camera_xpath}")
    print("HERE")