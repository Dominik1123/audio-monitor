from collections import deque
from datetime import datetime, timedelta
from io import BytesIO
import logging
from queue import Queue
import re
from subprocess import check_output, run
from threading import Lock, Thread
import time
import traceback

import matplotlib.pyplot as plt
import numpy as np
from scipy.io.wavfile import read as wav_read
from scipy.io.wavfile import write as wav_write
import telepot
from telepot.loop import MessageLoop
from urllib3.exceptions import ProtocolError

import config


audio_queue = Queue()
error_queue = Queue()


def record_audio():
    wav_file = 'chunk.wav'
    run(['arecord',
          '-D', f'hw:{config.audio.device}',
          '-f', f'{config.audio.format}',
          '-r', f'{config.audio.sample_rate}',
          '-c', f'{config.audio.channels}',
          '-d', f'{config.audio.chunk_duration}',
          wav_file],
        check=True)
    sample_rate, data = wav_read(wav_file)
    return data


def listen():
    while True:
        try:
            audio_queue.put(record_audio())
        except Exception as err:
            error_queue.put(err)


class Analyzer(Thread):
    def __init__(self):
        super().__init__()
        self.audio = deque(maxlen=config.ui.maximum_playback // config.audio.chunk_duration)
        self.timestamps = []
        self.amplitude_max = []
        self.amplitude_mean = []
        self.callbacks = []
        self.lock = Lock()

    def run(self):
        while True:
            try:
                self.process_chunk(audio_queue.get())
            except Exception as err:
                error_queue.put(err)

    def process_chunk(self, chunk):
        with self.lock:
            self.audio.append(chunk)
            chunk = np.abs(chunk)
            if len(chunk.shape) > 1:
                chunk = chunk.mean(axis=1)  # average over channels
            chunk = chunk.reshape(config.audio.chunk_duration, config.audio.sample_rate)  # per second
            chunk_max = chunk.max(axis=1)
            chunk_mean = chunk.mean(axis=1)
            self.amplitude_max.extend(chunk_max)
            self.amplitude_mean.extend(chunk_mean)
            now = datetime.now()
            self.timestamps.extend(now - timedelta(seconds=i) for i in range(len(chunk), 0, -1))
            logging.info(f'amplitude max, mean: ({chunk_max}, {chunk_mean})')
        if np.any(chunk_max > config.ui.threshold):
            for callback in self.callbacks:
                callback(chunk_max)


class TelegramUI:
    def __init__(self, analyzer):
        self.bot = telepot.Bot(config.ui.bot_token)
        self.chat_id = config.ui.chat_id
        self.analyzer = analyzer
        self._handle_ping('')
        self.analyzer.callbacks.append(self.notify)

    def handle(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        if chat_id == self.chat_id and content_type == 'text':
            cmd = re.match(r'^/([a-z]+)', msg['text'])
            if cmd is not None:
                try:
                    handler = getattr(self, f'_handle_{cmd.group(1)}')
                except AttributeError:
                    logging.info(f'Unknown command: {cmd.group(0)}')
                    self._reply(f'Unknown_command: {cmd.group(0)}')
                else:
                    try:
                        handler(msg['text'].replace(cmd.group(0), '', 1).lstrip())
                    except Exception as err:
                        logging.critical(traceback.format_exc())
                        self._reply(str(err))
        elif chat_id != self.chat_id:
            logging.info(f'Denied message from chat id {chat_id} ({msg})')

    def _handle_listen(self, text):
        duration = int(text) // config.audio.chunk_duration if text.strip() else 0
        if len(self.analyzer.audio) > 0:
            with self.analyzer.lock:
                audio = np.concatenate(tuple(self.analyzer.audio)[-duration:])
                self.analyzer.audio.clear()
            wav_file = 'listen.wav'
            wav_write(wav_file, config.audio.sample_rate, audio)
            opus = check_output(['opusenc', wav_file, '-'])
            stream = BytesIO(opus)
            stream.seek(0)
            self._send('voice', stream)
        else:
            self._reply('No audio recorded yet')

    def _handle_plot(self, text):
        fig = plt.figure()
        ax = fig.add_subplot()
        ax.set_xlabel('')
        ax.set_ylabel('sound pressure [a.u.]')
        with self.analyzer.lock:
            timestamps = [t.timestamp() for t in self.analyzer.timestamps]
            ax.plot([timestamps[0], timestamps[-1]], [config.ui.threshold]*2, '--', color='#d62728')
            ax.plot(timestamps, self.analyzer.amplitude_max, '-', label='max', color='#1f77b4')
            ax.plot(timestamps, self.analyzer.amplitude_mean, '-', label='mean', color='#ff7f0e')
        ax.legend()
        x_ticks = ax.get_xticks()
        ax.set_xticklabels([datetime.fromtimestamp(t).strftime('%H:%M:%S') for t in x_ticks], rotation=90)
        stream = BytesIO()
        fig.savefig(stream, bbox_inches='tight', pad_inches=0)
        stream.seek(0)
        self._send('photo', stream)

    def _handle_ping(self, text):
        self._reply('\N{Waving Hand Sign}')

    def _handle_threshold(self, text):
        config.ui.threshold = int(text)
        self._reply(f'\N{White Heavy Check Mark} `threshold = {config.ui.threshold}`')

    def _handle_reset(self, text):
        with self.analyzer.lock:
            self.analyzer.audio.clear()
            self.analyzer.timestamps.clear()
            self.analyzer.amplitude_mean.clear()
            self.analyzer.amplitude_max.clear()
        self._reply('\N{White Heavy Check Mark}')

    def notify(self, values):
        self._handle_plot('')
        self._handle_listen(f'{config.ui.notify_playback}')
        self._reply('\N{Bell}')

    def _reply(self, msg_text):
        self.send_message(msg_text)

    def _send(self, media_type, *args, **kwargs):
        logging.debug(f'sending message: {args} {kwargs} as {media_type}')
        try:
            getattr(self.bot, f'send{media_type.capitalize()}')(self.chat_id, *args, **kwargs)
        except ProtocolError:
            time.sleep(0.1)
            self.bot = telepot.Bot(config.ui.bot_token)
            self._send(media_type, *args, **kwargs)

    def send_message(self, msg_text):
        self._send('message', msg_text, parse_mode='markdown')


def handle_errors(ui):
    while True:
        ui.send_message(f'\N{Heavy Exclamation Mark Symbol} {error_queue.get()}')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    analyzer = Analyzer()
    analyzer.start()

    recorder = Thread(target=listen)
    recorder.start()

    ui = TelegramUI(analyzer)
    loop = MessageLoop(ui.bot, ui.handle)
    loop.run_as_thread()

    error_handler = Thread(target=handle_errors, args=(ui,))
    error_handler.start()

    while True:
        time.sleep(10)
