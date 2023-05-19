import os
import sys
import traceback
from typing import *

import yaml


def parse_basic5000(yml: Dict[str, Any]):
    parsed = {}
    try:
        for k in sorted(yml.keys()):
            corpus_type, number = k.split("_", 2)
            if number.isdecimal():
                datas: Dict[str, str] = yml[k]
                parsed_datas = {}
                for dk, dv in datas.items():
                    text_type, level = dk.split("_level", 2)
                    if not text_type in parsed_datas.keys():
                        parsed_datas[text_type] = {}
                    parsed_datas[text_type][level] = dv
                parsed_datas["type"] = corpus_type
                parsed_datas["name"] = k
                parsed[int(number)] = parsed_datas
    except Exception as e:
        raise e

    print(f"loaded {len(parsed.keys())} sentences as {corpus_type} style")
    return parsed


def load_basic5000_yaml(filename: str):
    with open(filename, "r", encoding="utf-8") as f:
        try:
            yml = yaml.safe_load(f)
            return parse_basic5000(yml)
        except Exception as e:
            print("trying skip first line as header")

        f.seek(0, os.SEEK_SET)
        next(f)
        try:
            yml = yaml.safe_load(f)
            return parse_basic5000(yml)
        except Exception as e:
            print(
                "exception occurred while loading basic5000 style corpus",
                file=sys.stderr,
            )
            raise e


def parse_itacorpus(file: Iterable):
    parsed = {}
    try:
        for l in file:
            corpus_type, number_texts = l.split("_", 2)
            number, texts = number_texts.split(":", 2)
            if number.isdecimal():
                texts: List[str] = texts.split(",")
                parsed_datas = {"text": {"0": texts[0].strip()}}
                if len(texts) > 1:
                    parsed_datas["kana"] = {"0": texts[1].strip()}
                parsed_datas["type"] = corpus_type
                parsed_datas["name"] = "_".join((corpus_type, number))
                parsed[int(number)] = parsed_datas
    except Exception as e:
        raise e

    print(f"loaded {len(parsed.keys())} sentences as {corpus_type} style")
    return parsed


def load_itacorpus_text(filename: str):
    with open(filename, "r", encoding="utf-8") as f:
        try:
            return parse_itacorpus(f)
        except Exception as e:
            print("trying skip first line as header")

        f.seek(0, os.SEEK_SET)
        next(f)
        try:
            return parse_itacorpus(f)
        except Exception as e:
            print(
                "exception occurred while loading ita-corpus style corpus",
                file=sys.stderr,
            )
            raise e


def parse_oremo_reclist(file: Iterable, name: str):
    parsed = {}
    try:
        text_type = os.path.splitext(os.path.basename(name))[0]
        text_index = 1
        for l in file:
            for phoneme in l.split(" "):
                if phoneme.strip() == "":
                    continue
                number = text_index

                parsed_datas = {"text": {"0": phoneme.strip()}}
                parsed_datas["type"] = text_type
                parsed_datas["name"] = number
                parsed[int(number)] = parsed_datas
                text_index += 1
    except Exception as e:
        raise e

    print(f"loaded {len(parsed.keys())} phonemes from {text_type}")
    return parsed


def load_oremo_reclist_text(filename: str):
    with open(filename, "r", encoding="shift_jis") as f:
        try:
            return parse_oremo_reclist(f, filename)
        except Exception as e:
            print("trying skip first line as header")

        f.seek(0, os.SEEK_SET)
        next(f)
        try:
            return parse_oremo_reclist(f, filename)
        except Exception as e:
            print(
                "exception occurred while loading OREMO style text",
                file=sys.stderr,
            )
            raise e


def parse_mycoeiroink_text(file: Iterable):
    parsed = {}
    try:
        corpus_types = []
        read_texts = []
        text_index = 1
        for l in file:
            stripped_line = l.strip()
            if stripped_line != "":
                read_texts.append(stripped_line)
                continue
            if len(read_texts) >= 4:
                name, text0, kana0, _ = read_texts[:4]
            else:
                raise ValueError

            corpus_type, _ = name.split("_", 2)

            parsed_datas = {
                "text": {"0": text0.strip()},
                "kana": {"0": kana0.strip()},
            }
            parsed_datas["type"] = corpus_type
            parsed_datas["name"] = name
            parsed[text_index] = parsed_datas

            if corpus_type not in corpus_types:
                corpus_types.append(corpus_type)
            read_texts = []
            text_index += 1
    except Exception as e:
        raise e

    print(f"loaded {len(parsed.keys())} sentences as {','.join(corpus_types)} style")
    return parsed


def load_mycoeiroink_text(filename: str):
    with open(filename, "r", encoding="utf-8") as f:
        try:
            return parse_mycoeiroink_text(f)
        except Exception as e:
            print("trying skip first line as header")

        f.seek(0, os.SEEK_SET)
        next(f)
        try:
            return parse_mycoeiroink_text(f)
        except Exception as e:
            print(
                "exception occurred while loading OREMO style text",
                file=sys.stderr,
            )
            raise e


def load_texts(filename: str):
    try:
        return load_basic5000_yaml(filename)
    except Exception as e:
        # print(
        #     "exception occurred while loading basic5000 style corpus",
        #     file=sys.stderr,
        # )
        pass

    try:
        return load_itacorpus_text(filename)
    except Exception as e:
        # print(
        #     "exception occurred while loading ITA-Corpus text",
        #     file=sys.stderr,
        # )
        # traceback.print_exc()
        pass

    try:
        return load_mycoeiroink_text(filename)
    except Exception as e:
        # print(
        #     "exception occurred while loading mycoeiroink-Corpus text",
        #     file=sys.stderr,
        # )
        # traceback.print_exc()
        pass

    try:
        return load_oremo_reclist_text(filename)
    except Exception as e:
        print(
            "exception occurred while loading text",
            file=sys.stderr,
        )
        traceback.print_exc()
        pass
    return None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # print(load_basic5000_yaml(sys.argv[1]))
        # print(load_itacorpus_text(sys.argv[1]))
        # load_itacorpus_yaml(sys.argv[1])
        load_texts(sys.argv[1])
