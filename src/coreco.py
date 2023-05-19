import os
import queue
import shutil
import string
import sys
import threading
import tkinter
from tkinter import filedialog
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import customtkinter
import librosa
import numpy as np
import sounddevice as sd
import soundfile as sf
from scipy import signal

from tools import loader, player, project_manager, recorder

# TODO: tag edit using open license...
# class TagsManager:
#     def __init__(self, project_manager: project_manager.ProjectManager) -> None:
#         self.project_manager = project_manager

#         self.tmpl_track = "${TEXT_TYPE}_${TEXT_NUMBER4}"
#         self.tmpl_artist = ""
#         self.tmpl_album = "${PROJECT_NAME}-${TEXT_TYPE}"
#         self.tmpl_comment = "${VERSION}"
#         self.rendering_file_pattern = "${PROJECT_NAME}/ch${CHANNEL_NUMBER}/${TEXT_TYPE}/${TEXT_TYPE}_${TEXT_NUMBER4}.${OUTPUT_EXT}"


# class TagSettingsWindow(customtkinter.CTkToplevel):
#     def __init__(self, *args, fg_color: str | Tuple[str, str] | None = None, **kwargs):
#         super().__init__(*args, fg_color=fg_color, **kwargs)


class RenderingSoundsWindow(customtkinter.CTkToplevel):
    def __init__(
        self,
        *args,
        project_manager: project_manager.ProjectManager,
        fg_color: str | Tuple[str, str] | None = None,
        **kwargs,
    ):
        super().__init__(*args, fg_color=fg_color, **kwargs)
        self.title(f"CoReco: {project_manager.get_project_name()}: 音声の書き出し")
        self.geometry("850x360")

        # modules
        self.project_manager = project_manager

        # callbacks
        validate_digit = self.register(self.validate_digit_callback)

        # variables
        a = [int(2 ** (i) + 1 * (i >= 0)) for i in range(-1, 3)]
        self.rendering_samplerate_list = [
            str(
                [4000, 11025][fsi]
                * (
                    (v + 1 + a[ivit] + ivit // 2 * 2) * (1 - fsi)
                    + 2 ** int(a[ivit] / 2 + 0.5) * fsi
                )
            )
            for ivit, vit in enumerate(
                [(tuple(range(a[ra + 1])), (ra,)) for ra in range(len(a) - 1)]
            )
            for fsi, vi in enumerate(vit)
            for v in vi
        ] + [
            str(fs * 2 ** (i + 3 * (fsi) - 1))
            for i in range(1, 6)
            for fsi, fs in enumerate([48000, 11025])
        ][
            :-1
        ]
        self.rendering_samplerate = "48000"
        self.rendering_format_dict = sf.available_formats()
        self.rendering_format = (
            "wav"
            if "WAV" in self.rendering_format_dict.keys()
            else list(self.rendering_format_dict.keys())[0].lower()
        )
        self.rendering_format_list = [f.lower() for f in self.rendering_format_dict.keys()]
        self.rendering_subtype_dict = sf.available_subtypes(self.rendering_format)
        self.rendering_subtype = (
            "PCM_16"
            if "PCM_16" in self.rendering_subtype_dict.keys()
            else list(self.rendering_subtype_dict.keys())[0]
        )
        self.rendering_subtype_list = list(self.rendering_subtype_dict.keys())
        self.rendering_output_dir = "out"
        self.rendering_file_pattern = (
            "${PROJECT_NAME}/ch${CHANNEL_NUMBER}/${TEXT_TYPE}/${TEXT_NAME}.${OUTPUT_EXT}"
        )
        self.filter_order_db_dict = {"OFF": 0}
        self.filter_order_db_dict.update(**{f"{n * -6}dB/oct": n for n in range(1, 13)})
        self.filter_order_db_list = list(self.filter_order_db_dict.keys())
        self.filter_hpf_order = 0
        self.filter_lpf_order = 0

        self.is_rendering = False
        self.render_thread = None

        # tkinter variables
        self.var_samplerate = tkinter.StringVar(self, self.rendering_samplerate)
        self.var_format = tkinter.StringVar(self, self.rendering_format)
        self.var_subtype = tkinter.StringVar(self, self.rendering_subtype)
        self.var_is_normalize = tkinter.BooleanVar(self, True)
        self.var_hpf_order = tkinter.StringVar(self, "OFF")
        self.var_lpf_order = tkinter.StringVar(self, "OFF")
        self.var_channels = tkinter.StringVar(self, "1-4")
        self.var_file_pattern = tkinter.StringVar(self, self.rendering_file_pattern)
        self.var_output_dir = tkinter.StringVar(self, self.rendering_output_dir)
        self.var_status = tkinter.StringVar(self, "準備完了")

        # main
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.main_frame = customtkinter.CTkFrame(self, width=480, corner_radius=0)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_columnconfigure((1, 2, 3), weight=1)
        self.main_frame.grid_rowconfigure((0, 1, 2, 3, 4, 5, 6, 7), weight=1)
        # self.sidebar_frame = customtkinter.CTkFrame(self, width=120, corner_radius=0)
        # self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        # self.sidebar_frame.grid_rowconfigure((0, 18), weight=0)
        # self.sidebar_frame.grid_rowconfigure(16, weight=1)
        self.format_label = customtkinter.CTkLabel(
            self.main_frame,
            text="フォーマット:",
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
        )
        self.format_label.grid(row=0, column=0, padx=16, pady=10)
        self.format_option = customtkinter.CTkOptionMenu(
            self.main_frame,
            values=self.rendering_format_list,
            variable=self.var_format,
            command=self.change_format_option_event,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.format_option.grid(row=0, column=1, padx=16, pady=10)
        self.samplerate_label = customtkinter.CTkLabel(
            self.main_frame,
            text="サンプルレート:",
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
        )
        self.samplerate_label.grid(row=0, column=2, padx=16, pady=10)
        self.samplerate_option = customtkinter.CTkOptionMenu(
            self.main_frame,
            values=self.rendering_samplerate_list,
            variable=self.var_samplerate,
            command=self.change_samplerate_option_event,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.samplerate_option.grid(row=0, column=3, padx=16, pady=10)

        self.subtype_label = customtkinter.CTkLabel(
            self.main_frame,
            text="詳細(ビット深度など):",
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
        )
        self.subtype_label.grid(row=1, column=0, padx=16, pady=10)
        self.subtype_option = customtkinter.CTkOptionMenu(
            self.main_frame,
            values=self.rendering_subtype_list,
            variable=self.var_subtype,
            command=self.change_subtype_option_event,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.subtype_option.grid(row=1, column=1, padx=16, pady=10)
        self.normalize_checkbox = customtkinter.CTkCheckBox(
            self.main_frame,
            text="音量をノーマライズ (dB)",
            variable=self.var_is_normalize,
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
        )
        self.normalize_checkbox.grid(row=1, column=2, padx=16, pady=10)
        self.normalize_target_entry = customtkinter.CTkEntry(
            self.main_frame,
            validate="all",
            validatecommand=(validate_digit, "%P"),
            placeholder_text="ピーク音量[dB]",
            justify="right",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.normalize_target_entry.grid(row=1, column=3, padx=16, pady=10, sticky="ew")

        self.filter_hpf_label = customtkinter.CTkLabel(
            self.main_frame,
            text="ハイパスフィルタ:",
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
        )
        self.filter_hpf_label.grid(row=2, column=0, padx=16, pady=10)
        self.filter_hpf_option = customtkinter.CTkOptionMenu(
            self.main_frame,
            values=self.filter_order_db_list,
            variable=self.var_hpf_order,
            command=self.change_hpf_option_event,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.filter_hpf_option.grid(row=2, column=1, padx=16, pady=10)
        self.filter_hpf_entry = customtkinter.CTkEntry(
            self.main_frame,
            validate="all",
            validatecommand=(validate_digit, "%P"),
            placeholder_text="周波数[Hz]",
            justify="right",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.filter_hpf_entry.grid(row=2, column=2, columnspan=2, padx=16, pady=10, sticky="ew")

        self.text_number_label = customtkinter.CTkLabel(
            self.main_frame,
            text="テキスト番号範囲:",
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
            anchor="e",
        )
        self.text_number_label.grid(row=3, column=0, padx=16, pady=10)
        self.text_number_entry = customtkinter.CTkEntry(
            self.main_frame,
            placeholder_text="範囲を入力 例: 1-4 (連続範囲)、2,5,7 (個別指定)、1-3,8,11 (組み合わせ)、空欄で全て",
            # textvariable=self.var_channels,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.text_number_entry.grid(row=3, column=1, padx=16, pady=10, sticky="ew")
        self.channels_label = customtkinter.CTkLabel(
            self.main_frame,
            text="チャンネル範囲:",
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
            anchor="e",
        )
        self.channels_label.grid(row=3, column=2, padx=16, pady=10)
        self.channels_entry = customtkinter.CTkEntry(
            self.main_frame,
            placeholder_text="範囲を入力 例: 1-4 (連続範囲)、2,5,7 (個別指定)、1-3,8,11 (組み合わせ)、空欄で全て",
            # textvariable=self.var_channels,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.channels_entry.grid(row=3, column=3, padx=16, pady=10, sticky="ew")

        self.pattern_label = customtkinter.CTkLabel(
            self.main_frame,
            text="ファイル名パターン:",
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
        )
        self.pattern_label.grid(row=4, column=0, padx=16, pady=10)
        self.pattern_entry = customtkinter.CTkEntry(
            self.main_frame,
            placeholder_text="パターンを入力 例: ${PROJECT_NAME}/ch${CHANNEL_NUMBER}/${TEXT_TYPE}/${TEXT_TYPE}_${TEXT_NUMBER4}.${OUTPUT_EXT}",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.pattern_entry.grid(row=4, column=1, columnspan=3, padx=16, pady=10, sticky="ew")
        self.output_dir_entry = customtkinter.CTkEntry(
            self.main_frame,
            placeholder_text="出力先ディレクトリを入力",
            # textvariable=self.var_output_dir,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.output_dir_entry.grid(row=5, column=0, columnspan=3, padx=16, pady=10, sticky="ew")
        self.select_output_dir_button = customtkinter.CTkButton(
            self.main_frame,
            text="参照",
            command=self.select_directory,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.select_output_dir_button.grid(row=5, column=3, padx=16, pady=10)

        self.run_output_button = customtkinter.CTkButton(
            self.main_frame,
            text="書き出し",
            command=self.run_rendering,
            font=customtkinter.CTkFont("Noto Sans JP", size=14, weight="bold"),
        )
        self.run_output_button.grid(row=6, column=0, columnspan=4, padx=16, pady=10, sticky="ew")

        self.status_label = customtkinter.CTkLabel(
            self.main_frame,
            textvariable=self.var_status,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
            anchor="w",
        )
        self.status_label.grid(row=7, column=0, columnspan=4, padx=8, sticky="ew")

        # defaults
        self.pattern_entry.insert(0, self.rendering_file_pattern)
        self.output_dir_entry.insert(0, self.rendering_output_dir)
        self.normalize_target_entry.insert(0, "-3.0")
        self.filter_hpf_entry.insert(0, "60.0")

        self.main_frame.bind("<Button-1>", self.set_focus_to_root)
        self.normalize_target_entry.bind("<KeyPress-Return>", self.set_focus_to_root)
        self.filter_hpf_entry.bind("<KeyPress-Return>", self.set_focus_to_root)
        self.channels_entry.bind("<KeyPress-Return>", self.set_focus_to_root)
        self.pattern_entry.bind("<KeyPress-Return>", self.set_focus_to_root)
        self.output_dir_entry.bind("<KeyPress-Return>", self.set_focus_to_root)

        # self.focus_set()
        # self.after(800, self.focus_set())
        # self.main_frame.focus_set()

    def change_format_option_event(self, new_selected_format: str):
        self.rendering_format = new_selected_format
        self.rendering_subtype_dict = sf.available_subtypes(new_selected_format)
        self.rendering_subtype_list = list(self.rendering_subtype_dict.keys())
        self.rendering_subtype = (
            self.rendering_subtype
            if self.rendering_subtype in self.rendering_subtype_list
            else self.rendering_subtype_list[0]
        )
        self.subtype_option.configure(
            values=self.rendering_subtype_list,
        )
        self.var_subtype.set(self.rendering_subtype)

    def change_subtype_option_event(self, new_selected_subtype: str):
        self.rendering_subtype = new_selected_subtype

    def change_samplerate_option_event(self, new_selected_samplerate: str):
        self.rendering_samplerate = int(new_selected_samplerate)
        now_hpf_freq = self.filter_hpf_entry.get()
        if now_hpf_freq != "" and float(now_hpf_freq) > self.rendering_samplerate / 2:
            self.filter_hpf_entry.delete(0, "end")
            self.filter_hpf_entry.insert(0, f"{int(self.rendering_samplerate/2)}")

    def change_hpf_option_event(self, new_selected_order: str):
        self.filter_hpf_order = self.filter_order_db_dict[new_selected_order]

    def change_lpf_option_event(self, new_selected_order: str):
        self.filter_lpf_order = self.filter_order_db_dict[new_selected_order]

    def validate_digit_callback(self, P):
        try:
            float(P)
        except ValueError:
            return P == ""
        return True

    def update_status(self, status_text: str):
        self.var_status.set(status_text)

    def set_focus_to_root(self, evt):
        self.focus_set()

    def select_directory(self):
        dir = filedialog.askdirectory(
            title="出力先ディレクトリを選択",
            initialdir=self.output_dir_entry.get(),
        )
        if dir == "":
            self.focus_set()
            return
        self.var_output_dir.set(dir)
        self.output_dir_entry.delete(0, "end")
        self.output_dir_entry.insert(0, dir)
        self.focus_set()

    def rendering_thread(
        self,
        in_filename: str,
        out_filename: str,
        format: str,
        samplerate: int,
        subtype: str,
        start_time: float = 0.0,
        stop_from_end_time: float = 0.0,
        is_normalize: bool = False,
        normalize_target_db: float = -6.0,
        filt_hp_sos: Optional[Any] = None,
        filt_lp_sos: Optional[Any] = None,
    ):
        if not os.path.exists(in_filename):
            print(f"error: cannot found file {in_filename}", file=sys.stderr)
            return
        os.makedirs(os.path.dirname(out_filename), exist_ok=True)
        with sf.SoundFile(in_filename) as f:
            if (
                (not is_normalize)
                and start_time <= 0.0
                and stop_from_end_time <= 0.0
                and int(f.samplerate) == samplerate
                and f.format == format.upper()
                and f.subtype == subtype
            ):
                # simply copy file
                shutil.copy2(in_filename, out_filename)
                return
            # seek
            start_sample = int(start_time * f.samplerate)
            if start_time > 0.0:
                if f.frames > start_sample:
                    f.seek(start_sample)
            # converting
            with sf.SoundFile(
                out_filename,
                "w",
                samplerate,
                f.channels,
                subtype,
                format=format.upper(),
            ) as fout:
                stop_sample = int(f.frames - stop_from_end_time * f.samplerate) - start_sample

                # need resample?
                if is_normalize:
                    # need hpf?
                    if not filt_hp_sos is None:
                        data = signal.sosfilt(filt_hp_sos, f.read(frames=stop_sample))
                    else:
                        data = f.read(frames=stop_sample)
                    # normalize peak
                    norm_target = 10 ** (normalize_target_db / 20)
                    if int(f.samplerate) != samplerate:
                        data = librosa.resample(
                            data,
                            orig_sr=f.samplerate,
                            target_sr=samplerate,
                        )

                    data_min, data_max = data.min(), data.max()
                    eps = 1e-15
                    norm_gain = 1.0 / (max(abs(data_min), abs(data_max)) + eps) * norm_target
                    fout.write(data[:] * norm_gain)
                else:
                    if int(f.samplerate) != samplerate:
                        # need hpf?
                        if not filt_hp_sos is None:
                            fout.write(
                                librosa.resample(
                                    signal.sosfilt(filt_hp_sos, f.read(frames=stop_sample)),
                                    orig_sr=f.samplerate,
                                    target_sr=samplerate,
                                )
                            )
                        else:
                            fout.write(
                                librosa.resample(
                                    f.read(frames=stop_sample),
                                    orig_sr=f.samplerate,
                                    target_sr=samplerate,
                                )
                            )
                    else:
                        # need hpf?
                        if not filt_hp_sos is None:
                            fout.write(signal.sosfilt(filt_hp_sos, f.read(frames=stop_sample)))
                        else:
                            fout.write(f.read(frames=stop_sample))

    def parse_values_select_text(self, values_text: str):
        targets = []
        if values_text != "":
            for val in values_text.split(","):
                val_split = val.split("-")
                if len(val_split) > 2:
                    v_start, v_end, v_step = val_split[:3]
                    if v_start.isdecimal() and v_end.isdecimal() and v_step.isdecimal():
                        targets.extend(
                            (str(v) for v in range(int(v_start), int(v_end) + 1, int(v_step) + 1))
                        )
                elif len(val_split) > 1:
                    v_start, v_end = val_split
                    if v_start.isdecimal() and v_end.isdecimal():
                        targets.extend((str(v) for v in range(int(v_start), int(v_end) + 1)))
                elif val_split[0].isdecimal():
                    targets.append(val_split[0])
        return targets

    def run_rendering(self):
        print(
            f"format: {self.var_format.get()}, sr: {self.var_samplerate.get()}, ch: {self.channels_entry.get()}"
        )
        print(f"text_number: {self.text_number_entry.get()}")
        print(f"pattern: {self.pattern_entry.get()}, dir: {self.output_dir_entry.get()}")
        print(
            f"normalize: {self.var_is_normalize.get()}, norm_target: {self.normalize_target_entry.get()}"
        )
        records = self.project_manager.get_all_recordings()
        print(
            [
                f'{r["id"]}: {r["takes"][r["use_take"]]["record"][t]}'
                for r in records
                if "use_take" in r and "record" in r["takes"][r["use_take"]]
                for t in r["takes"][r["use_take"]]["record"].keys()
            ]
        )
        # parse selection numbers text
        target_text_numbers = self.parse_values_select_text(self.text_number_entry.get())
        target_channels = self.parse_values_select_text(self.channels_entry.get())

        template_filename = string.Template(self.pattern_entry.get())

        proj_name = self.project_manager.get_project_name()
        output_format = self.var_format.get().lower()
        output_dir = self.output_dir_entry.get()
        samplerate = int(self.var_samplerate.get())
        subtype = self.var_subtype.get()
        is_normalize = self.var_is_normalize.get()
        normalize_db = self.normalize_target_entry.get()

        normalize_db = -3.0 if normalize_db == "" else float(normalize_db)

        hpf_freq = self.filter_hpf_entry.get()
        hpf_freq = 0.0 if hpf_freq == "" else float(hpf_freq)
        hpf_sos = (
            None
            if self.filter_hpf_order <= 0
            else signal.butter(
                self.filter_hpf_order, max(0.0, hpf_freq), "hp", fs=samplerate, output="sos"
            )
        )

        # lpf_freq = self.filter_lpf_entry.get()
        # lpf_freq = 0.0 if lpf_freq == "" else float(lpf_freq)
        # lpf_sos = (
        #     None
        #     if self.filter_lpf_order <= 0
        #     else signal.butter(
        #         self.filter_lpf_order, max(0.0, lpf_freq), "lp", fs=samplerate, output="sos"
        #     )
        # )

        self.is_rendering = True

        max_threads = max(1, os.cpu_count() - 2)  # TODO: UI?

        # mpmanager = multiprocessing.Manager()
        executed_count = 0
        # executed_count_lock = mpmanager.Lock()

        def render_process(
            in_file,
            take_num,
            ch,
            text,
            text_name,
            text_type,
            text_num,
            start_time,
            stop_from_end_time,
            hpf_sos=None,
            lpf_sos=None,
        ):
            if not self.is_rendering:
                return
            print(in_file)
            substitute_dict = {
                "PROJECT_NAME": proj_name,
                "TEXT": text,
                "TEXT_NAME": text_name,
                "TEXT_TYPE": text_type,
                "OUTPUT_EXT": output_format,
                "CHANNEL_NUMBER": ch,
                "TAKE_NUMBER": take_num,
                "TEXT_NUMBER": text_num,
            }
            substitute_dict.update(
                **{
                    k: v
                    for i in range(2, 9)
                    for s, sv in (
                        ("CHANNEL_NUMBER", ch),
                        ("TAKE_NUMBER", take_num),
                        ("TEXT_NUMBER", text_num),
                    )
                    for k, v in {
                        f"{s}{i}": f"{sv:0{i}}",
                    }.items()
                }
            )
            processed_filename = template_filename.safe_substitute(substitute_dict)
            filename = os.path.join(output_dir, processed_filename)
            print(f"outpath: {filename}")
            self.rendering_thread(
                in_filename=in_file,
                out_filename=filename,
                format=output_format,
                samplerate=samplerate,
                subtype=subtype,
                start_time=start_time,
                stop_from_end_time=stop_from_end_time,
                is_normalize=is_normalize,
                normalize_target_db=normalize_db,
                filt_hp_sos=hpf_sos,
                filt_lp_sos=lpf_sos,
            )
            # if not counter is None:
            #     counter += 1
            #     self.update_status(f"書き出し中... [{executed_count}]")
            # with executed_count_lock:
            #     executed_count += 1
            #     self.update_status(f"書き出し中... [{executed_count}]")

        # print(
        #     *[
        #         (
        #             f["takes"][f["use_take"]]["record"][c],
        #             f["use_take"],
        #             c,
        #             f["texts"]["text"]["0"],
        #             f["texts"]["name"],
        #             f["texts"]["type"],
        #             f["id"],
        #             0.0
        #             if "start" not in f["takes"][f["use_take"]]
        #             else f["takes"][f["use_take"]]["start"],
        #             0.0
        #             if "stop_from_end" not in f["takes"][f["use_take"]]
        #             else f["takes"][f["use_take"]]["stop_from_end"],
        #         )
        #         for f in records
        #         if (len(target_text_numbers) <= 0 or str(f["id"]) in target_text_numbers)
        #         and "use_take" in f
        #         and "record" in f["takes"][f["use_take"]]
        #         for c in f["takes"][f["use_take"]]["record"].keys()
        #         if len(target_channels) <= 0
        #         or c in target_channels
        #         and "texts" in f
        #         and "name" in f["texts"]
        #         and "type" in f["texts"]
        #         and "text" in f["texts"]
        #         and "0" in f["texts"]["text"]
        #     ]
        # )

        thread_queue = queue.Queue(maxsize=max_threads)
        # with ThreadPoolExecutor(max_workers=max_threads) as executor:
        for datas in [
            (
                f["takes"][f["use_take"]]["record"][c],
                f["use_take"],
                c,
                f["texts"]["text"]["0"],
                f'{f["texts"]["type"]}_{f["id"]:04}'
                if "name" not in f["texts"]
                else f["texts"]["name"],
                f["texts"]["type"],
                f["id"],
                0.0
                if "start" not in f["takes"][f["use_take"]]
                else f["takes"][f["use_take"]]["start"],
                0.0
                if "stop_from_end" not in f["takes"][f["use_take"]]
                else f["takes"][f["use_take"]]["stop_from_end"],
            )
            for f in records
            if (len(target_text_numbers) <= 0 or str(f["id"]) in target_text_numbers)
            and "use_take" in f
            and "record" in f["takes"][f["use_take"]]
            for c in f["takes"][f["use_take"]]["record"].keys()
            if len(target_channels) <= 0 or c in target_channels and "texts" in f
            # and "name" in f["texts"]
            and "type" in f["texts"] and "text" in f["texts"] and "0" in f["texts"]["text"]
        ]:
            # executor.map(
            #     render_process,
            #     datas,
            # )
            if thread_queue.full():
                thread_queue.get().join()
            renderer_thread = threading.Thread(target=render_process, args=(*datas, hpf_sos))
            renderer_thread.start()
            thread_queue.put(renderer_thread)
            executed_count += 1
            self.update_status(f"書き出し中... [{executed_count}]")
        # with executed_count_lock:
        #     executed_count += 1
        #     self.update_status(f"書き出し中... [{executed_count}]")
        while not thread_queue.empty():
            thread_queue.get().join(5.0)
        self.update_status(f"{executed_count}ファイルを書き出しました。")

        # for file, take_num, ch, text_type, text_num in (
        #     (
        #         f["takes"][f["use_take"]]["record"][c],
        #         f["use_take"],
        #         c,
        #         f["texts"]["type"],
        #         f["id"],
        #     )
        #     for f in records
        #     if (len(target_text_numbers) <= 0 or str(f["id"]) in target_text_numbers)
        #     and "use_take" in f
        #     and "record" in f["takes"][f["use_take"]]
        #     for c in f["takes"][f["use_take"]]["record"].keys()
        #     if len(target_channels) <= 0
        #     or c in target_channels
        #     and "texts" in f
        #     and "type" in f["texts"]
        # ):
        #     if not self.is_rendering:
        #         break
        #     print(file)
        #     substitute_dict = {
        #         "PROJECT_NAME": proj_name,
        #         "TEXT_TYPE": text_type,
        #         "OUTPUT_EXT": output_format,
        #         "CHANNEL_NUMBER": ch,
        #         "TAKE_NUMBER": take_num,
        #         "TEXT_NUMBER": text_num,
        #     }
        #     substitute_dict.update(
        #         **{
        #             k: v
        #             for i in range(2, 9)
        #             for s, sv in (
        #                 ("CHANNEL_NUMBER", ch),
        #                 ("TAKE_NUMBER", take_num),
        #                 ("TEXT_NUMBER", text_num),
        #             )
        #             for k, v in {
        #                 f"{s}{i}": f"{sv:0{i}}",
        #             }.items()
        #         }
        #     )
        #     processed_filename = template_filename.safe_substitute(substitute_dict)
        #     print(f"outpath: {os.path.join(output_dir, processed_filename)}")
        #     self.recorder_thread = threading.Thread(
        #         target=self.rec_writer_thread,
        #         kwargs=dict(
        #             basepath=basepath,
        #             filename=filename,
        #             ext=ext,
        #             channels=channels,
        #             individual_channels=2 if is_stereo else 1,
        #             samplerate=samplerate,
        #             subtype=subtype,
        #             queue=self.recorder_queue,
        #             fragments_data=self.rec_fragments_data,
        #         ),
        #     )
        #     self.recorder_thread.start()


class RecordingSettings:
    def __init__(self) -> None:
        self.recording_format_dict = sf.available_formats()
        self.recording_format = (
            "wav"
            if "WAV" in self.recording_format_dict.keys()
            else list(self.recording_format_dict.keys())[0].lower()
        )
        self.recording_format_list = [f.lower() for f in self.recording_format_dict.keys()]
        self.recording_subtype_dict = sf.available_subtypes(self.recording_format)
        self.recording_subtype = (
            "FLOAT"
            if "FLOAT" in self.recording_subtype_dict.keys()
            else list(self.recording_subtype_dict.keys())[0]
        )
        self.recording_subtype_list = list(self.recording_subtype_dict.keys())
        self.recording_is_stereo = False

    def get_format(self):
        return self.recording_format

    def get_subtype(self):
        return self.recording_subtype

    def get_is_stereo(self):
        return self.recording_is_stereo

    def get_format_list(self):
        return self.recording_format_list

    def get_subtype_list(self):
        return self.recording_subtype_list

    def set_format(self, format: str):
        if format in self.recording_format_list:
            self.recording_format = format
            self.recording_subtype_dict = sf.available_subtypes(format)
            self.recording_subtype_list = list(self.recording_subtype_dict.keys())
            self.recording_subtype = (
                self.recording_subtype
                if self.recording_subtype in self.recording_subtype_dict
                else self.recording_subtype_list[0]
            )

    def set_subtype(self, subtype: str):
        if subtype in self.recording_subtype_list:
            self.recording_subtype = subtype

    def set_is_stereo(self, is_stereo: bool):
        self.recording_is_stereo = is_stereo


class RecordingSettingsWindow(customtkinter.CTkToplevel):
    def __init__(
        self,
        *args,
        recording_settings: RecordingSettings,
        fg_color: str | Tuple[str, str] | None = None,
        **kwargs,
    ):
        super().__init__(*args, fg_color=fg_color, **kwargs)

        self.title("CoReco: 録音設定")
        self.geometry("620x180")

        # modules
        self.recording_settings = recording_settings

        # tkinter variables
        self.var_format = tkinter.StringVar(self, recording_settings.get_format())
        self.var_subtype = tkinter.StringVar(self, recording_settings.get_subtype())
        self.var_is_stereo = tkinter.BooleanVar(self, recording_settings.get_is_stereo())

        # window
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.main_frame = customtkinter.CTkFrame(self, width=480, corner_radius=0)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_columnconfigure((1, 3), weight=1)
        self.main_frame.grid_rowconfigure((0, 1), weight=1)

        self.format_label = customtkinter.CTkLabel(
            self.main_frame,
            text="フォーマット:",
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
        )
        self.format_label.grid(row=0, column=0, padx=16, pady=10)
        self.format_option = customtkinter.CTkOptionMenu(
            self.main_frame,
            values=self.recording_settings.get_format_list(),
            variable=self.var_format,
            command=self.change_format_option_event,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.format_option.grid(row=0, column=1, padx=16, pady=10)
        self.subtype_label = customtkinter.CTkLabel(
            self.main_frame,
            text="詳細(ビット深度など):",
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
        )
        self.subtype_label.grid(row=0, column=2, padx=16, pady=10)
        self.subtype_option = customtkinter.CTkOptionMenu(
            self.main_frame,
            values=self.recording_settings.get_subtype_list(),
            variable=self.var_subtype,
            command=self.change_subtype_option_event,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.subtype_option.grid(row=0, column=3, padx=16, pady=10)

        self.stereo_checkbox = customtkinter.CTkCheckBox(
            self.main_frame,
            text="ステレオ録音",
            variable=self.var_is_stereo,
            command=self.change_stereo_event,
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
        )
        self.stereo_checkbox.grid(row=1, column=0, padx=16, pady=10)

        # self.main_frame.focus_set()

    def change_format_option_event(self, new_format: str):
        self.recording_settings.set_format(new_format)

        self.subtype_option.configure(
            values=self.recording_settings.get_subtype_list(),
        )
        self.var_subtype.set(self.recording_settings.get_subtype())

    def change_subtype_option_event(self, new_subtype: str):
        self.recording_settings.set_subtype(new_subtype)

    def change_stereo_event(self):
        self.recording_settings.set_is_stereo(self.var_is_stereo.get())


class App(customtkinter.CTk):
    def __init__(self, fg_color: str | Tuple[str, str] | None = None, **kwargs):
        super().__init__(fg_color, **kwargs)

        self.title("CoReco")
        self.geometry("1140x720")

        # modules
        self.project_manager = project_manager.ProjectManager()
        self.recording_settings = RecordingSettings()

        self.player = player.Player()
        self.recorder = recorder.Recorder()

        self.player_thread = None
        self.recorder_thread = None

        self.player_stream = None
        self.recorder_stream = None

        self.player_queue = queue.Queue()
        self.recorder_queue = queue.Queue()

        self.recorder.set_default_samplerate(48000)

        self.devices = self.player.get_devices_dict()
        self.input_devices = self.devices["inputs"]
        self.output_devices = self.devices["outputs"]
        self.input_devices_dict = {
            f'{api}:{index}: {v["name"]} ({v["max_input_channels"]}ch)': v
            for api, indice in self.input_devices.items()
            for index, v in indice.items()
        }
        self.output_devices_dict = {
            f'{api}:{index}: {v["name"]} ({v["max_output_channels"]}ch)': v
            for api, indice in self.output_devices.items()
            for index, v in indice.items()
        }
        self.input_devices_index_list = {
            i: v for indice in self.input_devices.values() for i, v in indice.items()
        }
        self.input_devices_name_list = list(self.input_devices_dict.keys())
        self.output_devices_name_list = list(self.output_devices_dict.keys())

        self.input_device_samplerate = self.input_devices_index_list[
            self.player.get_default_device()[0]
        ]["default_samplerate"]

        # variables
        self.displaying_index = 0
        self.displaying_text_data = {}
        self.displaying_recording_data = None
        self.displaying_takes = []
        self.displaying_take_index = 0
        self.displaying_take_channels = []
        self.displaying_take_channel_index = 0
        self.displaying_take_file_samplerate = 0

        self.key_shift_pressed = False
        self.key_ctrl_pressed = False

        self.rec_fragments_data = {}

        self.rec_start_status_task = None

        self.rec_stream_settings_changed = True
        self.rec_device_channels = 1
        self.rec_is_recording = False

        self.rec_stream_previously_recording = False

        self.play_stream_settings_changed = True
        self.play_is_playing = False

        self.play_stream_channels = 1
        self.play_stream_samplerate = 48000

        # tkinter variables
        self.var_project_name = tkinter.StringVar(self, "<プロジェクト未ロード>")
        self.var_blank_start = tkinter.StringVar(self, 0.5)
        self.var_blank_end = tkinter.StringVar(self, 0.35)
        self.var_samplerate_label = tkinter.StringVar(
            self, f"サンプルレート: {self.input_device_samplerate}"
        )
        self.var_text_label = tkinter.StringVar(self, "----:\nここにテキストが表示されます")
        self.var_sub_label = tkinter.StringVar(self, "ここにてきすとがひょうじされます")
        self.var_input_channles_label = tkinter.StringVar(self, "入力チャンネル数: 0")
        self.var_input_channels = tkinter.IntVar(self, 1)
        self.var_status = tkinter.StringVar(self, "ここに現在のステータスが表示されます")
        self.var_selected_take_label = tkinter.StringVar(self, "テイク: --/--")
        self.var_selected_take_fileinfo_label = tkinter.StringVar(self, "SR: -----Hz")
        self.var_use_take = tkinter.StringVar(self, "1")
        self.var_take_blank_start = tkinter.StringVar(self, 0.5)
        self.var_take_blank_end = tkinter.StringVar(self, 0.35)
        self.var_is_verified = tkinter.BooleanVar(self, False)
        self.var_is_need_retake = tkinter.BooleanVar(self, False)
        self.var_is_recording = tkinter.BooleanVar(self, False)
        self.var_is_playing = tkinter.BooleanVar(self, False)

        # callbacks
        validate_digit = self.register(self.validate_digit_callback)

        self.grid_columnconfigure((1, 2, 3), weight=1)
        self.grid_columnconfigure(0, weight=0)
        # self.grid_columnconfigure((2, 3), weight=0)
        self.grid_rowconfigure((0, 1, 2, 3), weight=1)

        # sidebar
        self.sidebar_frame = customtkinter.CTkFrame(self, width=120, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure((0, 17), weight=0)
        self.sidebar_frame.grid_rowconfigure(16, weight=1)
        self.logo_label = customtkinter.CTkLabel(
            self.sidebar_frame,
            text="CoReco",
            font=customtkinter.CTkFont("Noto Sans JP", size=20, weight="bold"),
        )
        self.logo_label.grid(row=0, column=0, columnspan=4, padx=16, pady=(16, 10))
        self.sidebar_projectname_entry = customtkinter.CTkEntry(
            self.sidebar_frame,
            placeholder_text="プロジェクト名を入力",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.sidebar_projectname_entry.grid(row=1, column=0, columnspan=4, padx=16, pady=10)
        self.sidebar_projectname_label = customtkinter.CTkLabel(
            self.sidebar_frame,
            textvariable=self.var_project_name,
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
        )
        self.sidebar_projectname_label.grid(row=2, column=0, columnspan=4, padx=16, pady=10)
        self.sidebar_project_load_button = customtkinter.CTkButton(
            self.sidebar_frame,
            text="プロジェクトを作成/読込",
            command=self.load_or_make_project,
            font=customtkinter.CTkFont("Noto Sans JP", size=12, weight="bold"),
        )
        self.sidebar_project_load_button.grid(row=3, column=0, columnspan=2, padx=16, pady=10)
        self.sidebar_text_load_button = customtkinter.CTkButton(
            self.sidebar_frame,
            text="テキストの読み込み",
            command=self.load_text_file,
            font=customtkinter.CTkFont("Noto Sans JP", size=12, weight="bold"),
        )
        self.sidebar_text_load_button.grid(row=3, column=2, columnspan=2, padx=16, pady=10)
        self.sidebar_recording_settings_button = customtkinter.CTkButton(
            self.sidebar_frame,
            text="録音フォーマット設定",
            command=self.open_recording_settings_window,
            font=customtkinter.CTkFont("Noto Sans JP", size=12, weight="bold"),
        )
        self.sidebar_recording_settings_button.grid(row=4, column=0, columnspan=2, padx=16, pady=10)
        self.sidebar_rendering_button = customtkinter.CTkButton(
            self.sidebar_frame,
            text="音声の書き出し",
            command=self.open_rendering_window,
            font=customtkinter.CTkFont("Noto Sans JP", size=12, weight="bold"),
        )
        self.sidebar_rendering_button.grid(row=4, column=2, columnspan=2, padx=16, pady=10)

        self.output_device_label = customtkinter.CTkLabel(
            self.sidebar_frame,
            text="出力デバイス",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
            anchor="s",
        )
        self.output_device_label.grid(row=6, column=0, columnspan=4, padx=16, pady=(10, 2))
        self.output_device_optionmenu = customtkinter.CTkOptionMenu(
            self.sidebar_frame,
            values=self.output_devices_name_list,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
            command=self.change_output_device_event,
            dynamic_resizing=False,
        )
        self.output_device_optionmenu.grid(
            row=7,
            column=0,
            columnspan=4,
            padx=16,
            pady=10,
            sticky="ew",
        )
        self.input_device_label = customtkinter.CTkLabel(
            self.sidebar_frame,
            text="入力デバイス",
            anchor="s",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.input_device_label.grid(
            row=8,
            column=0,
            columnspan=4,
            padx=16,
            pady=(10, 2),
        )
        self.input_device_optionmenu = customtkinter.CTkOptionMenu(
            self.sidebar_frame,
            values=self.input_devices_name_list,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
            command=self.change_input_device_event,
            dynamic_resizing=False,
        )
        self.input_device_optionmenu.grid(
            row=9,
            column=0,
            columnspan=4,
            padx=16,
            pady=10,
            sticky="ew",
        )
        self.input_channels_label = customtkinter.CTkLabel(
            self.sidebar_frame,
            textvariable=self.var_input_channles_label,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
            anchor="s",
        )
        self.input_channels_label.grid(row=10, column=0, columnspan=4, padx=16, pady=(10, 2))
        self.input_device_channels = customtkinter.CTkSlider(
            self.sidebar_frame,
            from_=1,
            to=2,
            number_of_steps=2 - 1,
            variable=self.var_input_channels,
            command=self.change_input_channels_event,
        )
        self.input_device_channels.grid(
            row=11,
            column=0,
            columnspan=4,
            padx=16,
            pady=10,
            sticky="ew",
        )

        self.input_device_samplerate_label = customtkinter.CTkLabel(
            self.sidebar_frame,
            textvariable=self.var_samplerate_label,
            anchor="s",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.input_device_samplerate_label.grid(row=12, column=0, columnspan=4, padx=16, pady=10)

        self.blank_time_label = customtkinter.CTkLabel(
            self.sidebar_frame,
            text="ブランク時間(秒)",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
            anchor="s",
        )
        self.blank_time_label.grid(row=13, column=0, columnspan=4, padx=16, pady=(10, 2))
        self.blank_time_start_label = customtkinter.CTkLabel(
            self.sidebar_frame,
            text="開始:",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
            anchor="e",
            justify="right",
        )
        self.blank_time_start_label.grid(row=14, column=0, padx=(16, 2), pady=(10, 2))
        self.blank_time_start = customtkinter.CTkEntry(
            self.sidebar_frame,
            # textvariable=self.var_blank_start,
            validate="all",
            validatecommand=(validate_digit, "%P"),
            justify="right",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.blank_time_start.grid(row=14, column=1, padx=(2, 16), pady=(10, 2))
        self.blank_time_end_label = customtkinter.CTkLabel(
            self.sidebar_frame,
            text="終了:",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
            anchor="e",
            justify="right",
        )
        self.blank_time_end_label.grid(row=14, column=2, padx=(16, 2), pady=(10, 2))
        self.blank_time_end = customtkinter.CTkEntry(
            self.sidebar_frame,
            # textvariable=self.var_blank_end,
            validate="all",
            validatecommand=(validate_digit, "%P"),
            justify="right",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.blank_time_end.grid(row=14, column=3, padx=(2, 16), pady=(10, 2))

        self.appearance_mode_optionmenu = customtkinter.CTkOptionMenu(
            self.sidebar_frame,
            values=["System", "Light", "Dark"],
            command=self.change_appearance_mode_event,
        )
        self.appearance_mode_optionmenu.grid(row=17, column=0, columnspan=2, padx=16, pady=10)
        self.scaling_optionmenu = customtkinter.CTkOptionMenu(
            self.sidebar_frame,
            values=["50%", "75%", "100%", "125%", "150%"],
            command=self.change_scaling_event,
        )
        self.scaling_optionmenu.grid(row=17, column=2, columnspan=2, padx=16, pady=10)

        # self.appearance_mode_optionmenu = customtkinter.CTkOptionMenu(
        #     self.sidebar_frame,
        #     values=["System", "Light", "Dark"],
        #     command=self.change_appearance_mode_event,
        # )
        # self.appearance_mode_optionmenu.grid(row=15, column=0, padx=16, pady=10)
        # self.scaling_optionmenu = customtkinter.CTkOptionMenu(
        #     self.sidebar_frame,
        #     values=["50%", "75%", "100%", "125%", "150%"],
        #     command=self.change_scaling_event,
        # )
        # self.scaling_optionmenu.grid(row=16, column=0, padx=16, pady=10)

        # main
        self.main_frame = customtkinter.CTkFrame(self, width=360, corner_radius=0)
        self.main_frame.grid(row=0, column=1, rowspan=4, columnspan=3, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        # self.main_frame.grid_columnconfigure((2, 3), weight=0)
        # self.main_frame.grid_rowconfigure((0, 1), weight=1)
        self.main_frame.grid_rowconfigure((0, 1), weight=0)
        self.main_frame.grid_rowconfigure(2, weight=1)
        self.main_frame.grid_rowconfigure(3, weight=0)
        # self.main_frame.grid_rowconfigure(3, weight=1)
        # self.main_frame.grid_rowconfigure(3, weight=1)
        # read texts
        self.text_label = customtkinter.CTkLabel(
            self.main_frame,
            width=360,
            textvariable=self.var_text_label,
            font=customtkinter.CTkFont("Noto Sans JP", size=24, weight="bold"),
        )
        self.text_label.grid(row=0, column=0, padx=16, pady=(12, 8), sticky="nsew")
        self.sub_label = customtkinter.CTkLabel(
            self.main_frame,
            width=360,
            textvariable=self.var_sub_label,
            font=customtkinter.CTkFont("Noto Sans JP", size=16),
        )
        self.sub_label.grid(row=1, column=0, padx=16, pady=(8, 12), sticky="nsew")

        # info
        self.info_frame = customtkinter.CTkFrame(self.main_frame, corner_radius=0)
        self.info_frame.grid(row=2, column=0, sticky="nsew")
        self.info_frame.grid_columnconfigure((0, 1), weight=1)
        # self.info_frame.grid_columnconfigure(1, weight=1)
        self.info_frame.grid_rowconfigure(0, weight=1)
        # memo
        self.memo_textbox = customtkinter.CTkTextbox(
            self.info_frame, font=customtkinter.CTkFont("Noto Sans JP", size=12)
        )
        self.memo_textbox.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        # checks
        self.checks_frame = customtkinter.CTkFrame(self.info_frame)
        self.checks_frame.grid(row=0, column=1, sticky="nsew")
        self.checks_frame.grid_columnconfigure((1, 3), weight=1)
        self.checks_frame.grid_rowconfigure((0, 1, 2, 3, 5, 6), weight=0)
        self.checks_frame.grid_rowconfigure(4, weight=1)
        self.take_label = customtkinter.CTkLabel(
            self.checks_frame,
            textvariable=self.var_selected_take_label,
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
        )
        self.take_label.grid(row=0, column=0, pady=10, padx=16, sticky="n")
        self.take_fileinfo_label = customtkinter.CTkLabel(
            self.checks_frame,
            textvariable=self.var_selected_take_fileinfo_label,
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.take_fileinfo_label.grid(row=0, column=1, pady=10, padx=16, sticky="n")
        self.use_take_label = customtkinter.CTkLabel(
            self.checks_frame,
            text="使用するテイク:",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.use_take_label.grid(row=1, column=0, pady=10, padx=16, sticky="n")
        self.select_take = customtkinter.CTkOptionMenu(
            self.checks_frame,
            values=[""],
            variable=self.var_use_take,
            command=self.change_select_take_event,
        )
        self.select_take.grid(row=1, column=1, pady=10, padx=16, sticky="n")

        self.take_blank_time_label = customtkinter.CTkLabel(
            self.checks_frame,
            text="ブランク時間(秒)",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
            anchor="s",
        )
        self.take_blank_time_label.grid(row=2, column=0, columnspan=4, padx=16, pady=(10, 2))
        self.take_blank_time_start_label = customtkinter.CTkLabel(
            self.checks_frame,
            text="開始:",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
            anchor="e",
            justify="right",
        )
        self.take_blank_time_start_label.grid(row=3, column=0, padx=2, pady=(10, 2))
        self.take_blank_time_start = customtkinter.CTkEntry(
            self.checks_frame,
            # textvariable=self.var_take_blank_start,
            validate="all",
            validatecommand=(validate_digit, "%P"),
            justify="right",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.take_blank_time_start.grid(row=3, column=1, padx=(2, 16), pady=(10, 2))
        self.take_blank_time_end_label = customtkinter.CTkLabel(
            self.checks_frame,
            text="終了:",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
            anchor="e",
            justify="right",
        )
        self.take_blank_time_end_label.grid(row=3, column=2, padx=2, pady=(10, 2))
        self.take_blank_time_end = customtkinter.CTkEntry(
            self.checks_frame,
            # textvariable=self.var_take_blank_end,
            validate="all",
            validatecommand=(validate_digit, "%P"),
            justify="right",
            font=customtkinter.CTkFont("Noto Sans JP", size=12),
        )
        self.take_blank_time_end.grid(row=3, column=3, padx=(2, 16), pady=(10, 2))

        self.verified_checkbox = customtkinter.CTkCheckBox(
            self.checks_frame,
            text="確認済み",
            variable=self.var_is_verified,
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
            command=self.change_verified_event(),
        )
        self.verified_checkbox.grid(row=5, column=0, pady=10, padx=16, sticky="s")
        self.retake_checkbox = customtkinter.CTkCheckBox(
            self.checks_frame,
            text="要リテイク",
            variable=self.var_is_need_retake,
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
            command=self.change_need_retake_event(),
        )
        self.retake_checkbox.grid(row=6, column=0, pady=10, padx=16, sticky="s")

        # status
        self.status_label = customtkinter.CTkLabel(
            self.main_frame,
            textvariable=self.var_status,
            font=customtkinter.CTkFont("Noto Sans JP", size=14),
            anchor="w",
        )
        self.status_label.grid(row=3, column=0, sticky="sew")

        # sub windows
        self.rendering_window = None
        self.recording_settings_window = None

        # set defaults
        self.appearance_mode_optionmenu.set("System")
        self.scaling_optionmenu.set("100%")
        self.memo_textbox.insert("0.0", "ここにメモが書けます")
        self.blank_time_start.insert(0, "0.75")
        self.blank_time_end.insert(0, "0.1")

        self.text_data = None
        self.text_data_range = (0, 0)

        # inputs list
        # self.inputs_dict = {
        #     "project_name": self.sidebar_projectname_entry,
        #     "memo": self.memo_textbox,
        # }

        # set key event handler
        self.bind("<Key>", self.on_key)

        # set shift/ctrl-key event handler
        self.bind("<KeyPress-Shift_L>", self.on_shift_press)
        self.bind("<KeyPress-Shift_R>", self.on_shift_press)
        self.bind("<KeyRelease-Shift_L>", self.on_shift_release)
        self.bind("<KeyRelease-Shift_R>", self.on_shift_release)
        self.bind("<KeyPress-Control_L>", self.on_ctrl_press)
        self.bind("<KeyPress-Control_R>", self.on_ctrl_press)
        self.bind("<KeyRelease-Control_L>", self.on_ctrl_release)
        self.bind("<KeyRelease-Control_R>", self.on_ctrl_release)

        # set mouse event handler
        self.sidebar_frame.bind("<Button-1>", self.set_focus_to_root)
        self.main_frame.bind("<Button-1>", self.set_focus_to_root)
        self.text_label.bind("<Button-1>", self.set_focus_to_root)
        self.sub_label.bind("<Button-1>", self.set_focus_to_root)
        self.info_frame.bind("<Button-1>", self.set_focus_to_root)
        self.sidebar_project_load_button.bind("<Button-1>", self.set_focus_to_root)
        self.sidebar_projectname_entry.bind("<KeyPress-Return>", self.load_or_make_project)
        self.blank_time_start.bind("<KeyPress-Return>", self.set_focus_to_root)
        self.blank_time_end.bind("<KeyPress-Return>", self.set_focus_to_root)
        self.take_blank_time_start.bind("<KeyPress-Return>", self.set_focus_to_root)
        self.take_blank_time_end.bind("<KeyPress-Return>", self.set_focus_to_root)
        # self.checks_frame.bind("<Button-1>", self.on_window_click)
        # self.bind("<Button-1>", self.on_window_click)
        # self.main_frame.bind("<Button-1>", self.on_window_click)

        # set main_frame handler for wrap texts
        self.main_frame.bind("<Configure>", self.set_texts_wraplength)

        # self.input_device_channels.configure(
        #     to=self.input_devices_index_list[self.player.get_default_device()[0]][
        #         "max_input_channels"
        #     ],
        #     number_of_steps=max(
        #         1,
        #         self.input_devices_index_list[self.player.get_default_device()[0]][
        #             "max_input_channels"
        #         ]
        #         - 1,
        #     ),
        # )
        self.change_input_channels_event(1)

        self.protocol("WM_DELETE_WINDOW", self.on_close_event)

        self.resizable(True, True)

        self.set_texts_wraplength(None)

    def validate_digit_callback(self, P):
        try:
            float(P)
        except ValueError:
            return P == ""
        return True

    def set_texts_wraplength(self, evt):
        self.text_label.configure(wraplength=self.text_label.winfo_width())
        self.sub_label.configure(wraplength=self.sub_label.winfo_width())

    def change_appearance_mode_event(self, new_appearance_mode: str):
        customtkinter.set_appearance_mode(new_appearance_mode)

    def change_scaling_event(self, new_scaling: str):
        new_scaling_float = int(new_scaling.replace("%", "")) / 100
        customtkinter.set_widget_scaling(new_scaling_float)

    def change_select_take_event(self, new_take: str):
        # print(f"select take: {self.var_use_take.get()}")
        if new_take.isdecimal():
            self.project_manager.set_main_take(self.displaying_index, int(new_take) - 1)

    def change_verified_event(self):
        # print(f"verified: {self.var_is_verified.get()}")
        pass

    def change_need_retake_event(self):
        # print(f"need_retake: {self.var_is_need_retake.get()}")
        pass

    def change_input_device_event(self, new_selected_device: str):
        self.input_device_channels.configure(
            to=self.input_devices_dict[new_selected_device]["max_input_channels"],
            number_of_steps=self.input_devices_dict[new_selected_device]["max_input_channels"] - 1,
        )
        self.change_input_channels_event(self.input_device_channels.get())
        self.input_device_samplerate = self.input_devices_dict[new_selected_device][
            "default_samplerate"
        ]
        self.var_samplerate_label.set(f"サンプルレート: {self.input_device_samplerate:.0f}")
        self.rec_stream_settings_changed = True

    def change_output_device_event(self, new_selected_device: str):
        self.play_stream_settings_changed = True

    def change_input_channels_event(self, new_selected_value: float):
        self.var_input_channles_label.set(f"入力チャンネル数: {int(new_selected_value)}")

    def on_close_event(self):
        if self.rec_is_recording:
            self.stop_recording()
        if self.var_is_playing.get():
            self.stop_playing()
        self.save_recording_data()
        self.destroy()

    def set_status(self, info: str):
        self.var_status.set(info)

    def load_or_make_project(self, *args):
        project_name = self.sidebar_projectname_entry.get()
        if project_name != "":
            loaded_project_name = self.project_manager.open_or_create_project(project_name)
            if loaded_project_name is None:
                print("error: cannot open or create project, invalid project name = path name?")
                self.set_status(f"プロジェクトの作成に失敗しました。名前に特殊文字などパスに使えない文字がないか確認してください。")
                return
            self.var_project_name.set(loaded_project_name)
            self.set_status(f"プロジェクトを読み込みました: {loaded_project_name}")
            self.reload_project()
        self.set_focus_to_root(args)

    def set_take_channel_index(self, index: int):
        # TODO: change play target data
        self.var_selected_take_label.set(
            f"テイク: {self.displaying_take_index+1}/{len(self.displaying_recording_data['takes'])} ch:{index + 1}/{len(self.displaying_take_channels[self.displaying_take_index])}"
        )
        if self.displaying_take_channel_index >= len(
            self.displaying_take_channels[self.displaying_take_index]
        ):
            self.displaying_take_channel_index = (
                len(self.displaying_take_channels[self.displaying_take_index]) - 1
            )
        self.displaying_take_channel_index = index

    def set_take_index(self, index: int):
        if len(self.displaying_recording_data["takes"]) <= index:
            self.var_selected_take_label.set(f"テイク: --/--")
            return
        self.displaying_take_index = index
        self.displaying_take_channels = [
            list(k["record"].keys()) for k in self.displaying_recording_data["takes"]
        ]
        self.var_selected_take_label.set(
            f"テイク: {index+1}/{len(self.displaying_recording_data['takes'])} ch:{self.displaying_take_channel_index + 1}/{len(self.displaying_take_channels[self.displaying_take_index])}"
        )
        if self.displaying_take_channel_index >= len(
            self.displaying_take_channels[self.displaying_take_index]
        ):
            self.set_take_channel_index(
                len(self.displaying_take_channels[self.displaying_take_index]) - 1
            )

    def set_use_take(self, index: int):
        # print(f"set_use_take: {index+1}")
        if self.project_manager is None or not self.project_manager.is_loaded():
            self.set_status(f"プロジェクトが読み込まれていません。")
            return
        self.var_use_take.set(f"{index+1}")

    def increment_take_channel_index(self, increment: int):
        if self.project_manager is None or not self.project_manager.is_loaded():
            self.set_status(f"プロジェクトが読み込まれていません。")
            return
        if (
            self.displaying_recording_data is None
            or "takes" not in self.displaying_recording_data
            or len(self.displaying_recording_data["takes"]) <= 0
        ):
            return
        if (
            len(self.displaying_take_channels[self.displaying_take_index])
            <= self.displaying_take_index
        ):
            return

        incremented_index = self.displaying_take_channel_index + increment

        if incremented_index >= len(self.displaying_take_channels[self.displaying_take_index]) - 1:
            incremented_index = len(self.displaying_take_channels[self.displaying_take_index]) - 1
        elif incremented_index < 0:
            incremented_index = 0

        # print(self.displaying_take_channels)

        self.set_take_channel_index(incremented_index)

    def increment_take_index(self, increment: int):
        if self.project_manager is None or not self.project_manager.is_loaded():
            self.set_status(f"プロジェクトが読み込まれていません。")
            return
        if len(self.displaying_takes) <= 0:
            return
        if (
            (self.displaying_recording_data is None)
            or ("takes" not in self.displaying_recording_data)
            or len(self.displaying_recording_data["takes"]) <= 0
        ):
            self.var_selected_take_label.set(f"テイク: --/--")
            return

        incremented_index = self.displaying_take_index + increment

        if incremented_index >= len(self.displaying_recording_data["takes"]):
            incremented_index = len(self.displaying_recording_data["takes"]) - 1
        elif incremented_index < 0:
            incremented_index = 0

        self.set_take_index(incremented_index)
        # self.set_text_data(incremented_index, recording["texts"])
        self.save_recording_data()

    def increment_to_next_need_retake_text(self, increment: int):
        if self.project_manager is None or not self.project_manager.is_loaded():
            self.set_status(f"プロジェクトが読み込まれていません。")
            return
        recording = self.project_manager.get_next_need_retake(self.displaying_index, increment)
        if recording == None:
            self.set_status(f"未録音です。")
            return
        if self.recorder_thread is not None and self.recorder_thread.is_alive():
            self.stop_recording()
            recording = self.project_manager.get_recording(recording["id"])
            self.displaying_recording_data = recording
            self.set_recording_data(recording["id"], recording)
            self.rec()
        else:
            self.save_recording_data()
            self.set_recording_data(recording["id"], recording)
        self.displaying_recording_data = recording

    def increment_text_index(self, increment: int):
        if self.project_manager is None or not self.project_manager.is_loaded():
            self.set_status(f"プロジェクトが読み込まれていません。")
            return
        incremented_index = self.displaying_index + increment
        # index_num = len(self.text_data.keys())
        max_loop = 32
        # print(self.text_data_range)
        for _ in range(max_loop):
            # if incremented_index in self.text_data.keys():
            #     break
            if incremented_index < self.text_data_range[0]:
                incremented_index = self.text_data_range[1]
            elif incremented_index > self.text_data_range[1]:
                incremented_index = self.text_data_range[0]

            recording = self.project_manager.get_recording(incremented_index)
            if not recording is None:
                break

            incremented_index += increment

        if recording is None:
            recording, incremented_index = self.project_manager.get_next_recording(
                incremented_index, increment
            )

            if recording is None:
                print("index search was gave up")
                self.set_status(f"次のテキストが見つかりませんでした。テキストを読み込んでください。")
                return

        if not "texts" in recording.keys():
            self.set_status(f"テキストが見つかりませんでした。")
            print("no text found")
            return

        if self.take_blank_time_start.get() == "":
            self.take_blank_time_start.insert(0, self.blank_time_start.get())
        if self.take_blank_time_end.get() == "":
            self.take_blank_time_end.insert(0, self.blank_time_end.get())

        self.project_manager.set_start_end_take(
            self.displaying_index,
            self.displaying_take_index,
            float(self.take_blank_time_start.get()),
            float(self.take_blank_time_end.get()),
        )

        # self.displaying_recording_data = recording

        if self.recorder_thread is not None and self.recorder_thread.is_alive():
            self.stop_recording()
            recording = self.project_manager.get_recording(incremented_index)
            self.displaying_recording_data = recording
            self.set_recording_data(incremented_index, recording)
            self.rec()
        else:
            self.displaying_recording_data = recording
            self.save_recording_data()
            self.set_recording_data(incremented_index, recording)
            self.increment_take_index(0)

        # self.displaying_recording_data = recording

        # self.set_text_data(incremented_index, recording["texts"])
        # self.set_recording_data(incremented_index, recording)

        # self.set_text_data_index(incremented_index)

    def reload_project(self, index: Optional[int] = None):
        if self.project_manager is None or not self.project_manager.is_loaded():
            return
        self.text_data_range = self.project_manager.get_index_min_max()
        if not any(self.text_data_range):
            return
        if index is None:
            index = self.text_data_range[0]
        self.displaying_recording_data = self.project_manager.get_recording(index)
        if (
            self.displaying_recording_data is not None
            and "texts" in self.displaying_recording_data.keys()
        ):
            self.set_recording_data(index, self.displaying_recording_data)
        else:
            index = self.text_data_range[0]
            self.displaying_recording_data = self.project_manager.get_recording(index)
            if (
                self.displaying_recording_data is not None
                and "texts" in self.displaying_recording_data.keys()
            ):
                self.set_recording_data(index, self.displaying_recording_data)
        self.increment_text_index(0)

    def rec_callback(self, indata, frames, time, status):
        if status:
            print(status, file=sys.stderr)

        if self.rec_is_recording:
            self.recorder_queue.put(indata.copy())
            self.rec_stream_previously_recording = True
        elif self.rec_stream_previously_recording:
            self.recorder_queue.put(None)
            self.rec_stream_previously_recording = False

    def open_rec_stream(
        self,
        device,
        channels: int,
        samplerate: int = 48000,
    ):
        if self.recorder_stream is not None:
            self.recorder.close_stream()
        self.recorder_stream = self.recorder.open_stream(
            device, samplerate, channels, self.rec_callback
        )
        if self.recorder_stream is None:
            self.set_status("エラー: 入力デバイスを開けませんでした。")
            return
        self.rec_device_channels = channels

    def rec_writer_thread(
        self,
        basepath: str,
        filename: str,
        ext: str,
        channels: int,
        individual_channels: int,
        samplerate: int,
        format: str,
        subtype: str,
        queue: queue.Queue,
        fragments_data: Optional[queue.Queue] = None,
        **kwargs,
    ):
        fragments = None
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
                mode="w",
                samplerate=samplerate,
                channels=individual_channels,
                format=format,
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
                    mode="w",
                    samplerate=samplerate,
                    channels=channels - residual_chan,
                    format=format,
                    subtype=subtype,
                )
            )
            channels_list.append((channels - residual_chan, channels))
        print("### recording... ###")
        while self.rec_is_recording:
            data = queue.get()
            if data is None:
                break
            for f, c in zip(sound_files, channels_list):
                f.write(data[:, c[0] : c[1]])

        for f in sound_files:
            f.flush()
            f.close()
        fragments = {f"{ch[0]+1}": name for ch, name in zip(channels_list, filenames)}

        print("### recorded ###")

        if not fragments_data is None:
            fragments_data.put(fragments)

    def start_recording(
        self,
        channels: int,
        basepath: str,
        filename: str,
        is_stereo: bool = False,
        ext: str = "wav",
        samplerate: int = 48000,
        format: str = "WAV",
        subtype: str = "FLOAT",
    ):
        # if not self.recorder_thread is None and self.recorder_thread.is_alive():
        #     self.recorder.stop()
        #     if self.recorder_thread.is_alive():
        #         self.recorder_thread.join(5.0)
        # if not self.player_thread is None and self.player_thread.is_alive():
        #     self.player.stop()
        #     self.player_thread = None

        # self.rec_fragments_data = queue.Queue()

        # self.recorder_thread = threading.Thread(
        #     target=self.recorder.rec,
        #     args=(
        #         basepath,
        #         filename,
        #         ext,
        #         device,
        #         samplerate,
        #         channels,
        #         subtype,
        #         True,
        #         2 if is_stereo else 1,
        #         self.rec_fragments_data,
        #         device_channels,
        #     ),
        # )
        # self.recorder_thread.start()
        # self.var_is_recording.set(True)

        if self.rec_is_recording:
            self.rec_is_recording = False

        if not self.recorder_thread is None:
            self.recorder_thread.join(10.0)

        if not self.rec_start_status_task is None:
            self.rec_start_status_task.cancel()

        self.rec_fragments_data = queue.Queue()

        self.rec_is_recording = True
        self.recorder_thread = threading.Thread(
            target=self.rec_writer_thread,
            kwargs=dict(
                basepath=basepath,
                filename=filename,
                ext=ext,
                channels=channels,
                individual_channels=2 if is_stereo else 1,
                samplerate=samplerate,
                format=format,
                subtype=subtype,
                queue=self.recorder_queue,
                fragments_data=self.rec_fragments_data,
            ),
        )
        self.recorder_thread.start()
        self.var_is_recording.set(True)

        def update_status():
            self.rec_start_status_task = None
            self.set_status(
                f"録音中: {self.displaying_index}: {'' if not 'text' in self.displaying_text_data else self.displaying_text_data['text']['0']}"
            )

        self.set_status(f"録音開始ブランク... ({self.blank_time_start.get()}秒)")
        self.after(
            int(float(self.blank_time_start.get()) * 1000),
            update_status,
        )

    def rec(self):
        if self.project_manager is None or not self.project_manager.is_loaded():
            self.set_status(f"録音はプロジェクトを開いた後に可能になります。")
            return
        if "type" not in self.displaying_text_data:
            self.set_status(f"非対応のテキストのようです。録音はできません。")
            return
        device = self.input_devices_dict[self.input_device_optionmenu.get()]["index"]
        device_channels = self.input_devices_dict[self.input_device_optionmenu.get()][
            "max_input_channels"
        ]
        device_samplerate = self.input_devices_dict[self.input_device_optionmenu.get()][
            "default_samplerate"
        ]
        channels = self.var_input_channels.get()
        filename = f'{self.displaying_text_data["type"]}_{self.displaying_index:04}'
        next_take = len(self.displaying_takes) + 1
        basepath = os.path.join(
            self.project_manager.get_recording_path(),
            self.displaying_text_data["type"],
            f"{self.displaying_index:04}",
            f"take{next_take}",
        )
        if self.recorder_stream is None or self.rec_stream_settings_changed:
            self.open_rec_stream(device, device_channels, int(device_samplerate))
            self.rec_stream_settings_changed = False
        self.start_recording(
            channels,
            basepath,
            filename,
            is_stereo=self.recording_settings.get_is_stereo(),
            ext=self.recording_settings.get_format(),
            samplerate=int(device_samplerate),
            format=self.recording_settings.get_format(),
            subtype=self.recording_settings.get_subtype(),
        )

    def stop_recording(self):
        if self.project_manager is None or not self.project_manager.is_loaded():
            return

        if self.rec_is_recording:
            self.rec_is_recording = False
        else:
            return

        if not self.recorder_thread is None and self.recorder_thread.is_alive():
            self.recorder_thread.join(5.0)
            self.recorder_thread = None

        # if not self.recorder_thread is None and self.recorder_thread.is_alive():
        #     # self.recorder.stop()
        #     if self.recorder_thread.is_alive():
        #         self.recorder_thread.join(5.0)
        #     self.recorder_thread = None

        self.var_is_recording.set(False)
        fragments = self.rec_fragments_data.get()
        self.save_recording_data(fragments)
        self.set_status(f"録音しました: {self.displaying_index}")
        self.increment_text_index(0)

    def load_text_file(self):
        file = filedialog.askopenfilename(
            filetypes=[("テキストファイル", ("*.txt", "*.yml", "*.yaml"))],
            initialdir=os.path.curdir,
        )
        if file == "":
            return
        self.text_data = loader.load_texts(file)
        if self.text_data is None or len(self.text_data.keys()) < 1:
            self.set_status(f"非対応のテキストファイルです。")
            return
        if self.project_manager is None:
            return

        self.project_manager.update_text_datas(self.text_data)
        self.reload_project()

        # text_data_keys = self.text_data.keys()
        # self.text_data_range = (min(text_data_keys), max(text_data_keys))
        # self.set_text_data_index(list(self.text_data.keys())[0])

    def open_rendering_window(self):
        if self.project_manager is None or not self.project_manager.is_loaded():
            self.set_status(f"プロジェクトが読み込まれていません。")
            return
        self.save_recording_data()
        if self.rendering_window is None or not self.rendering_window.winfo_exists():
            self.rendering_window = RenderingSoundsWindow(
                self, project_manager=self.project_manager
            )
        else:
            self.rendering_window.focus_set()
        self.rendering_window.after(
            100, self.rendering_window.lift
        )  # workaround for a bug: CustomTkinter #1486

    def open_recording_settings_window(self):
        if (
            self.recording_settings_window is None
            or not self.recording_settings_window.winfo_exists()
        ):
            self.recording_settings_window = RecordingSettingsWindow(
                self, recording_settings=self.recording_settings
            )
        else:
            self.recording_settings_window.focus_set()
        self.recording_settings_window.after(100, self.recording_settings_window.lift)

    def set_recording_data(self, index: int, recording_data: Dict[str, Dict[Any, Any]]):
        if not "texts" in recording_data:
            self.set_status(f"テキストが読み込まれていません。")
            return

        if "verified" in recording_data:
            self.var_is_verified.set(recording_data["verified"])
        else:
            self.var_is_verified.set(False)

        if "need_retake" in recording_data:
            self.var_is_need_retake.set(recording_data["need_retake"])
        else:
            self.var_is_need_retake.set(False)

        if "takes" in recording_data and len(recording_data["takes"]) > 0:
            self.displaying_takes = [f"{r + 1}" for r in range(len(recording_data["takes"]))]
            self.select_take.configure(values=self.displaying_takes)
            if "use_take" in recording_data:
                # self.set_take_index(recording_data["use_take"])
                self.set_take_index(recording_data["use_take"])
                self.set_use_take(recording_data["use_take"])
                # self.var_selected_take_label.set(
                #     f'テイク: {recording_data["use_take"] + 1}/{len(self.displaying_takes)} ch:{self.displaying_take_channel_index + 1}/{len(self.displaying_take_channels[self.displaying_take_index])}'
                # )
            else:
                # self.set_take_index(len(self.displaying_takes) - 1)
                self.set_take_index(len(self.displaying_takes) - 1)
                self.set_use_take(len(self.displaying_takes) - 1)
                # self.var_selected_take_label.set(
                #     f"テイク: {len(self.displaying_takes)}/{len(self.displaying_takes)} ch:{self.displaying_take_channel_index + 1}/{len(self.displaying_take_channels[self.displaying_take_index])}"
                # )
            using_take = recording_data["takes"][recording_data["use_take"]]
            self.take_blank_time_start.delete(0, "end")
            if "start" in using_take:
                self.take_blank_time_start.insert(0, f"{using_take['start']}")
            else:
                self.take_blank_time_start.insert(0, self.blank_time_start.get())
            self.take_blank_time_end.delete(0, "end")
            if "stop_from_end" in using_take:
                self.take_blank_time_end.insert(0, f"{using_take['stop_from_end']}")
            else:
                self.take_blank_time_end.insert(0, self.blank_time_end.get())
            if "samplerate" in using_take:
                self.var_selected_take_fileinfo_label.set(f"SR: {using_take['samplerate']}Hz")
                self.displaying_take_file_samplerate = using_take["samplerate"]
            else:
                if "record" in using_take and isinstance(using_take["record"], dict):
                    first_ch_filename = using_take["record"][list(using_take["record"].keys())[0]]
                    if os.path.exists(first_ch_filename):
                        with sf.SoundFile(first_ch_filename) as f:
                            self.var_selected_take_fileinfo_label.set(f"SR: {f.samplerate}Hz")
                            self.displaying_take_file_samplerate = f.samplerate
                else:
                    self.var_selected_take_fileinfo_label.set(f"SR: -----Hz")
                    self.displaying_take_file_samplerate = 0
            # else:
            #     self.displaying_takes = []
        else:
            self.select_take.configure(values=[""])
            self.var_selected_take_label.set(f"テイク: --/--")

        # TODO: load and be playable recorded audio

        self.memo_textbox.delete("0.0", "end")
        if "memo" in recording_data:
            self.memo_textbox.insert("0.0", recording_data["memo"])

        self.set_text_data(index, recording_data["texts"])

    def save_recording_data(
        self, audio_path: Optional[Union[str, List[str], Dict[str, str]]] = None
    ):
        if self.project_manager is None or not self.project_manager.is_loaded():
            return

        self.project_manager.update_recording(
            self.displaying_index,
            audio_path,  # TODO: set recorded audio path
            {
                "verified": self.var_is_verified.get(),
                "need_retake": self.var_is_need_retake.get(),
                "memo": self.memo_textbox.get("0.0", "end").strip(),
            },
            self.displaying_text_data,
            int(self.input_device_samplerate),
            float(self.take_blank_time_start.get()),
            float(self.take_blank_time_end.get()),
        )

    def set_text_data(self, index: int, text_data: Dict[str, Dict[str, str]]):
        if "text" not in text_data:
            self.set_status(f"テキストデータが読み込まれていません。")
            return
        self.var_text_label.set(f"{index}:\n{text_data['text']['0']}")
        if "kana" in text_data.keys():
            self.var_sub_label.set(f"{text_data['kana']['0']}")
        else:
            self.var_sub_label.set("")
        self.displaying_index = index
        self.displaying_text_data = text_data

    def set_text_data_index(self, index: int):
        if index in self.text_data.keys():
            self.set_text_data(index, self.text_data[index])

    def play_callback(self, outdata, frames, time, status):
        if status:
            print(status, file=sys.stderr)

        if status.output_underflow:
            # output buffer underflow, suggest: increase blocksize
            # print(status, file=sys.stderr)
            raise sd.CallbackAbort
        assert not status
        try:
            data = self.player_queue.get_nowait()
        except queue.Empty:
            # buffer is empty, suggest: increase buffersize
            # raise sd.CallbackAbort
            # ---
            # no data, fill zeros
            outdata[:] = b"\x00" * (len(outdata))
            return
        if len(data) < len(outdata):
            outdata[: len(data)] = data
            outdata[len(data) :] = b"\x00" * (len(outdata) - len(data))
            # raise sd.CallbackStop
        elif len(data) > len(outdata):
            outdata[:] = data[(len(data) - len(outdata)) :]
        else:
            outdata[:] = data
            # if not self.play_is_playing:
            #     raise sd.CallbackStop

        # if self.play_is_playing:
        #     self.recorder_queue.put(indata.copy())
        #     self.rec_stream_previously_recording = True
        # elif self.rec_stream_previously_recording:
        #     self.recorder_queue.put(None)
        #     self.rec_stream_previously_recording = False

    def open_play_stream(
        self,
        device,
        channels: int,
        blocksize: Optional[int] = None,
        samplerate: int = 48000,
    ):
        if self.player_stream is not None:
            self.player.close_stream()
        self.player_stream = self.player.open_stream(
            device, samplerate, channels, blocksize, self.play_callback
        )
        if self.player_stream is None:
            self.set_status("エラー: 出力デバイスを開けませんでした。")
            return

    def play_reader_thread(
        self,
        filename: str,
        queue: queue.Queue,
        end_callback: Optional[Callable] = None,
        continue_pos: int = 0,
        stop_pos_from_end: int = -1,
        **kwargs,
    ):
        while not queue.empty():
            queue.get_nowait()
        with sf.SoundFile(filename) as f:
            playback_pos = continue_pos
            f.seek(continue_pos)
            buffersize, blocksize = self.player.get_buffer_settings()
            for _ in range(buffersize):
                data = f.buffer_read(blocksize, dtype="float32")
                if not data:
                    break
                queue.put_nowait(data)
            print("### playing... ###")
            timeout = blocksize * buffersize / f.samplerate
            while len(data):
                if not self.play_is_playing:
                    while not queue.empty():
                        queue.get()
                    break
                read_size = blocksize
                if (
                    stop_pos_from_end >= 0
                    and f.frames - playback_pos - read_size < stop_pos_from_end
                ):
                    read_size = f.frames - playback_pos - stop_pos_from_end
                data = f.buffer_read(read_size, dtype="float32")
                try:
                    queue.put(data, timeout=timeout)
                except Exception as e:
                    print(f"maybe player queue is full: {e}")
                    break
                playback_pos = f.tell()
                if read_size < blocksize:
                    break

            print("### stop playing ###")

        if not end_callback is None:
            end_callback()

    def start_playing(self, filename: str):
        # if not self.recorder_thread is None and self.recorder_thread.is_alive():
        #     self.recorder.stop()
        #     if self.recorder_thread.is_alive():
        #         self.recorder_thread.join(5.0)
        #     self.recorder_thread = None
        if self.rec_is_recording:
            self.stop_recording()

        if self.play_is_playing:
            self.play_is_playing = False

        if self.player_thread is not None and self.player_thread.is_alive():
            self.player_thread.join(10.0)

        # self.rec_fragments_data = queue.Queue()

        def playing_end():
            self.set_status("再生終了")
            self.var_is_playing.set(False)
            self.player_thread = None

        start_samples = max(
            0,
            0
            if self.displaying_take_file_samplerate <= 0
            else int(
                float(self.take_blank_time_start.get()) * self.displaying_take_file_samplerate
            ),
        )
        end_samples = (
            -1
            if self.displaying_take_file_samplerate <= 0
            else int(float(self.take_blank_time_end.get()) * self.displaying_take_file_samplerate)
        )

        # self.player_thread = threading.Thread(
        #     target=self.player.play,
        #     args=(
        #         filename,
        #         device,
        #         playing_end,
        #         start_samples,
        #         end_samples,
        #     ),
        # )
        self.player_queue = queue.Queue(maxsize=self.player.get_buffer_settings()[0])
        self.play_is_playing = True
        self.player_thread = threading.Thread(
            target=self.play_reader_thread,
            args=(
                filename,
                self.player_queue,
                playing_end,
                start_samples,
                end_samples,
            ),
        )
        self.player_thread.start()
        self.var_is_playing.set(True)

    def play(self):
        if self.project_manager is None or not self.project_manager.is_loaded():
            self.set_status(f"プロジェクトが読み込まれていません。")
            return
        device = self.output_devices_dict[self.output_device_optionmenu.get()]["index"]
        take_channel_index = f"{self.displaying_take_channel_index + 1}"
        # print(
        #     self.displaying_recording_data["takes"][self.displaying_take_index][
        #         "record"
        #     ][take_channel_index]
        # )
        # print(
        #     f"{self.displaying_recording_data['takes']} len: {len(self.displaying_recording_data['takes'])}"
        # )
        if (
            self.displaying_recording_data is None
            or len(self.displaying_recording_data["takes"]) <= self.displaying_take_index
            or "record" not in self.displaying_recording_data["takes"][self.displaying_take_index]
            or take_channel_index
            not in self.displaying_recording_data["takes"][self.displaying_take_index]["record"]
        ):
            self.set_status(f"未録音です。")
            return

        filename = os.path.join(
            os.curdir,
            self.displaying_recording_data["takes"][self.displaying_take_index]["record"][
                take_channel_index
            ],
        )

        if not os.path.exists(filename):
            self.set_status(f"ファイルが見つかりませんでした。: {filename}")
            return

        with sf.SoundFile(filename) as f:
            file_channels = f.channels
            file_samplerate = f.samplerate

        if (
            self.player_stream is None
            or self.play_stream_settings_changed
            or self.play_stream_channels != file_channels
            or self.play_stream_samplerate != file_samplerate
        ):
            self.open_play_stream(device, file_channels, None, int(file_samplerate))
            self.play_stream_channels = file_channels
            self.play_stream_samplerate = file_samplerate
            self.play_stream_settings_changed = False

        # self.start_playing(filename, device)
        self.start_playing(filename)
        self.set_status(
            f"再生中: {self.displaying_index} take{self.displaying_take_index + 1}, ch{take_channel_index}"
        )

    def stop_playing(self):
        if self.project_manager is None or not self.project_manager.is_loaded():
            self.set_status(f"プロジェクトが読み込まれていません。")
            return
        # if not self.player_thread is None and self.player_thread.is_alive():
        #     self.player.stop()
        #     self.player_thread = None
        if self.play_is_playing:
            self.play_is_playing = False
        self.var_is_playing.set(False)
        # self.var_status.set("再生停止")

    # def get_any_input_focused(self, evt):
    #     print(
    #         evt.widget,
    #         self.memo_textbox.winfo_id(),
    #         self.sidebar_projectname_entry.winfo_id(),
    #     )
    #     return any([evt.widget == i for i in self.inputs_dict])

    def set_focus_to_root(self, evt):
        self.focus_set()

    def on_shift_press(self, evt):
        self.key_shift_pressed = True

    def on_shift_release(self, evt):
        self.key_shift_pressed = False

    def on_ctrl_press(self, evt):
        self.key_ctrl_pressed = True

    def on_ctrl_release(self, evt):
        self.key_ctrl_pressed = False

    def on_key(self, evt):
        # print(evt.keysym, evt.keycode)
        # print(f"self: {self.focus_get()}")
        # print(f"memo: {self.memo_textbox.focus_get()}")
        if evt.widget == self:
            if evt.keysym == "Right" or evt.keysym == "d" or evt.keysym == "D":
                if self.key_shift_pressed:
                    self.increment_to_next_need_retake_text(1)
                else:
                    self.increment_text_index(1)
            elif evt.keysym == "Left" or evt.keysym == "a" or evt.keysym == "A":
                if self.key_shift_pressed:
                    self.increment_to_next_need_retake_text(-1)
                else:
                    self.increment_text_index(-1)
            elif evt.keysym == "Up" or evt.keysym == "w" or evt.keysym == "W":
                if self.key_shift_pressed:
                    self.increment_take_channel_index(1)
                else:
                    self.increment_take_index(1)
            elif evt.keysym == "Down" or evt.keysym == "s" or evt.keysym == "S":
                if self.key_shift_pressed:
                    self.increment_take_channel_index(-1)
                else:
                    self.increment_take_index(-1)
            elif evt.keysym == "r":
                if self.key_ctrl_pressed:
                    if self.var_is_recording.get():
                        self.stop_recording()
                        self.increment_text_index(0)
                    else:
                        self.rec()
                elif self.var_is_recording.get():
                    self.stop_recording()
                    self.increment_text_index(0)
                    self.rec()
            elif evt.keysym == "space":
                if self.var_is_recording.get():
                    self.stop_recording()
                    self.increment_text_index(0)
                elif self.var_is_playing.get():
                    self.stop_playing()
                else:
                    self.play()


if __name__ == "__main__":
    customtkinter.set_default_color_theme("blue")

    app = App()
    # app.geometry("600x320")
    # app.title("CoReco")

    # def button_function():
    #     print("button pressed")

    # frame_head = customtkinter.CTkFrame(master=app)
    # frame_head.pack(pady=10, padx=30, fill="both", expand=True)

    # button = customtkinter.CTkButton(
    #     master=frame_head, text="CTkButton", command=button_function
    # )
    # button.place(relx=0.5, rely=0.5, anchor=tkinter.CENTER)

    app.mainloop()
