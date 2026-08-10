# CodeNova 프로젝트 - LLM 백엔드 엔지니어 면접 예상 질문 & 답변

> 대상: 정민영 (LangGraph 설계 / sLLM 파인튜닝 / LLM·sLLM 성능 평가 담당)
> 답변은 모두 실제 프로젝트 코드 기반으로 작성되었습니다.
> 핵심 파일:
> - API 챗봇(LangGraph): `web/apichat/utils/langgraph_node2.py`, `langgraph_setting2.py`, `rag2.py`, `retriever_hybrid.py`, `retriever_bm25.py`, `main3.py`
> - 사내 sLLM(FastAPI): `ai/main.py`, `ai/routers/chat_router.py`, `ai/services/langchain_service.py`, `ai/models/chat_model.py`, `web/internal/utils/sllm.py`

---

## 목차
1. [프로젝트 전반 / 아키텍처](#1-프로젝트-전반--아키텍처)
2. [LangGraph 설계](#2-langgraph-설계)
3. [RAG / 하이브리드 검색](#3-rag--하이브리드-검색)
4. [품질 평가 & 재시도(HyDE) 루프](#4-품질-평가--재시도hyde-루프)
5. [멀티모달 / 멀티턴 / 메모리](#5-멀티모달--멀티턴--메모리)
6. [sLLM 파인튜닝 (Qwen3-8B / LoRA)](#6-sllm-파인튜닝-qwen3-8b--lora)
7. [sLLM 서빙 (FastAPI + vLLM) & TOOL CALL](#7-sllm-서빙-fastapi--vllm--tool-call)
8. [권한 기반 RAG / 보안](#8-권한-기반-rag--보안)
9. [성능 평가 방법론](#9-성능-평가-방법론)
10. [트러블슈팅 / 심화 & 압박 질문](#10-트러블슈팅--심화--압박-질문)

---

## 1. 프로젝트 전반 / 아키텍처

### Q1. 프로젝트를 한 문장으로 소개하고, 본인이 맡은 부분을 설명해주세요.
**A.** CodeNova는 *"구글 API 문서와 사내 내부 문서를 근거로, 인용된 답변과 실행 가능한 예제를 제공하는 개발자 지원 문서 검색 시스템"*입니다.
크게 두 개의 챗봇으로 구성됩니다.
- **API 전문 어시스턴트**: OpenAI GPT-4o 기반, LangGraph로 오케스트레이션, 하이브리드 RAG + 품질평가 재시도 루프
- **사내 문서 sLLM 챗봇**: Qwen3-8B를 LoRA로 파인튜닝해 RunPod + vLLM으로 서빙, 권한 기반 RAG

제가 담당한 부분은 **① API 챗봇의 LangGraph 구조 설계, ② sLLM(Qwen3-8B/Qwen2.5-7B) LoRA 파인튜닝, ③ LLM/sLLM 성능 평가(RAGAS·자체 정량 RAG 평가·TOOL CALL 평가)**입니다.

### Q2. 두 챗봇의 모델/서빙 구조가 다른 이유는?
**A.** 용도와 제약이 다르기 때문입니다.
- **API 챗봇**은 외부 공개 문서를 다루고 멀티모달(이미지/음성)과 구조화 출력(JSON 모드, function calling)이 필요해서, 이런 기능이 성숙한 **OpenAI GPT-4o/4o-mini**를 API로 호출합니다. 비용/지연이 중요한 분류·일상응답 노드는 `gpt-4o-mini`로 내리고, 정확도가 중요한 메인 답변·품질평가는 `gpt-4o`/`gpt-4.1`로 올려 **노드별로 모델을 분리**했습니다.
- **사내 챗봇**은 사내 기밀 문서를 다루므로 외부 API로 본문을 보내기 부담스럽고, 사내 말투·보고체계·TOOL CALL 패턴을 학습시켜야 했습니다. 그래서 **자체 호스팅 가능한 Qwen3-8B를 파인튜닝**해 RunPod GPU에서 vLLM(OpenAI 호환 API)으로 서빙합니다.

코드상으로도 분리되어 있습니다. API 챗봇은 Django 앱(`web/apichat`) 안에서 LangGraph로 직접 돌고, 사내 sLLM은 별도 **FastAPI 서비스**(`ai/`)로 떠 있어 Django가 HTTP로 호출합니다(`web/internal/utils/sllm.py`의 `run_sllm`).

### Q3. 왜 sLLM 챗봇만 별도 FastAPI 서비스로 분리했나요?
**A.** GPU 서빙 계층을 웹 서버와 분리하기 위해서입니다. vLLM 추론은 GPU(RunPod) 위에서 돌고, Django(EB/Docker)는 CPU 환경입니다. `ai/` FastAPI 서비스가 vLLM 앞단의 어댑터 역할을 하면서 **tool call 파싱, 권한별 프롬프트 구성, 제목 생성** 같은 로직을 담당하고, Django는 `SLLM_API_URL/api/v1/chat`로 `{history, permission, tone}`만 POST 하면 됩니다(`web/internal/utils/sllm.py:16-27`). 이렇게 하면 모델 교체/스케일링이 웹과 독립적으로 가능합니다.

---

## 2. LangGraph 설계

### Q4. LangGraph 전체 흐름을 설명해주세요.
**A.** `langgraph_setting2.py`의 `graph_setting()`에 정의되어 있습니다. 진입점은 `analyze_image`이고 흐름은 다음과 같습니다.

```
analyze_image → classify ─┬─(api)──→ extract_queries → split_queries → tool → basic → evaluate
                          ├─(basic)→ simple → END
                          └─(none)─→ impossible → END

evaluate ─┬─(good/final)→ END
          └─(bad)───────→ generate_queries → tool → basic → evaluate (재시도)
```

1. **analyze_image**: 이미지가 있으면 GPT-4o Vision으로 설명 생성
2. **classify**: 질문을 `api / basic / none` 3분류 (`route_from_classify`로 분기)
3. **extract_queries**: 히스토리(최근 4개) + 이미지 설명 + 현재 질문을 통합
4. **split_queries**: 통합 질문을 JSON 모드로 한/영 다중 쿼리로 분리
5. **tool**: LLM이 쿼리별로 적절한 API 태그를 골라 `vector_search_tool` 호출(하이브리드 검색)
6. **basic**: 검색 결과 기반 답변 생성
7. **evaluate**: good/bad 평가 → bad면 `generate_queries`(HyDE 대체 쿼리)로 가서 재검색 후 재답변

### Q5. 왜 분류(classify) 노드를 가장 앞에 두고 3-way로 나눴나요?
**A.** 모든 질문을 RAG로 보내면 비용·지연이 낭비되고, 일상대화나 범위 밖 질문에 엉뚱한 문서를 끌어와 환각이 생깁니다. 그래서 `classify_chain`(gpt-4o, temperature=0)으로 먼저 분기합니다(`rag2.py:109`).
- `api`: 구글 API/코딩/IT 기술 → 전체 RAG 파이프라인
- `basic`: 단순 일상질문 → `simple` 노드에서 gpt-4o-mini로 가볍게 응답
- `none`: 지원 범위 밖(예: 양자컴퓨터, 딥러닝 이론) → `impossible` 노드에서 정중히 거절

프롬프트에 경계 케이스 예시를 다수 넣어 정확도를 높였습니다. 예를 들어 *"구글 맵 API 호출법 알려주고 참고로 배고파"* → `api`, *"오늘 날씨 + 딥러닝 CNN 설명"* → `none`처럼 혼합 질문 규칙까지 명시했습니다(`rag2.py:134-185`).

### Q6. 상태(State) 관리는 어떻게 했나요?
**A.** `ChatState`라는 `TypedDict(total=False)`로 노드 간 데이터를 전달합니다(`langgraph_node2.py:39-56`). 주요 필드는 question/answer, rewritten(통합질문), queries(분리된 쿼리), search_results·qa_search_results(원문/QA 검색결과), messages(히스토리), image·image_analysis, classify, answer_quality, retry(재시도 플래그), hyde_text_results·hyde_qa_results(재검색 결과), search_results_final 등입니다.
`total=False`로 둔 이유는 노드마다 채우는 필드가 다르고, 분기에 따라 어떤 필드는 아예 안 쓰이기 때문입니다(예: basic/none 분기는 검색 관련 필드를 안 채움).

### Q7. `extract_queries`와 `split_queries`를 왜 분리했나요?
**A.** 역할이 다릅니다.
- `extract_queries`: 히스토리(최근 4개) + 이미지 설명 + 현재 질문을 **하나의 맥락(context)으로 통합**만 함(`langgraph_node2.py:147`). LLM 호출 없이 메시지 구조만 만듭니다.
- `split_queries`: 그 통합 맥락을 `query_chain`(JSON 모드)에 넣어 **검색에 적합한 다중 쿼리로 분해**합니다(`langgraph_node2.py:178`).

여기서 핵심은 후속 대화의 대명사/생략 해소입니다. 예: 직전에 "People API 연락처 조회"를 말한 뒤 "그럼 프로필 수정은?"이 오면 → "People API에서 프로필 수정 방법"으로 통합하고, **동일 질문을 한글/영어 둘 다 생성**해 다국어 검색 리콜을 높입니다(`rag2.py:64-99`). 오타 교정도 프롬프트에 포함했습니다(`projets.databeses.gte` → `projects.databases.operations.get`).

---

## 3. RAG / 하이브리드 검색

### Q8. 하이브리드 검색을 어떻게 구성했나요? 가중치는?
**A.** Dense(Chroma + BGE-m3)와 Sparse(BM25)를 `EnsembleRetriever`로 결합했습니다(`retriever_hybrid.py:43`).

```python
return EnsembleRetriever(retrievers=[chroma_retriever, bm25], weights=[0.8, 0.2])
```

- **Dense 0.8 / BM25 0.2**: 의미 기반 검색을 주력으로 하되, BM25로 정확한 메서드명·파라미터명 같은 키워드 매칭을 보완합니다. API 문서는 `projects.databases.operations.get` 같은 **정확한 토큰 매칭이 중요한 식별자**가 많아서 BM25를 섞는 게 효과적이었습니다.
- 태그가 여러 개면 태그별 BM25를 다시 동일가중 `EnsembleRetriever`로 묶은 뒤, 그 결과를 다시 Chroma와 앙상블합니다(`retriever_hybrid.py:36-43`).

### Q8-1. EnsembleRetriever는 점수를 가중평균하나요? 내부 동작을 설명해주세요.
**A.** 흔히 오해하는데, **점수 가중평균이 아니라 RRF(Reciprocal Rank Fusion, 역순위 융합)**입니다. 유사도 점수가 아니라 **순위(rank)**로 합칩니다.

각 문서의 최종 점수는 다음과 같이 누적됩니다(c는 상수, LangChain 기본값 60):

```
최종점수(d) = Σ (d가 등장한 retriever만) weight × 1 / (rank + 60)
```

우리 코드(`weights=[0.8, 0.2]`)로 풀면:

```
최종점수(d) = 0.8 × 1/(Chroma_순위 + 60) + 0.2 × 1/(BM25_순위 + 60)
```

**점수가 아니라 순위로 합치는 이유**는, Dense 코사인 유사도(0~1)와 BM25 점수(0~수십)는 **스케일이 달라 직접 더할 수 없기** 때문입니다. 순위로 정규화하면 두 시스템이 동일 척도(1등, 2등...)가 되어 공정하게 융합됩니다. 따라서 `0.8/0.2`는 *"유사도 점수를 4배 한다"*가 아니라 *"Dense의 **순위 신호**를 BM25보다 4배 신뢰한다"*는 의미입니다.

### Q8-2. 한쪽 retriever에만 있는 문서(예: BM25만 잡은 문서)의 순위는 어떻게 매겨지나요?
**A.** **없는 쪽 항은 페널티가 아니라 0으로 빠집니다.** 즉 그 문서가 등장한 retriever의 항만 더합니다. BM25에만 있는 문서 D라면:

```
최종점수(D) = 0.2 × 1/(BM25_순위 + 60)   ← Chroma 항은 아예 계산 안 함(0)
```

Chroma 항을 "꼴찌 순위"로 넣는 게 아니라 **그냥 더하지 않습니다**(`rrf_score`가 `defaultdict(float)`라 기본값 0 유지). 예시(`weights=[0.8(Chroma), 0.2(BM25)]`, c=60):

| 문서 | Chroma 순위 | BM25 순위 | 계산 | 최종점수 |
|---|---|---|---|---|
| A (둘 다) | 1위 | 2위 | 0.8×1/61 + 0.2×1/62 | **0.01633** |
| B (Chroma만) | 2위 | 없음 | 0.8×1/62 | **0.01290** |
| C (BM25만) | 없음 | 1위 | 0.2×1/61 | **0.00328** |

→ 최종 순위 **A > B > C**. 시사점:
1. **두 retriever가 모두 찾은 A가 가장 강함** (합의 부각 = RRF의 핵심 의도)
2. **C는 BM25 1등인데도 B(Chroma 2등)에 밀림** — 가중치(0.8 vs 0.2)가 순위보다 영향이 클 수 있음
3. **단독 문서도 버려지지 않음** — BM25만 잡은 정확 키워드 매칭 청크가 Dense가 놓쳐도 후보에 남음. 페널티를 안 주는 이유는, BM25가 의미검색을 못 하고 Dense가 정확 토큰 매칭을 놓치는 건 정상이므로 *"못 찾은 것"을 벌하지 않고 "찾은 것"만 신뢰*하는 게 두 방식의 장점을 살리기 때문입니다.

### Q8-3. 같은 문서인지 다른 문서인지는 무엇으로 구분하나요?
**A.** 기본값은 **`doc.page_content`(본문 문자열)의 완전 일치(exact match)**입니다. LangChain `EnsembleRetriever`는 `id_key`가 없으면 `page_content`로, 지정하면 `metadata[id_key]`로 동일성을 판단합니다. 우리 코드는 `id_key`를 안 넘기므로(`retriever_hybrid.py:43`) **`page_content` 기준**입니다.

**중요한 함정**: 이건 fuzzy 매칭이 아니라 **글자 단위 완전 일치**라, 공백·줄바꿈 하나만 달라도 다른 문서로 취급되어 점수가 합산되지 않습니다. 우리 프로젝트에서 이게 문제되지 않는 이유는, **BM25 인덱스를 Chroma DB의 바로 그 문서로 만들었기** 때문입니다(`retriever_bm25.py:25-33`):

```python
data = vs.get(include=["documents", "metadatas"])   # Chroma 원본 page_content
docs = data["documents"]
... BM25Retriever.from_documents([Document(page_content=doc, ...) for ...])
```

Dense와 Sparse가 **동일한 원본 텍스트를 공유**하므로 같은 청크는 양쪽에서 글자까지 동일한 `page_content`로 나와 RRF에서 정확히 합산됩니다. 만약 BM25를 별도 전처리(소문자화 등)해서 만들었다면 `page_content`가 달라져 *같은 문서인데 별개로 취급되는 버그*가 났을 겁니다. 즉 **"같은 풀에서 동일 텍스트로 만든다"는 fusion이 작동하기 위한 전제 조건**입니다. 더 견고하게 하려면 청크에 고유 `doc_id`를 메타데이터로 넣고 `id_key="doc_id"`로 매칭할 수도 있습니다.

### Q9. "태그별 BM25 인덱스 캐싱"이란 무엇이고 왜 했나요?
**A.** BM25는 메모리 기반이라 매 요청마다 전체 문서로 인덱스를 새로 만들면 느립니다. 그래서 **태그(API 종류)별로 BM25 인덱스를 미리 만들어 pickle로 디스크 캐싱**합니다(`retriever_bm25.py`).
- 앱 시작 시 `bm25_index.pkl`(원문)·`bm25_qa_index.pkl`(QA)이 있으면 로드, 없으면 Chroma에서 전체 문서를 꺼내 `tags` 메타데이터로 그룹핑 후 태그별 `BM25Retriever`를 생성해 pickle 저장합니다(`retriever_bm25.py:18-47`).
- 검색 시엔 `bm25_retrievers_by_tag(k)`로 각 retriever의 `k`만 갱신해 재사용합니다(`retriever_bm25.py:50-53`).

이렇게 전역 1회 로드로 두면 요청 지연을 크게 줄일 수 있습니다.

### Q10. 원문 DB와 QA DB를 둘 다 둔 이유는?
**A.** README의 1단계 실험(원문 vs QA vs 하이브리드)에서 검증한 결과입니다.
- 원문 DB: Correctness는 상대적으로 높지만 Recall이 낮음 (Recall 0.65)
- QA DB: Recall/Faithfulness는 좋지만 정답 일치율(Correctness)이 낮음 (Recall 0.75)
- **둘 다 검색**: Recall 0.80으로 가장 높고 균형이 좋음

두 구조가 잘 처리하는 질문 유형이 상호 보완적이어서, 원문(`vector_search_tool`의 `text`)과 QA(`qa`)를 **둘 다 검색해 답변 프롬프트에 함께** 넣습니다(`langgraph_node2.py:204-207`, `rag2.py:33-39`). 답변 프롬프트는 원문/QA/원문 추가/QA 추가 4개 컨텍스트 슬롯을 받습니다.

### Q11. LLM이 검색 태그를 "자동 선택"한다는 게 무슨 의미인가요?
**A.** 11개 구글 API(map, drive, gmail, calendar, bigquery 등)를 메타데이터 태그로 관리하는데, 사용자가 어떤 API인지 명시하지 않아도 됩니다. `tool_based_search_node`에서 LLM(gpt-4.1)에게 **선택 가능한 태그 목록과 함께 "각 쿼리마다 적절한 api_tags를 골라 `vector_search_tool`을 호출하라"**고 지시합니다(`langgraph_node2.py:213-243`).

```python
llm_with_tools = llm.bind_tools([vector_search_tool])
response = llm_with_tools.invoke(search_instruction)
for tool_call in response.tool_calls:
    args = tool_call["args"]   # {"query": ..., "api_tags": ["drive"]}
    result = vector_search_tool.invoke(args)
```

선택된 태그는 Chroma 메타 필터(`{"tags": {"$in": api_tags}}`)로 들어가 **검색 공간을 해당 API로 좁혀** 노이즈를 줄입니다(`retriever_hybrid.py:18-23`). 이게 단순 임베딩 검색 대비 정밀도를 높인 핵심입니다.

---

## 4. 품질 평가 & 재시도(HyDE) 루프

### Q12. 답변 품질 평가 노드는 어떻게 동작하나요?
**A.** `evaluate_answer_node`가 `quality_chain`(gpt-4.1, temperature=0)으로 답변을 good/bad로 판정합니다(`langgraph_node2.py:393`, `rag2.py:251`). 평가 기준의 핵심은:
1. **회피성/무응답 멘트 감지** — "죄송하지만 ~정보는 문서에 없습니다" 같은 답변은 무조건 bad
2. 검색 결과에 없는 정보(환각) → bad
3. 검색 결과와 핵심이 다르면 → bad
4. 검색 결과를 충실히 반영하고 질문에 맞으면 → good

그리고 분기 제어 로직이 중요합니다(`langgraph_node2.py:416-423`):
- classify가 basic/none이면 평가 자체를 건너뛰고 `final`(바로 종료)
- good이면 `good`
- 이미 retry를 한 번 돌았으면(`state["retry"]`) bad여도 `final`로 강제 종료 → **무한 루프 방지**
- 그 외는 `bad` → 재시도

### Q13. "bad"일 때 HyDE 재검색은 어떻게 하나요?
**A.** `generate_alternative_queries` 노드가 HyDE(Hypothetical Document Embeddings) 방식으로 동작합니다(`langgraph_node2.py:430`).
- 원래 질문을 더 검색하는 게 아니라, **LLM이 자신의 지식으로 "가상의 답변"을 한글/영어로 생성**합니다(`rag2.py:286`의 `alternative_queries_chain`). 이 가상 답변을 새 검색 쿼리(`state["queries"]`)로 씁니다.
- `state["retry"] = True`로 세팅하고 다시 `tool` 노드로 보냅니다.

가상 답변은 실제 정답 문서와 임베딩 공간에서 더 가깝기 때문에, 질문 문장보다 검색 리콜이 좋아집니다. 이게 README 실험에서 Faithfulness를 0.69 → 0.88로 끌어올린 VER-4의 핵심이었습니다.

### Q14. 재검색 시 Top-K를 늘리는 이유와 값은?
**A.** 첫 검색은 빠르게(`text_k=5, qa_k=20`), 실패 후 재검색은 더 넓게 봅니다. `tool_based_search_node`에서 `state["retry"]`가 True면 K를 강제로 키웁니다(`langgraph_node2.py:255-257`).

```python
if state["retry"]:
    args["text_k"] = 15
    args["qa_k"] = 30
```

초기에 좁게 잡는 건 비용/속도 때문이고, 한 번 실패했다는 건 "정답이 상위 K에 없었을 가능성"이 크므로 재검색 때 K를 5→15 / 20→30으로 늘립니다. README의 정량 평가에서 (15, 30) 조합이 총점 18.35/20으로 품질·속도 균형이 가장 좋아 채택했습니다. 그리고 첫 검색 결과는 `search_results`에, 재검색 결과는 `hyde_text_results`/`hyde_qa_results`에 따로 저장해 **둘 다 답변 컨텍스트로 합칩니다**(`langgraph_node2.py:272-327`).

### Q15. 검색 결과 중복 제거는?
**A.** `list(dict.fromkeys(...))`로 순서를 유지하면서 중복 page_content를 제거합니다(`langgraph_node2.py:273`). 원문/QA, 그리고 여러 쿼리·여러 태그를 검색하다 보면 같은 청크가 중복될 수 있어서, 답변 프롬프트에 들어가기 전에 정리해 토큰 낭비와 편향을 줄였습니다.

---

## 5. 멀티모달 / 멀티턴 / 메모리

### Q16. 멀티턴 대화 맥락은 어떻게 유지하나요?
**A.** 두 단계로 관리합니다.
1. **LangGraph 체크포인터**: `graph.compile(checkpointer=MemorySaver())`로 `thread_id`(세션 ID) 단위 상태를 유지합니다(`langgraph_setting2.py:63-64`, `main3.py:8`).
2. **히스토리 윈도잉**: 거의 모든 노드에서 `messages[-4:]`로 **최근 4개 메시지만** 사용합니다(`langgraph_node2.py:80, 157, 299` 등). 토큰 비용과 지연을 억제하면서도, 대명사 해소·맥락 통합은 `extract_queries`에서 이 4개로 처리합니다.

### Q17. 이미지/음성 멀티모달은 어떻게 처리하나요?
**A.**
- **이미지**: `analyze_image` 노드가 GPT-4o Vision으로 이미지를 텍스트 설명으로 변환하고(`langgraph_node2.py:105-143`), 이후 classify/extract/answer 노드에서 이 설명을 질문에 합쳐 처리합니다. 이미지 원본은 S3에 저장하고 URL로 넘깁니다.
- **음성**: OpenAI Whisper(`whisper-1`, language="ko")로 STT 후 텍스트 질문으로 처리합니다(`whisper.py`). 즉 이미지/음성을 모두 텍스트로 정규화해서 동일한 LangGraph 파이프라인을 태우는 구조입니다.

### Q18. 이미지 분석 결과를 별도 필드에 저장한 이유는?
**A.** `state["image"]`(원본 URL)는 유지하고 `state["image_analysis"]`(텍스트 설명)를 따로 둡니다(`langgraph_node2.py:134`). 원본은 S3 저장/표시용으로 보존하고, 후속 멀티턴에서 "그 이미지 뭐였지?" 같은 질문에 분석 텍스트를 재사용하기 위해서입니다. 그래서 여러 노드에서 `state.get("image_analysis")`가 있으면 질문에 합쳐 넣습니다.

---

## 6. sLLM 파인튜닝 (Qwen3-8B / LoRA)

### Q19. 왜 풀 파인튜닝이 아니라 LoRA를 썼나요? 설정값은?
**A.** 8B 모델 풀 파인튜닝은 VRAM·시간 비용이 크고, 사내 도메인 적응에는 어댑터만으로 충분했습니다. LoRA 설정은:
- `rank=8, alpha=32, dropout=0.1, target=["q_proj","v_proj"], bias=none`

rank를 8로 낮게 잡아 파라미터 수를 최소화하면서 alpha=32(scaling = alpha/rank = 4)로 적응 강도를 확보했습니다. target을 attention의 q/v projection으로 한정한 건 LoRA의 표준적이고 가성비 좋은 선택입니다.

학습 설정: `epochs=3, batch=4, grad_accum=2(유효 배치 8), lr=1e-4, optimizer=adamw_torch_fused, bf16, max_len=8192`. 메모리 최적화로 `gradient_checkpointing=True, grad_clip=0.3, warmup_ratio=0.03, scheduler=constant`를 사용했습니다.

### Q20. 학습 데이터는 어떻게 구성했나요?
**A.** `qwen3_company_train_dataset_combined.json`으로, **팀별(Backend/Frontend/Data_AI/CTO) × 말투(공손/친구)**를 통합한 데이터셋입니다. 핵심은 **TOOL CALL 패턴 학습**입니다.
- 문서 검색 질문: `질문 → tool_call → tool_response → 모델 답변` 형태로 라벨링
- 일상 질문: 툴 호출 없이 즉시 답변

즉 **"언제 툴을 부르고 언제 안 부르는지"를 멀티턴 맥락 안에서 판단**하도록 학습시킨 게 핵심입니다. 전처리는 Qwen chat 템플릿을 적용하고 **assistant 응답 토큰만 라벨링**(user/system은 loss에서 제외)했습니다.

### Q21. assistant 응답만 라벨링한 이유는?
**A.** 사용자 질문이나 시스템 프롬프트, tool_response까지 loss에 포함하면 모델이 "질문을 생성하는 법"을 배우게 되어 본래 목적(좋은 답변·올바른 tool_call 생성)과 어긋납니다. assistant 턴에만 loss를 걸어야 **모델이 생성해야 할 부분만 정확히 학습**합니다. 이건 instruction tuning의 표준 관행이기도 합니다.

### Q22. Qwen3-8B와 Qwen2.5-7B 중 왜 Qwen3-8B를 최종 선택했나요?
**A.** 두 모델을 같은 데이터로 파인튜닝해 비교했습니다.
- TOOL CALL: 파인튜닝 후 둘 다 비슷(Qwen2.5 tool_selection 99.68% vs Qwen3 98.05%)
- 하지만 **RAGAS에서 Qwen3-8B가 전반적으로 우수**: context_recall 0.93 vs 0.77, faithfulness 0.86 vs 0.80, factual_correctness 0.37 vs 0.32

TOOL CALL은 비등했지만 **실제 답변 품질(RAG 충실도·정답 일치)에서 Qwen3-8B가 앞서서** 최종 선택했습니다. "도구를 잘 부르는 것"과 "검색 결과로 좋은 답을 쓰는 것"은 다른 능력이고, 후자가 사용자 경험에 직결되기 때문입니다.

### Q23. 베이스 모델 대비 개선 폭은?
**A.** Qwen3-8B 기준 파인튜닝으로 tool_selection 79.22% → 98.05% (+18.83%p), params_value_similarity 77.21% → 88.50% (+11.29%p)로 개선됐습니다. 특히 **Qwen2.5-7B는 베이스가 25.97%로 TOOL CALL을 거의 못 했는데 파인튜닝 후 99.68%(+73.71%p)**로 극적으로 올랐습니다. 베이스 모델이 Qwen 특유의 `<tool_call>` XML 포맷을 잘 못 따르던 것을, 포맷·판단을 함께 학습시켜 교정한 결과입니다.

---

## 7. sLLM 서빙 (FastAPI + vLLM) & TOOL CALL

### Q24. 파인튜닝한 모델을 어떻게 서빙하나요?
**A.** RunPod GPU 위에서 **vLLM**으로 OpenAI 호환 엔드포인트를 띄우고, FastAPI 서비스(`ai/`)가 그 앞단 어댑터가 됩니다. `LangChainChatService`에서 `ChatOpenAI`의 `openai_api_base`를 vLLM 주소로 바꿔 호출합니다(`langchain_service.py:201-206`).

```python
self.llm = ChatOpenAI(
    model=self.model_name,
    openai_api_base=self.api_url,   # vLLM 주소
    openai_api_key=self.api_key,
    temperature=0.0,
)
```

vLLM을 쓴 이유는 PagedAttention 기반의 높은 처리량과 OpenAI 호환 API라서 LangChain `ChatOpenAI`를 그대로 재사용할 수 있기 때문입니다. 엔드포인트는 `POST /api/v1/chat`이고 `{history, permission, tone}`을 받습니다(`chat_router.py`, `chat_model.py`).

### Q25. tool call을 어떻게 파싱하나요? (function calling을 안 쓴 이유)
**A.** 파인튜닝된 Qwen은 답변 본문에 **`<tool_call>{...}</tool_call>` XML 형태**로 도구 호출을 내보냅니다. 그래서 OpenAI function calling 대신 **정규식으로 직접 파싱**합니다(`langchain_service.py:354-356`).

```python
matches = re.findall(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", assistant_reply, flags=re.S)
```

흐름은: ① LLM 1차 호출 → ② `<tool_call>` 추출·JSON 파싱 → ③ permission에 맞는 `tool_map`에서 함수 실행 → ④ 결과를 `<tool_response>`로 감싸 대화에 추가 → ⑤ LLM 2차 호출로 최종 답변 생성(`langchain_service.py:358-393`). 이렇게 직접 파싱하는 이유는, 파인튜닝 데이터를 Qwen 네이티브 tool_call 포맷으로 구성했기 때문에 모델 출력 포맷과 서빙 파싱을 일치시킨 것입니다.

### Q26. `<think>` 태그는 왜 제거하나요?
**A.** Qwen3는 추론 과정을 `<think>...</think>`로 출력하는 reasoning 모델입니다. 사용자에게는 사고 과정이 아닌 최종 답만 보여야 하므로 정규식으로 제거합니다(`langchain_service.py:397-401`). 제목 생성 결과에서도 동일하게 정리합니다.

### Q27. 톤(formal/informal)은 어떻게 제어하나요?
**A.** 시스템 프롬프트에서 동적으로 주입합니다(`langchain_service.py:304-325`). `tone="formal"`이면 "정중하고 사무적인 어조", `informal`이면 "가볍고 친근한 반말"로 지시하고, 모르는 경우의 답변까지 톤에 맞게("잘 모르겠습니다" vs "잘 모르겠어") 다르게 지정합니다. 또 *"대화 내역의 말투는 참고하지 말고 무조건 지정 톤으로"*라고 강하게 못박아, 사용자가 반말로 물어도 설정한 톤을 유지하게 했습니다. 톤은 파인튜닝 데이터에도 공손/친구 두 버전을 넣어 학습시켰습니다.

### Q28. 대화 제목은 어떻게 생성하나요?
**A.** 답변 생성 후 동일 모델을 한 번 더 호출해 한국어 제목을 만듭니다(`langchain_service.py:407-447`). 프롬프트에 "12~24자, 명사 중심, 특수문자/이모지 금지, 원문 복붙 금지" 같은 제약을 줘서 일관된 제목이 나오게 했습니다.

---

## 8. 권한 기반 RAG / 보안

### Q29. 직급/팀별 문서 접근 제어를 어떻게 구현했나요?
**A.** 두 단계 방어로 구현했습니다.
1. **벡터 DB 물리적 분리**: 팀별로 Chroma DB를 따로 둡니다(`chroma_db/backend`, `/frontend`, `/data_ai`, `/cto`). 각 검색 툴(`backend_search` 등)은 자기 팀 디렉터리만 바라봅니다(`langchain_service.py:74-187`).
2. **툴 자체 제한**: `permission` 값에 따라 **그 사용자에게 허용된 툴만 `tool_map`에 바인딩**합니다(`langchain_service.py:216-301`). frontend 사용자에겐 `frontend_search`만 주어지고, 애초에 backend 검색 도구가 모델에게 노출되지 않습니다. CTO만 전체를 볼 수 있는 `cto_search`를 받습니다.

즉 모델이 잘못 판단하더라도 **호출할 수 있는 도구 자체가 없어서** 타 팀 문서에 접근이 불가능합니다. 프롬프트 가드가 아니라 **실행 계층에서 차단**한 게 핵심입니다.

### Q30. 프롬프트로만 막지 않고 툴/DB를 분리한 이유는?
**A.** 프롬프트 가드(예: "타 팀 문서는 보지 마")는 프롬프트 인젝션이나 모델 오판으로 뚫릴 수 있습니다. 보안은 LLM의 판단에 의존하면 안 됩니다. 그래서 권한 결정을 **결정론적인 코드 계층**(어떤 툴을 bind 할지, 어떤 디렉터리를 열지)으로 끌어올렸습니다. permission은 `Literal`로 타입을 강제해(`chat_model.py:7`) 허용된 값만 들어오게 했습니다.

---

## 9. 성능 평가 방법론

### Q31. 어떤 지표로 평가했고 왜 여러 방법을 썼나요?
**A.** 세 축으로 평가했습니다.
- **RAGAS**: context_recall(검색이 정답을 포괄하는지), faithfulness(답변이 문맥에 충실한지), factual_correctness(정답과 의미적 일치, F1)
- **자체 정량 RAG 평가**: 정확도/재현율/구체성을 0~3점 척도로 LLM-as-judge 채점 후 100점 환산
- **TOOL CALL 평가**: tool_selection(도구명 일치), params_selection(키 일치), params_value_similarity(값 유사도)

RAGAS만으로는 부족했던 이유는, factual_correctness가 표면적 표현 차이에 민감해서 실제 품질을 과소평가하는 경우가 있었기 때문입니다. 그래서 자체 척도(정확도/재현율/구체성)를 병행해 **상호 검증**했습니다.

### Q32. TOOL CALL 평가의 params_value_similarity는 어떻게 계산했나요?
**A.** 공통 키의 값에 대해 **형태소 Jaccard(0.6) + 문자 유사도(0.4)의 가중 평균**으로 계산했습니다. 단순 문자열 일치는 "구글 드라이브 파일 권한"과 "드라이브 권한 수정"을 다르게 보지만, 의미는 거의 같습니다. 형태소 단위 Jaccard로 의미 겹침을, 문자 유사도로 표기 차이를 함께 잡아 **부분 정답을 공정하게 평가**하려 했습니다.

### Q33. Top-K는 어떻게 최적화했나요?
**A.** 두 챗봇에서 각각 실험했습니다.
- **sLLM**: k=4~8을 정확도/재현율/구체성으로 평가 → **k=7이 평균 72.53으로 최고** → 사내 검색 툴 모두 `similarity_search(k=7)`로 고정(`langchain_service.py:87` 등)
- **API 챗봇**: 재시도 시 (원문, QA) K 조합을 실험 → (15, 30)이 자체 총점 18.35/20으로 품질·속도 균형 최적 → 채택

데이터로 K를 정한 거라 "감"이 아니라 근거가 있습니다.

### Q34. Perplexity 대비 우위는 어떻게 측정했나요?
**A.** 동일 질문셋에 대해 정확도/재현율/신뢰성을 비교해 전체 평균 +21.11%p(정확도 +16.66%p, 재현율 +18.34%p, 신뢰성 +28.34%p) 우위였습니다. 특히 신뢰성 격차가 큰데, 이는 우리 시스템이 **사내/구글 문서라는 한정된 근거 안에서만 답하고 회피성 답변을 평가로 걸러내기** 때문에 환각이 적었던 결과로 해석합니다.

---

## 10. 트러블슈팅 / 심화 & 압박 질문

### Q35. 재시도 루프가 무한 반복될 위험은 어떻게 막았나요?
**A.** `evaluate_answer_node`에서 `state.get("retry")`가 이미 True면, 평가가 또 bad여도 `final`로 강제 종료합니다(`langgraph_node2.py:420-421`). 또 `generate_alternative_queries`도 시작에서 `if state.get("retry"): return state`로 재진입을 막습니다(`langgraph_node2.py:437`). 즉 **재시도는 최대 1회**로 못박아, 비용 폭주와 무한 루프를 동시에 차단했습니다.

### Q36. 현재 구조의 한계나 개선하고 싶은 점은?
**A.** 몇 가지 있습니다.
1. **품질평가가 LLM 1회 호출**이라 비결정적이고 비용이 듭니다. 휴리스틱(검색 점수 임계값) 1차 필터 후 LLM 평가를 2차로 두면 비용을 줄일 수 있습니다.
2. **재시도 1회 고정**이라 어려운 질문은 여전히 실패할 수 있습니다. 신뢰도에 따라 동적으로 횟수를 조절하고 싶습니다.
3. **임베딩 모델 파인튜닝·리랭커 도입**이 다음 단계입니다. 현재는 BGE-m3 그대로라, 도메인 적응 임베딩과 cross-encoder 리랭킹을 넣으면 정밀도가 더 오를 것으로 봅니다.
4. **시맨틱 캐시** 도입으로 유사 질문 반복 호출 비용을 줄이는 것도 계획입니다.

### Q37. CORS를 `allow_origins=["*"]`로 둔 건 보안상 괜찮나요?
**A.** 솔직히 개선 포인트입니다(`ai/main.py:14-20`). 현재 sLLM FastAPI는 내부망에서 Django만 호출하는 구조라 우선 열어뒀지만, 운영에서는 Django 도메인으로 화이트리스트하고, 내부 서비스 간 인증(예: 헤더 토큰)을 추가하는 게 맞습니다.

### Q38. 동기 `requests.post`로 sLLM을 호출하는데 동시성 문제는 없나요?
**A.** Django 쪽 `run_sllm`은 동기 `requests`라(`sllm.py:20`) 요청당 워커가 블로킹됩니다. Gunicorn/Uvicorn 워커 수로 어느 정도 커버하지만, 부하가 커지면 vLLM 응답 대기 동안 워커가 묶입니다. 개선한다면 Django 뷰를 async로 바꾸고 `httpx.AsyncClient`로 비동기 호출하거나, 스트리밍 응답으로 체감 지연을 줄이는 방향을 보고 있습니다. FastAPI 서비스 자체는 이미 `async def`로 작성돼 있습니다(`chat_router.py:9`).

### Q39. 벡터 DB를 구글 드라이브에서 다운로드하는데, 운영상 문제는 없나요?
**A.** 현재 `gdown`으로 드라이브 폴더를 받아 로컬 Chroma로 구성합니다(`vector_db.py`, `langchain_service.py:37-68`). 컨테이너 첫 기동 시 한 번 받아 디렉터리가 있으면 스킵하는 구조라 매번 받지는 않습니다. 다만 드라이브 의존은 운영에서 취약하므로(링크 만료·rate limit), S3나 영속 볼륨에 두고 빌드 타임에 굽는 방식이 더 안정적이라고 봅니다.

### Q40. classify가 틀리면 전체가 망가지는데, 단일 분류 의존 리스크는?
**A.** 맞는 지적입니다. classify가 api를 basic으로 잘못 보내면 RAG를 안 타서 답변 품질이 떨어집니다. 이를 완화하려고 ① 프롬프트에 경계 케이스 예시를 다수 넣어 분류 정확도를 높였고(`rag2.py`), ② basic/none 분기에서도 `simple`/`impossible` 프롬프트가 "이미지/이전 대화 질문은 답해도 된다"는 식으로 일부 안전장치를 뒀습니다. 더 견고하게 하려면 분류 신뢰도가 낮을 때 api 쪽으로 폴백하거나, classify와 answer를 합쳐 한 번에 처리하는 방안도 고려할 수 있습니다.

### Q41. 만약 LLM 비용을 50% 줄여야 한다면 어디부터 손대겠습니까?
**A.** 우선순위는:
1. **노드별 모델 다운그레이드 재검토**: 이미 분류/일상은 4o-mini를 쓰지만, 품질평가(gpt-4.1)를 더 싼 모델이나 룰베이스로 대체 가능한지 A/B 평가
2. **시맨틱 캐시**: 반복·유사 질문 캐싱
3. **재시도 발생률 낮추기**: 1차 검색 품질을 올리면(리랭커) bad 비율이 줄어 재시도(가장 비싼 경로) 호출이 감소
4. **히스토리 윈도우/컨텍스트 압축**: 이미 최근 4개로 제한 중이지만 검색 컨텍스트도 리랭킹 후 상위만 넣어 토큰 절감

모두 **평가 지표로 품질 저하 없이 비용이 주는지 검증**하면서 진행할 겁니다. 이 프로젝트에서 일관되게 지켰던 "데이터로 증명한다"는 원칙 그대로요.

---

## 부록: 자주 나오는 기술 키워드 빠른 답변

| 키워드 | 한 줄 답변 |
|---|---|
| **LangGraph** | 노드/엣지/조건부엣지/체크포인터로 상태 기반 워크플로우를 구성. `StateGraph(ChatState)` + `MemorySaver` |
| **HyDE** | 질문 대신 LLM이 만든 가상 답변으로 재검색해 리콜 향상. 재시도 시 적용 |
| **EnsembleRetriever** | Dense(Chroma/BGE-m3) 0.8 + Sparse(BM25) 0.2를 **RRF(순위 융합)**로 결합. 점수평균 아님, 문서 동일성은 `page_content` 완전일치 |
| **BGE-m3** | 다국어 임베딩 모델. 한/영 쿼리 동시 검색에 적합 |
| **vLLM** | PagedAttention 고처리량 추론 서버, OpenAI 호환 API |
| **LoRA** | rank=8, alpha=32, q/v_proj 타깃 어댑터 파인튜닝 |
| **RAGAS** | context_recall / faithfulness / factual_correctness 자동 평가 |
| **MemorySaver** | thread_id별 LangGraph 상태 영속화(멀티턴) |
| **temperature=0** | 분류·검색·평가의 재현성 확보용 |
| **메타 필터링** | Chroma `{"tags": {"$in": api_tags}}`로 검색 공간 축소 |
