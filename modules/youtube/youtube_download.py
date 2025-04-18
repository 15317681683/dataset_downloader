from __future__ import unicode_literals

import shutil
from pathlib import Path
import glob
import yt_dlp
import time
import os


def youtube2wav(url, output_path=None, overwrite=False):
    output_path = output_path if output_path else 'output.wav'
    if overwrite:
        os.remove(output_path)
    else:
        if Path(output_path).exists():
            return output_path
    ffmpeg_path = Path(__file__).parent / 'ffmpeg_bin'
    tmp_path = f'yd_tmp_{str(int(time.time() * 1000))}'
    ydl_opts = {
        'format': 'bestaudio/best',
        #    'outtmpl': 'output.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
        }],
        'proxy': 'socks5://127.0.0.1:1082',
        'ffmpeg_location': str(ffmpeg_path),
        'paths': {'home': tmp_path},
        'prefer_insecure': True,
        'cookies-from-browser': 'chrome',
        'cookies': 'cookies.txt'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
        wav_path = glob.glob(str(Path(tmp_path) / '*.wav'))
        if not wav_path:
            raise Exception(f"Fail to download: {url}")
        wav_path = wav_path[0]
        os.makedirs(Path(output_path).parent, exist_ok=True)
        shutil.move(wav_path, output_path)
        os.rmdir(tmp_path)
    return output_path