import os

import soundfile
import numpy as np
import webrtcvad
import tqdm
# from paddlespeech.cli.asr.infer import ASRExecutor
import whisper
# from paddlespeech.cli.text.infer import TextExecutor
from loguru import logger
from pathlib import Path
from pydub import AudioSegment


class ASR:
    def __init__(self):
        # self.text_punc = TextExecutor()
        # self.asr = ASRExecutor()
        self.asr = whisper.load_model("medium")

    def asr_audio(self, audio):
        result = whisper.transcribe(self.asr, audio, prompt='这是一段中文访谈录音，请注意标注断句和问句。')
        logger.success(result)
        return result

    def asr_crop(self, wavfile_path, lang='zh'):
        if lang not in ['zh', 'en', 'zh_en']:
            return None
        if Path(wavfile_path).suffix == '.m4a':
            logger.warning("Need to reformat input to WAV.")
            song = AudioSegment.from_file(wavfile_path)
            wavfile_path2 = Path(wavfile_path).parent / (Path(wavfile_path).stem + '.wav')
            song.export(str(wavfile_path2), 'wav')
            wavfile_path = str(wavfile_path2)
        samples, sample_rate = soundfile.read(wavfile_path, dtype='int16')
        if sample_rate != 16000:
            logger.warning('Need to convert to 16Hz.')
            audio = AudioSegment.from_wav(wavfile_path).set_frame_rate(16000)
            new_audio_path = Path(wavfile_path).parent / ("16hz_" + str(Path(wavfile_path).stem) + '.wav')
            audio.export(str(new_audio_path), format='wav')
            samples, sample_rate = soundfile.read(new_audio_path, dtype='int16')

        # 对音频进行分块
        x_len = len(samples)
        assert sample_rate == 16000, 'Sample rate should be 16bit'
        # VAD 以10ms为单位进行划分
        chunk_size = int(10 * sample_rate / 1000)  # 10ms, sample_rate = 16kHz

        if x_len % chunk_size != 0:
            padding_len_x = chunk_size - x_len % chunk_size
        else:
            padding_len_x = 0

        padding = np.zeros((padding_len_x, 2), dtype=samples.dtype) if not isinstance(samples[0],
                                                                                      np.int16) else np.zeros(
            (padding_len_x,), dtype=samples.dtype)

        padded_x = np.concatenate([samples, padding], axis=0)

        assert (x_len + padding_len_x) % chunk_size == 0
        num_chunk = (x_len + padding_len_x) / chunk_size
        num_chunk = int(num_chunk)
        chunk_wavs = []
        for i in range(0, num_chunk):
            start = i * chunk_size
            end = start + chunk_size
            x_chunk = padded_x[start:end]
            chunk_wavs.append(x_chunk)

        vad = webrtcvad.Vad(1)
        # 每一个静音的长度
        sil_flag = False
        sil_indexes = []  # 切分后的 index 信息
        sil_length = []

        RATE = sample_rate
        # 通过 webrtc 检测静音帧
        start = 0
        for idx, chunk in tqdm.tqdm(enumerate(chunk_wavs)):
            active = vad.is_speech(chunk.tobytes(), RATE)
            # print(active)
            if not active:
                # 是静音帧
                if not sil_flag:
                    start = idx
                sil_flag = True
            else:
                if sil_flag:
                    # 刚刚结束
                    sil_flag = False
                    end = idx
                    sil_indexes.append((start, end, end - start))
                    sil_length.append((end - start))

        # 句子间的间隔时长为 1000 ms
        # 可以根据句子的实际情况进行调整
        min_sentence_sil_duration = 50  # VAD 一帧 10 ms

        split_start = 0
        sub_wav_max_length = 50
        sub_wavs = []
        for start, end, dur in tqdm.tqdm(sil_indexes):
            if dur > min_sentence_sil_duration:
                mid_split = int((start + end) / 2 * (RATE / 100))
                sub_wavs.append(samples[split_start:mid_split])
                split_start = mid_split
        # 最后结尾
        if split_start < len(samples):
            sub_wavs.append(samples[split_start:len(samples)])

        sub_wavs_processed = []
        for sub_wav in sub_wavs:
            if len(sub_wav) / sample_rate >= sub_wav_max_length:
                cuts = int(len(sub_wav) / sample_rate // sub_wav_max_length + 1)
                cut_sample_num = len(sub_wav) // cuts
                for i in range(1, cuts + 1):
                    if i * cut_sample_num > len(sub_wav):
                        sub_wavs_processed.append(sub_wav[(i - 1) * cut_sample_num:])
                    else:
                        sub_wavs_processed.append(sub_wav[(i - 1) * cut_sample_num: i * cut_sample_num])
            else:
                sub_wavs_processed.append(sub_wav)

        sub_wavs = sub_wavs_processed

        long_asr_result = ""
        for idx, sub_wav in tqdm.tqdm(enumerate(sub_wavs)):
            temp_path = 'temp'
            os.makedirs(temp_path, exist_ok=True)
            audio_path = f"{temp_path}/temp_{idx}.wav"
            soundfile.write(audio_path, sub_wav, sample_rate)
            asr_result = self.asr_audio(audio_path)
            if asr_result:
                # 有识别结果才恢复标点
                # text_result = self.text_punc(text=asr_result['text'], lang=lang)
                long_asr_result += asr_result['text']
                logger.info(asr_result['text'])
        logger.success(long_asr_result)
        return long_asr_result

    def asr_bulk(self, audio):
        return self.asr_audio(audio)

    def __call__(self, *args, **kwargs):
        return self.asr_bulk(*args, **kwargs)