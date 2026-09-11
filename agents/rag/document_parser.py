"""
把"城市→区域→景点→字段"结构化的景点 txt 解析成「每景点一个 Document」。

源文件约定格式：
  区域标题：        0 缩进，以"："结尾（如 "澳门半岛："）
    景点名：        2 缩进，以"："结尾（如 "  大三巴牌坊及议事亭前地："）
      字段：值      4 缩进，如 "    描述：..."、"    预算：..."

解析后每个景点生成 1 个 Document：
  - page_content = "景点名（城市·区域）\n字段：值\n..."
  - metadata    = {source, city, region, attraction}
若单个景点内容超长（> max_chars），再按句细分为多个子分片，每段保留 header 上下文。
"""
import os
import re
from langchain_core.documents import Document

REGION_INDENT = 0
ATTR_MAX_INDENT = 4  # 景点标题缩进 < 4
FIELD_INDENT = 4


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _split_colon(text: str):
    for idx, ch in enumerate(text):
        if ch in "：:":
            return text[:idx].strip(), text[idx + 1:].strip()
    return None, None


def _city_from_path(path: str) -> str:
    name = os.path.basename(path)
    for suffix in ("旅游景点.txt", "旅游景点.pdf"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return os.path.splitext(name)[0]


def parse_attraction_txt(
    path: str,
    max_chars: int = 512,
    sub_size: int = 200,
) -> list[Document]:
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    city = _city_from_path(path)
    region = ""
    attraction = ""
    fields: list[tuple[str, str]] = []
    docs: list[Document] = []

    def flush():
        nonlocal attraction, fields
        if attraction and fields:
            header = f"{attraction}（{city}·{region}）"
            body = "\n".join(f"{k}：{v}" for k, v in fields)
            docs.extend(_to_docs(path, city, region, attraction, header, body, max_chars, sub_size))
        attraction = ""
        fields = []

    for raw in lines:
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        indent = _leading_spaces(line)
        stripped = line.strip()

        # 区域标题（0 缩进 + 以"："结尾）
        if indent == REGION_INDENT and stripped.endswith("："):
            flush()
            region = stripped[:-1].strip()
            continue
        # 景点标题（2 缩进 + 以"："结尾）
        if 0 < indent < ATTR_MAX_INDENT and stripped.endswith("："):
            flush()
            attraction = stripped[:-1].strip()
            continue
        # 字段行（>=4 缩进 + 含冒号）
        if indent >= FIELD_INDENT and ("：" in line or ":" in line):
            k, v = _split_colon(stripped)
            if k:
                fields.append((k, v))
            continue
        # 字段值续行（>=4 缩进但无冒号，追加到上一字段）
        if indent >= FIELD_INDENT and fields:
            fields[-1] = (fields[-1][0], fields[-1][1] + stripped)
            continue
        # 其它（标题说明、括号注释等）忽略

    flush()
    return docs


def _to_docs(path, city, region, attraction, header, body, max_chars, sub_size) -> list[Document]:
    meta = {"source": path, "city": city, "region": region, "attraction": attraction}
    content = f"{header}\n{body}"
    if len(content) <= max_chars:
        return [Document(page_content=content, metadata=meta)]

    # 超长：按句细分，每段保留 header 上下文
    chunks, buf = [], ""
    for seg in re.split(r"(?<=[。！？!?；;])", body):
        if not seg.strip():
            continue
        if buf and len(buf) + len(seg) > sub_size:
            chunks.append(f"{header}\n{buf}")
            buf = seg
        else:
            buf += seg
    if buf:
        chunks.append(f"{header}\n{buf}")
    return [Document(page_content=c, metadata=meta) for c in chunks]
