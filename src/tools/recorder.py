import os
import queue
import sys
import threading
from typing import *

import sounddevice as sd
import soundfile as sf


class Recorder:
    def __init__(self) -> None:
        self.data_queue = queue.Queue()

        self.sem = threading.BoundedSemaphore(1)
        self.is_running = False

        self.stream = None

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

    def set_default_samplerate(self, samplerate: Optional[int] = None):
        now_sr = sd.default.samplerate
        sd.default.samplerate = samplerate, now_sr if now_sr is None else now_sr[1]

    def open_stream(self, device, samplerate: int, device_channels: int, callback: Callable):
        if self.is_running:
            self.is_running = False
        self.sem.acquire()
        self.sem.release()
        while not self.data_queue.empty():
            self.data_queue.get()

        if self.stream is not None:
            self.stream.close()

        self.stream = sd.InputStream(
            samplerate=samplerate,
            device=device,
            channels=device_channels,
            callback=callback,
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

    def rec_callback(self, indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)

        self.data_queue.put(indata.copy())

    def rec(
        self,
        basepath: str,
        filename: str,
        ext: str,
        device,
        samplerate: int,
        channels: int,
        subtype: str,
        save_individual: bool = False,
        individual_channels: int = 1,
        fragments_data: Optional[queue.Queue] = None,
        device_config_channels: Optional[int] = None,
    ):
        if self.is_running:
            self.is_running = False
        self.sem.acquire()
        while not self.data_queue.empty():
            self.data_queue.get()
        fragments = None
        if save_individual:
            # num_files = channels // indivisual_channels
            residual_chan = channels % individual_channels
            filenames = [
                os.path.join(basepath, f"ch{c+1}", f"{filename}.{ext}")
                for c in range(0, channels, individual_channels)
            ]
            for fn in filenames:
                os.makedirs(os.path.dirname(fn), exist_ok=True)
            sound_files = [
                sf.SoundFile(
                    file,
                    mode="w+",
                    samplerate=samplerate,
                    channels=individual_channels,
                    subtype=subtype,
                )
                for file in filenames
            ]
            channels_list = [
                (s, s + individual_channels) for s in range(0, channels, individual_channels)
            ]
            if residual_chan > 0:
                filenames.append(
                    os.path.join(
                        basepath,
                        f"ch{channels - residual_chan}",
                        f"{filename}.{ext}",
                    )
                )
                os.makedirs(os.path.dirname(filenames[-1]), exist_ok=True)
                sound_files.append(
                    sf.SoundFile(
                        filenames[-1],
                        mode="w+",
                        samplerate=samplerate,
                        channels=channels - residual_chan,
                        subtype=subtype,
                    )
                )
                channels_list.append((channels - residual_chan, channels))
            with sd.InputStream(
                samplerate=samplerate,
                device=device,
                channels=channels if device_config_channels is None else device_config_channels,
                callback=self.rec_callback,
            ):
                print("### recording... ###")
                print(channels_list, self)
                self.is_running = True
                while self.is_running:
                    data = self.data_queue.get()
                    for f, c in zip(sound_files, channels_list):
                        f.write(data[:, c[0] : c[1]])
            for f in sound_files:
                f.flush()
                f.close()
            fragments = {f"{ch[0]+1}": name for ch, name in zip(channels_list, filenames)}
        else:
            filenames = os.path.join(
                basepath,
                f"{filename}.{ext}",
            )
            os.makedirs(os.path.dirname(filenames), exist_ok=True)
            with sf.SoundFile(
                filenames,
                mode="w+",
                samplerate=samplerate,
                channels=channels,
                subtype=subtype,
            ) as f:
                with sd.InputStream(
                    samplerate=samplerate,
                    device=device,
                    channels=channels if device_config_channels is None else device_config_channels,
                    callback=self.rec_callback,
                ):
                    print("### recording... ###")
                    self.is_running = True
                    while self.is_running:
                        f.write(self.data_queue.get())
            fragments = {"1": filenames}
        while not self.data_queue.empty():
            self.data_queue.get()
        print("### recorded ###")
        self.sem.release()

        if not fragments_data is None:
            fragments_data.put(fragments)

        return fragments

    def stop(self):
        self.is_running = False
