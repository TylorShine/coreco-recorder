import os
import sys
import time
from typing import Any, Dict, List, Optional, Union

from tinydb import Query, TinyDB


class ProjectManager:
    def __init__(self) -> None:
        self.coreco_db_name = "coreco.json"
        self.recorded_dirname = "recorded"

        self.main_table_name = "recordings"
        self.meta_table_name = "meta"

        self.current_project_name = ""
        self.current_project_path = ""
        self.current_project_db = None
        self.current_project_main_table = None

    def open_project(self, project_base_dir: str, name: str):
        project_dir = os.path.join(project_base_dir, name)
        db_file = os.path.join(project_dir, self.coreco_db_name)
        os.makedirs(project_dir, exist_ok=True)
        self.current_project_db = TinyDB(db_file)
        if self.current_project_db is None:
            return None
        self.current_project_main_table = self.current_project_db.table(self.main_table_name)

        self.current_project_name = name
        self.current_project_path = project_dir
        return name

    def open_or_create_project(self, name: str):
        project_base_dir = os.path.join(os.curdir, "projects")
        project_dir = os.path.join(project_base_dir, name)
        db_file = os.path.join(project_dir, self.coreco_db_name)
        if (
            os.path.exists(project_dir)
            and os.path.isdir(project_dir)
            and (os.path.exists(db_file) and os.path.isfile(db_file))
        ):
            return self.open_project(project_base_dir, name)
        else:
            return self.open_project(project_base_dir, name)

    def get_project_path(self):
        return self.current_project_path

    def get_recording_path(self):
        return os.path.join(self.current_project_path, self.recorded_dirname)

    def get_project_name(self):
        return self.current_project_name

    def is_loaded(self):
        return self.current_project_db is not None

    def get_index_min_max(self):
        if not self.is_loaded():
            return

        indice = [d["id"] for d in self.current_project_main_table.all()]
        # print(indice)
        if len(indice) <= 0:
            return 0, 0
        return min(indice), max(indice)

    def get_recording(self, index: Optional[int]):
        if not self.is_loaded():
            return

        if index is None:
            index, _ = self.get_index_min_max()

        Recording = Query()

        record = self.current_project_main_table.search(Recording.id == index)

        return None if len(record) <= 0 else record[0]

    def get_next_recording(self, now_index: Optional[int], direction: int = 1):
        if not self.is_loaded():
            return

        Recording = Query()

        if direction > 0:
            record = self.current_project_main_table.search(Recording.id > now_index)
        else:
            record = self.current_project_main_table.search(Recording.id < now_index)

        if not len(record) <= 0:
            record = sorted(record, key=lambda x: x["id"], reverse=direction < 0)[0]

        return (None, None if len(record) <= 0 else record, record["id"])

    def get_all_recordings(self, verified_only: bool = False):
        if not self.is_loaded():
            return

        Recording = Query()

        if verified_only:
            return self.current_project_main_table.search(
                (Recording.takes.exists()) & (Recording.verified == True)
            )
        return self.current_project_main_table.search(Recording.takes.exists())

    def get_next_need_retake(self, now_index: int, direction: int = 1):
        if not self.is_loaded():
            return

        Recording = Query()

        if direction > 0:
            record = self.current_project_main_table.search(
                (Recording.need_retake == True) & (Recording.id > now_index)
            )
        else:
            record = self.current_project_main_table.search(
                (Recording.need_retake == True) & (Recording.id < now_index)
            )

        return (
            None
            if len(record) <= 0
            else sorted(record, key=lambda x: x["id"], reverse=direction < 0)[0]
        )

    def delete_take(
        self,
        index: int,
        take_index: int,
    ):
        if self.current_project_db is None:
            return None

        Recording = Query()

        record = self.current_project_main_table.search(Recording.id == index)
        if len(record) <= 0 or "takes" not in record[0]:
            return None

        data = record[0]
        if len(data["takes"]) < take_index or take_index < 0:
            return None

        del data["takes"][take_index]

        self.current_project_main_table.update(data, Recording.id == index)

    def set_main_take(
        self,
        index: int,
        take_index: int,
    ):
        if self.current_project_db is None:
            return None

        Recording = Query()

        record = self.current_project_main_table.search(Recording.id == index)
        if len(record) <= 0 or "takes" not in record[0]:
            return None

        data = record[0]
        if len(data["takes"]) < take_index or take_index < 0:
            return None

        data["use_take"] = take_index

        self.current_project_main_table.update(data, Recording.id == index)

    def set_start_end_take(
        self,
        index: int,
        take_index: int,
        start_time: float,
        stop_from_end_time: float,
    ):
        if self.current_project_db is None:
            return None

        Recording = Query()

        record = self.current_project_main_table.search(Recording.id == index)
        if len(record) <= 0 or "takes" not in record[0]:
            return None

        data = record[0]
        if len(data["takes"]) <= take_index or take_index < 0:
            return None

        data["takes"][take_index]["start"] = start_time
        data["takes"][take_index]["stop_from_end"] = stop_from_end_time

        self.current_project_main_table.update(data, Recording.id == index)

    def update_recording(
        self,
        index: int,
        audio_path: Optional[Union[str, List[str], Dict[str, str]]],
        states: Optional[Dict[str, Any]],
        text_data: Optional[Dict[Any, Any]],
        samplerate: int = 48000,
        start_time: float = 0.0,
        stop_from_end_time: float = -1.0,
        timestamp: Optional[float] = None,
        save_as_take: bool = True,
        mark_as_main_take: bool = True,
    ):
        if self.current_project_db is None or not self.is_loaded():
            return None

        Recording = Query()

        record = self.current_project_main_table.search(Recording.id == index)
        if len(record) > 0:
            data = record[0]
        else:
            data = {"id": index}

        if not "takes" in data.keys():
            data["takes"] = []

        last_update = time.time()
        if timestamp is None:
            timestamp = last_update

        if not audio_path is None:
            audio_channels_path = {}
            if isinstance(audio_path, dict):
                audio_channels_path = {
                    "recorded": timestamp,
                    "record": audio_path,
                }
            else:
                if isinstance(audio_path, list):
                    audio_channels_path = {
                        "recorded": timestamp,
                        "record": {str(i + 1): v for i, v in enumerate(audio_path)},
                    }
                else:
                    audio_channels_path = {
                        "recorded": timestamp,
                        "record": {"1": audio_path},
                    }
            audio_channels_path.update(
                start=start_time,
                stop_from_end=stop_from_end_time,
                samplerate=samplerate,
            )
            if save_as_take:
                data["takes"].append(audio_channels_path)
            else:
                data["takes"] = [audio_channels_path]

            if len(data["takes"]) <= 1 or mark_as_main_take:
                data["use_take"] = len(data["takes"]) - 1

        if not states is None:
            data.update(**states)

        if not text_data is None:
            data["texts"] = text_data

        data["last_update"] = last_update

        self.current_project_main_table.upsert(data, Recording.id == index)

    def update_text_datas(self, text_datas: Dict[int, Dict[Any, Any]]):
        if self.current_project_db is None:
            return None

        for index, text_data in text_datas.items():
            self.update_recording(index, None, None, text_data)
