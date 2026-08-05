from dataclasses import dataclass
from langchain_core.documents import Document
from sentence_transformers import CrossEncoder
from typing import List, Dict, Any, Optional
import chromadb
#import shutil, gc, time, os

# Document 구현
@dataclass
class MyDocument:
    page_content:str
    metadata: dict | None=None


class BGEreranker:
    def __init__(self, model_name="BAAI/bge-reranker-base"):
        print(f"[INFO] Loading reranker model: {model_name}")
        self.model = CrossEncoder(model_name)
        print("[INFO] Model loaded")

    def score(self, query: str, text: str) -> float:
        """
        query: 질문
        text : 평가할 문서/문맥
        return: relevance score (float)
        """
        score = self.model.predict([(query, text)])[0]
        return float(score)

# ================================
# rerank_easy
# ================================
# def rerank_easy(query, lc_docs, reranker, top_n=10):
#     reranked_results = []
#     for doc in lc_docs:
#         rscore = reranker.score(query, doc.page_content)
#         reranked_results.append({
#             "doc": doc,
#             "rerank_score": rscore
#         })
#     reranked_results.sort(key=lambda x: x["rerank_score"], reverse=True)
#     return reranked_results[:top_n]

def rerank_easy(query, candidates: List[Dict[str, Any]], reranker, top_n=10):
    reranked_results = []

    for candidate  in candidates:
        doc = candidate["doc"]
        text = doc.page_content
        rscore = reranker.score(query, text)

        reranked_results.append({
            "doc": doc,
            "embed_score": candidate.get("embed_score", 0.0),
            "rerank_score": float(rscore)
        })
    reranked_results.sort(key=lambda x: x["rerank_score"], reverse=True)
    reranked_results = reranked_results[:top_n]  # 내림차순 정렬 후 Top5개를 선택
    filtered_rerankscore = [
        doc for doc in reranked_results
        if doc["rerank_score"] >= 0.6    # Top5개를 다시 rerank score로 다시 필터링
    ]

    return filtered_rerankscore
    #return reranked_results[:top_n]


# 임베딩 score 사용
#from langchain_community.vectorstores.chroma import Chroma
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={'device': 'cpu'},
    encode_kwargs={'normalize_embeddings': True}
)


from typing import List, Tuple
from langchain_core.documents import Document
def top_k_by_embedding_score( results: List[Tuple[Document, float]], top_k: int = 10):
    """
    results: [(Document, distance_score), ...]
    return : [{"doc": Document, "embed_score": similarity}, ...]
    """

    scored = []
    for doc, distance in results:
        similarity = 1.0 - distance  # cosine distance → similarity
        scored.append({
            "doc": doc,
            "embed_score": similarity
        })

    # similarity 기준 내림차순 정렬
    scored.sort(key=lambda x: x["embed_score"], reverse=True)

    return scored[:top_k]



# def lcDocument_chroma_vector_embedding(lc_docs,persist_directory=None):
#
#     vector_store = None
#     gc.collect()
#     time.sleep(0.2)
#
#     shutil.rmtree("./chroma_db", ignore_errors=True)
#
#     vector_store = Chroma.from_documents(
#         lc_docs,
#         embeddings,
#         persist_directory="./chroma_db",
#         collection_metadata={"hnsw:space": "cosine"}
#     )
#
#     # 이게 있어야 sqlite가 생성/저장됨 (문서 0개면 당연히 안 생김)
#     vector_store.add_documents(lc_docs)
#
#     print("count =", vector_store._collection.count())
#     print("sqlite exists =", os.path.exists(os.path.join("./chroma_db", "chroma.sqlite3")))
#
#     return vector_store

DB_DIR = "./chroma_db"
COLLECTION = "my_company_analy"


def delete_all_docs(collection, batch_size=5000):
    """
    Chroma 버전 호환:
    - 어떤 버전은 include=["ids"] 불가
    - ids는 get() 결과에 기본 포함되는 경우가 많음
    """
    deleted = 0

    while True:
        # include를 비우거나 최소한으로(메모리 절약)
        res = collection.get(limit=batch_size)  #  include 지정하지 않음
        ids = res.get("ids") or []

        if not ids:
            break

        collection.delete(ids=ids)
        deleted += len(ids)

    return deleted

# 앱 시작 시 1회만 생성/오픈 (중요)
client = chromadb.PersistentClient(path=DB_DIR)
vector_store = Chroma(
    client=client,
    collection_name=COLLECTION,
    embedding_function=embeddings,
)


def lcDocument_chroma_vector_embedding(lc_docs):

    #  문서만 전부 삭제 / 갱신
    deleted = delete_all_docs(vector_store._collection)
    print("deleted =", deleted)

    # 다시 적재
    vector_store.add_documents(lc_docs)

    print("count =", vector_store._collection.count())
    return vector_store

if __name__ == "__main__":
    docs_split = [
        MyDocument(page_content="여의도에서 용산까지는 지하철 5호선을 이용하면 편리합니다.", metadata={"id": 0}),
        MyDocument(page_content="서울 여의도에서 용산은 한강을 건너 이동하며, 버스와 지하철 모두 가능합니다.", metadata={"id": 1}),
        MyDocument(page_content="용산 맛집 추천: 삼겹살, 파스타, 와인바", metadata={"id": 2}),
        MyDocument(page_content="여의도에서 남산타워 가는 버스 노선 안내", metadata={"id": 3}),
        MyDocument(page_content="용산역 가는 방법: 여의도역 → 5호선 → 공덕 환승", metadata={"id": 4}),
    ]
    # 위 코드는 Document() 를 생성할 수 는 있지만
    # 오류는 없지만 안정적으로 Chroma.from_documents() 로 벡터 DB화 하려면
    # LangChain Document 리스트를 사용 추천 함.
    # 따라서 아래 처럼 치환 해서 사용해야을 권함.
    # Document ==> langchain_core.documents
    lc_docs = [Document(page_content=d.page_content, metadata=d.metadata) for d in docs_split]

    # ----------------------------
    # Rerank
    # ----------------------------
    reranker = BGEreranker()

    query = "서울 여의도에서 용산 가는 방법"


    print("\n==============================")
    print("B) rerank 결과")
    print("==============================")
    reranked = rerank_easy(query, lc_docs, reranker, top_n=3)
    print(reranked)
    for i, r in enumerate(reranked, 1):
        print(f"[{i}] rerank={r['rerank_score']:.4f}")
        print(f"    {r['doc'].page_content}")


