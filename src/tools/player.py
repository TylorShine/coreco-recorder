import queue
import sys
import threading
from typing import *

import sounddevice as sd
import soundfile as sf


class Player:
    def __init__(self, buffersize: int = 20, blocksize: int = 2048) -> None:
        self.data_queue = queue.Queue(maxsize=buffersize)

        self.sem = threading.BoundedSemaphore(1)
        self.is_running = False

        self.volume = 1.0

        self.buffersize = buffersize
        self.blocksize = blocksize

        self.playback_pos = 0
        self.continue_pos = 0

        self.stream = None

        self.event = threading.Event()

    def get_devices(self):
        return sd.query_devices()

    def get_devices_dict(self):
        devices = {"inputs": {}, "outputs": {}}
        for hostapi in sd.query_hostapis():
            hostapi_name = hostapi["name"]
            devices["inputs"][hostapi_name] = {}
            devices["outputs"][hostapi_name] = {}
            for i in hostapi["devices"]:
                device = sd.query_devices(device=i)
                if device["max_input_channels"] > 0:
                    devices["inputs"][hostapi_name][device["index"]] = device
                if device["max_output_channels"] > 0:
                    devices["outputs"][hostapi_name][device["index"]] = device
        return devices

    def get_default_device(self):
        return sd.default.device

    def get_buffer_settings(self):
        return self.buffersize, self.blocksize

    def set_volume(self, vol: float):
        self.volume = vol

    def open_stream(
        self,
        device,
        samplerate: int,
        device_channels: int,
        blocksize: Optional[int] = None,
        callback: Optional[Callable] = None,
    ):
        if self.is_running:
            self.is_running = False
        self.sem.acquire()
        self.sem.release()
        while not self.data_queue.empty():
            self.data_queue.get()

        if self.stream is not None:
            self.stream.close()

        self.stream = sd.RawOutputStream(
            samplerate=samplerate,
            blocksize=self.blocksize if blocksize is None else blocksize,
            device=device,
            channels=device_channels,
            dtype="float32",
            callback=self.play_callback if callback is None else callback,
        )
        if self.stream is None:
            return None
        self.stream.start()

        return self.stream

    def close_stream(self):
        if self.is_running:
            self.is_running = False
            self.sem.acquire()
            self.sem.release()
        if self.stream is not None:
            self.stream.close()
            self.stream = None
        return self.stream

    def play_callback(self, outdata, frames, time, status):
        assert frames == self.blocksize
        if status.output_underflow:
            # output buffer underflow, suggest: increase blocksize
            # print(status, file=sys.stderr)
            raise sd.CallbackAbort
        assert not status
        try:
            data = self.data_queue.get_nowait()
        except queue.Empty:
            # buffer is empty, suggest: increase buffersize
            raise sd.CallbackAbort
        if len(data) < len(outdata):
            outdata[: len(data)] = data
            outdata[len(data) :] = b"\x00" * (len(outdata) - len(data))
            raise sd.CallbackStop
        else:
            outdata[:] = data
            if not self.is_running:
                raise sd.CallbackAbort

    def play(
        self,
        filename: str,
        device,
        end_callback: Optional[Callable] = None,
        continue_pos: int = 0,
        stop_pos_from_end: int = -1,
    ):
        if self.is_running:
            self.is_running = False
        self.sem.acquire()
        while not self.data_queue.empty():
            self.data_queue.get()
        # self.data_queue = queue.Queue(maxsize=self.buffersize)
        self.event = threading.Event()
        with sf.SoundFile(filename) as f:
            f.seek(continue_pos)
            for _ in range(self.buffersize):
                data = f.buffer_read(self.blocksize, dtype="float32")
                if not data:
                    break
                self.data_queue.put_nowait(data)

            self.is_running = True

            stream = sd.RawOutputStream(
                samplerate=f.samplerate,
                blocksize=self.blocksize,
                device=device,
                channels=f.channels,
                dtype="float32",
                callback=self.play_callback,
                finished_callback=self.event.set,
            )
            with stream:
                timeout = self.blocksize * self.buffersize / f.samplerate
                while len(data):
                    if not self.is_running:
                        self.event.set()
                        break
                    read_size = self.blocksize
                    if stop_pos_from_end >= 0 and f.frames - self.playback_pos < stop_pos_from_end:
                        read_size = f.frames - self.playback_pos - stop_pos_from_end
                    data = f.buffer_read(read_size, dtype="float32")
                    self.data_queue.put(data, timeout=timeout)
                    self.playback_pos = f.tell()
                    if read_size < self.blocksize:
                        self.event.set()
                        break
                #     print(f"running: {self.is_running}")
                # print(f"waiting")
                self.event.wait()
                # print(f"waited")

        self.playback_pos = 0
        self.is_running = False
        self.sem.release()
        if not end_callback is None:
            end_callback()

    def pause(self):
        self.continue_pos = self.playback_pos
        self.is_running = False
        return self.continue_pos

    def toggle_play(self, filename: str, device, end_callback=None):
        if self.is_running:
            self.pause()
        else:
            self.play(filename, device, end_callback, self.continue_pos)

    def stop(self):
        self.is_running = False
