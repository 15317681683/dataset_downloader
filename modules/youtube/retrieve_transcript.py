import shutil
import subprocess
import time
import os
from loguru import logger
from pathlib import Path
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
# from modules.asr_utils import ASR
from youtube_transcript_api.formatters import TextFormatter
from modules.youtube.youtube_download import youtube2wav


class TransRetrieveException(Exception):
    pass


class TranscriptRetrieve:
    def __init__(self, tmp_path=None):
        if not tmp_path:
            self.tmp_path = Path(__file__).parent
        else:
            self.tmp_path = tmp_path
        os.makedirs(self.tmp_path, exist_ok=True)
        # self.asr = ASR()

    @staticmethod
    def api_get_youtube_video_script(video_id):
        try:
            script = YouTubeTranscriptApi.get_transcript(video_id=video_id,
                                                         proxies={'http': 'socks5://127.0.0.1:1082',
                                                                  'https': 'socks5://127.0.0.1:1082'},
                                                         languages=["zh-CN", "zh", "zh-Hans", 'zh-Hant', "zh-HK",
                                                                    "zh-TW", 'zh-SG', 'zh-Hans', 'en', 'en-US'])
            return script
        except Exception as e:
            logger.error(str(e))
            raise TransRetrieveException(f"Fail to retrieve {video_id}. {str(e)}")

    @staticmethod
    def api2_get_video_transcript(video_id):
        try:
            # 获取给定视频ID的字幕列表
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            logger.debug(transcript_list)

            # 尝试找到一个合适的字幕（无论是手动上传的还是自动生成的）
            transcript = None
            for t in transcript_list:
                if t.is_generated():  # 如果需要的是自动生成的字幕
                    transcript = t.fetch()
                    break
            else:  # 如果没有自动生成的字幕，则尝试使用第一个可用的手动上传字幕
                transcript = transcript_list.find_manually_created_transcript(['en'])

            if transcript is None:
                return "No suitable transcript found."

            # 使用TextFormatter将字幕格式化为纯文本
            formatter = TextFormatter()
            text_formatted = formatter.format_transcript(transcript)

            return text_formatted

        except Exception as e:
            logger.error(str(e))
            return None

    @staticmethod
    def api3_get_youtube_video_script(video_id, language='en'):
        """
        通过YouTube视频ID获取字幕
        :param video_id: YouTube视频ID（如：dQw4w9WgXcQ）
        :param language: 字幕语言代码（默认en=英文，zh-Hans=简体中文）
        :return: 字幕文本 或 None
        """
        ydl_opts = {
            'skip_download': True,  # 不下载视频
            'writesubtitles': True,  # 写入字幕
            'writeautomaticsub': True,  # 包括自动生成字幕
            'subtitleslangs': [language],  # 指定语言
            'subtitlesformat': 'srt',  # 字幕格式
            'quiet': True,  # 关闭冗余输出
            'no_warnings': True,  # 关闭警告
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(
                    f'https://www.youtube.com/watch?v={video_id}',
                    download=False
                )

                if 'subtitles' not in info and 'automatic_captions' not in info:
                    print("⚠️ 该视频无可用字幕")
                    return None

                # 尝试获取指定语言字幕
                subtitles = info.get('subtitles', {}).get(language, [])
                auto_subs = info.get('automatic_captions', {}).get(language, [])

                # 优先选择手动上传的字幕
                all_subs = subtitles + auto_subs

                if not all_subs:
                    print(f"⚠️ 找不到 {language} 语言的字幕")
                    return None

                # 下载第一个可用的字幕文件
                sub_url = all_subs[0]['url']
                sub_data = ydl.urlopen(sub_url).read().decode('utf-8')

                # 将SRT格式转换为纯文本
                return '\n'.join(
                    line.strip()
                    for line in sub_data.split('\n')
                    if line.strip() and not line.strip().isdigit()
                    and '-->' not in line
                )

        except Exception as e:
            logger.error(f"❌ 发生错误: {str(e)}")
            return None

    def get_wav_script(self, video_path: Path, lang='zh'):
        if video_path.suffix != '.wav':
            raise TransRetrieveException(f"Fail to retrieve input transcript: {video_path} is not wav file.")
        try:
            res = self.asr(audio=str(video_path))
            return res
        except Exception as e:
            raise TransRetrieveException(str(e))

    def asr_get_youtube_video_script(self, video_id, lang='zh', keep_wav=False):
        tmp_path = self.tmp_path / f'tmp_{str(int(time.time() * 1000))}'
        output_wav_path = tmp_path / f'{video_id}.wav'
        wav_path = youtube2wav('https://www.youtube.com/watch?v=' + video_id, str(output_wav_path))
        # subprocess.
        if not output_wav_path.exists():
            raise TransRetrieveException(f"Fail to download youtube wav for {video_id}")
        try:
            transcript = self.get_wav_script(Path(wav_path), lang)
            if not keep_wav:
                shutil.rmtree(tmp_path)
            return transcript
        except TransRetrieveException as e:
            raise TransRetrieveException(str(e))

    def get_youtube_video_transcript(self, video_id, lang='zh', auto_switch=False):
        logger.info(f"Starts to retrieve transcript for {video_id}")
        try:
            script_raw = self.api_get_youtube_video_script(video_id)
            # script = ','.join([i['text'] for i in script_raw])
            return script_raw
        except TransRetrieveException as e:
            if auto_switch:
                logger.warning("Fail to download script by API. Will try to get by ASR video.")
                self.asr_get_youtube_video_script(video_id, lang)
                # return self.api2_get_video_transcript(video_id)
            raise TransRetrieveException(str(e))
