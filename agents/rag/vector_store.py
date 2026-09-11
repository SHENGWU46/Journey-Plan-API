from langchain_chroma import Chroma
from langchain_core.documents import Document
from agents.utils.config_handler import chroma_conf
from agents.model.factory import embed_model
from langchain_text_splitters import RecursiveCharacterTextSplitter
from agents.utils.path_tool import get_abs_path
from agents.utils.file_handler import pdf_loader, txt_loader, listdir_with_allowed_type, get_file_md5_hex
from agents.rag.document_parser import parse_attraction_txt
from agents.utils.logger_handler import logger
import os


class VectorStoreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name=chroma_conf["collection_name"],
            embedding_function=embed_model,
            persist_directory=get_abs_path(chroma_conf["persist_directory"]),
        )

        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_conf["chunk_size"],
            chunk_overlap=chroma_conf["chunk_overlap"],
            separators=chroma_conf["separators"],
            length_function=len,
        )

    def get_retriever(self, k: int | None = None, exclude: list[str] | None = None):
        """返回检索器；k 不传则使用配置默认值 chroma_conf["k"]。

        用于支持不同检索场景返回不同数量的分片（如首次宽泛检索返回更多、
        查具体景点返回更少）。

        exclude: 可选景点名列表；非空时通过 Chroma 元数据过滤排除这些景点，
        用于「换一批 / 继续推荐」场景，避免重复返回已展示过的景点。
        依赖分片 metadata 中的 attraction 字段（见 document_parser.py）。
        """
        k = k or chroma_conf["k"]
        search_kwargs = {"k": k}
        if exclude:
            # 物理排除已展示景点：检索层直接过滤掉这些 attraction 的分片，
            # 即使 LLM 想重复也拿不到对应材料，根治重复卡片。
            search_kwargs["filter"] = {"attraction": {"$nin": exclude}}
        return self.vector_store.as_retriever(search_kwargs=search_kwargs)

    def load_document(self):
        """
        从数据文件夹内读取数据文件，转为向量存入向量库
        要计算文件的MD5做去重
        :return: None
        """

        def check_md5_hex(md5_for_check: str):
            if not os.path.exists(get_abs_path(chroma_conf["md5_hex_store"])):
                # 创建文件
                open(get_abs_path(chroma_conf["md5_hex_store"]), "w", encoding="utf-8").close()
                return False            # md5 没处理过

            with open(get_abs_path(chroma_conf["md5_hex_store"]), "r", encoding="utf-8") as f:
                for line in f.readlines():
                    line = line.strip()
                    if line == md5_for_check:
                        return True     # md5 处理过

                return False            # md5 没处理过

        def save_md5_hex(md5_for_check: str):
            with open(get_abs_path(chroma_conf["md5_hex_store"]), "a", encoding="utf-8") as f:
                f.write(md5_for_check + "\n")

        def get_file_documents(read_path: str):
            if read_path.endswith("txt"):
                return txt_loader(read_path)

            if read_path.endswith("pdf"):
                return pdf_loader(read_path)

            return []

        allowed_files_path: list[str] = listdir_with_allowed_type(
            get_abs_path(chroma_conf["data_path"]),
            tuple(chroma_conf["allow_knowledge_file_type"]),
        )

        for path in allowed_files_path:
            # 获取文件的MD5
            md5_hex = get_file_md5_hex(path)

            if check_md5_hex(md5_hex):
                logger.info(f"[加载知识库]{path}内容已经存在知识库内，跳过")
                continue

            try:
                if path.endswith(".txt"):
                    # 结构化解析：每景点一片（超长再按句细分）
                    documents: list[Document] = parse_attraction_txt(
                        path,
                        max_chars=chroma_conf.get("max_attraction_chars", 512),
                        sub_size=chroma_conf.get("sub_chunk_size", 200),
                    )
                    if not documents:
                        logger.warning(f"[加载知识库]{path}未解析出景点，退回整文件切分")
                        documents = get_file_documents(path)
                        documents = self.spliter.split_documents(documents)
                else:
                    documents = get_file_documents(path)
                    documents = self.spliter.split_documents(documents)

                if not documents:
                    logger.warning(f"[加载知识库]{path}内没有有效文本内容，跳过")
                    continue

                split_document: list[Document] = documents

                if not split_document:
                    logger.warning(f"[加载知识库]{path}分片后没有有效文本内容，跳过")
                    continue

                # 将内容存入向量库
                self.vector_store.add_documents(split_document)

                # 记录这个已经处理好的文件的md5，避免下次重复加载
                save_md5_hex(md5_hex)

                logger.info(f"[加载知识库]{path} 内容加载成功")
            except Exception as e:
                # exc_info为True会记录详细的报错堆栈，如果为False仅记录报错信息本身
                logger.error(f"[加载知识库]{path}加载失败：{str(e)}", exc_info=True)
                continue


if __name__ == '__main__':
    vs = VectorStoreService()

    vs.load_document()

    retriever = vs.get_retriever()

    res = retriever.invoke("迷路")
    for r in res:
        print(r.page_content)
        print("-"*20)


