# import os
# import glob
# import asyncio
# from torrentp import TorrentDownloader
#
#
# async def download_torrent(torrent_file, save_path):
#     try:
#         # 创建 TorrentDownloader 实例
#         downloader = TorrentDownloader(torrent_file, save_path)
#
#         # 开始下载
#         await downloader.start_download()
#
#         print(f"下载完成: {torrent_file}")
#     except Exception as e:
#         print(f"下载失败: {torrent_file} - {e}")
#
#
# def main(folder_path):
#     # 使用 glob 匹配所有 .torrent 文件
#     torrent_files = glob.glob(os.path.join(folder_path, '*.torrent'))
#
#     # 确保目标保存路径存在
#     save_path = folder_path
#
#     # 创建异步任务列表
#     tasks = [download_torrent(torrent_file, save_path) for torrent_file in torrent_files][0]
#
#     # 运行异步任务
#     asyncio.run(asyncio.gather(*tasks))
#
#
# if __name__ == '__main__':
#     # 指定文件夹路径
#     folder_path = 'D:\datasets\hyperai\ DukeMTMC-reID 多相机追踪重识别数据集_人脸识别'  # 请根据实际情况修改路径
#
#     # 运行主函数
#     main(folder_path)

import libtorrent as lt
import time
import sys


def download_torrent(torrent_link, save_path='./'):
    # 初始化会话
    ses = lt.session()
    ses.listen_on(6881, 6891)

    # 添加torrent
    if torrent_link.endswith('.torrent'):
        info = lt.torrent_info(torrent_link)
        handle = ses.add_torrent({'ti': info, 'save_path': save_path})
    else:  # 假设这是一个磁力链接
        params = {
            'save_path': save_path,
            'storage_mode': lt.storage_mode_t(2),
            'paused': False,
            'auto_managed': True,
            'duplicate_is_error': True
        }
        handle = lt.add_magnet_uri(ses, torrent_link, params)

    print('开始下载:', torrent_link)

    # 下载循环
    while not handle.is_seed():
        s = handle.status()

        state_str = ['queued', 'checking', 'downloading metadata',
                     'downloading', 'finished', 'seeding', 'allocating']
        print('\r%.2f%% complete (down: %.1f kB/s up: %.1f kB/s peers: %d) %s' % (
            s.progress * 100, s.download_rate / 1000, s.upload_rate / 1000,
            s.num_peers, state_str[s.state]), end=' ')

        time.sleep(1)

    print('\n下载完成')


if __name__ == '__main__':
    # if len(sys.argv) < 2:
    #     print('用法: python3 download_torrent.py [torrent链接] [保存路径]')
    #     sys.exit(1)
    torrent_link = 'D:\datasets\hyperai\ DukeMTMC-reID 多相机追踪重识别数据集_人脸识别\dataset.torrent'
    # torrent_link = sys.argv[1]
    save_path = 'D:\datasets\hyperai\ DukeMTMC-reID 多相机追踪重识别数据集_人脸识别'

    download_torrent(torrent_link, save_path)