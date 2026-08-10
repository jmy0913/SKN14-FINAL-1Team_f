# retriever_bm25.py
from collections import defaultdict
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from .retriever import retriever_setting
from .retriever_qa import retriever_setting2
from .korean_tokenizer import tokenize
import os, pickle

HERE = os.path.dirname(os.path.abspath(__file__))
# 파일명에 토크나이저를 명시한다.
# 예전 인덱스(bm25_index.pkl)는 띄어쓰기로 잘려 있어 지금 질의와 매칭되지 않으므로 재사용 금지.
INDEX_FILE_PATH = os.path.join(HERE, "bm25_index_kiwi.pkl")
QA_INDEX_FILE_PATH = os.path.join(HERE, "bm25_qa_index_kiwi.pkl")

BM25_INDEX = None
BM25_QA_INDEX = None


# 전역에서 한 번만 로드
def _load_bm25_index(path, retriever_func):
    if os.path.exists(path):
        print(f"BM25 인덱스 로드: {path}")
        with open(path, "rb") as f:
            return pickle.load(f)
    else:
        print(f"BM25 인덱스 없음 → 새로 생성: {path}")
        vs = retriever_func()
        data = vs.get(include=["documents", "metadatas"])
        docs, metas = data["documents"], data["metadatas"]

        tag_docs = defaultdict(list)
        for doc, meta in zip(docs, metas):
            tag = meta.get("tags")
            if tag:
                tag_docs[tag].append(Document(page_content=doc, metadata=meta))

        # preprocess_func: 문서를 자르는 방식. 질의도 이 함수로 잘린다.
        bm25_dict = {
            tag: BM25Retriever.from_documents(dlist, preprocess_func=tokenize)
            for tag, dlist in tag_docs.items()
        }

        with open(path, "wb") as f:
            pickle.dump(bm25_dict, f)

        return bm25_dict


# 시작 시 로드
BM25_INDEX = _load_bm25_index(INDEX_FILE_PATH, retriever_setting)
BM25_QA_INDEX = _load_bm25_index(QA_INDEX_FILE_PATH, retriever_setting2)


# BM25_INDEX는 전역이라 모든 요청이 공유한다.
# 전역 객체의 k를 직접 바꾸면(r.k = k) 동시 요청끼리 서로의 k를 덮어쓴다.
# 그래서 k만 바꾼 사본을 요청마다 새로 만들어 넘긴다.
# model_copy는 vectorizer/docs를 원본과 공유하므로 비용이 거의 없다(11개에 약 0.03ms).
def bm25_retrievers_by_tag(k=5):
    return {tag: r.model_copy(update={"k": k}) for tag, r in BM25_INDEX.items()}


def bm25_retrievers_by_tag_qa(k=20):
    return {tag: r.model_copy(update={"k": k}) for tag, r in BM25_QA_INDEX.items()}
