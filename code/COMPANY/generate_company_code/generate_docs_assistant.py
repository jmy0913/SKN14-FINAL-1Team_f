import os
import datetime as dt
from pathlib import Path
from textwrap import dedent
from typing import List, Dict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DOCS_DIR = Path("docs")
DOCS_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

TEMPERATURE = 0.5
MAX_TOKENS = 1100  # A4 한 장 분량 목표치

# -------- 문서 스펙(6개) --------
project_docs = [
    ("프로젝트 관리 문서", "M-Core 프로젝트 진행 현황 보고서"),
    ("프로젝트 관리 문서", "M-Core 프로젝트 일정 관리 문서"),
    ("프로젝트 관리 문서", "M-Core 프로젝트 리스크 관리 보고서"),  
    ("프로젝트 관리 문서", "M-Core 프로젝트 품질 점검 보고서"), 
]

team_performance = [
    ("팀 성과 자료", "콘텐츠팀 KPI 달성 현황"),
    ("팀 성과 자료", "영업지원팀 팀 단위 성과 분석"),
    ("팀 성과 자료", "고객지원팀 팀 성과 종합 보고서"), 
]

feedback_docs = [
    ("내부 평가/피드백 문서", "사원 근무 태도 평가 보고서"),
    ("내부 평가/피드백 문서", "사원 성과 평가 보고서"),
    ("내부 평가/피드백 문서", "사원 역량 개발 피드백 보고서"), 
]

DOC_SPECS: List[Dict] = [
    *[{"category": c, "title": t} for c, t in project_docs],
    *[{"category": c, "title": t} for c, t in team_performance],
    *[{"category": c, "title": t} for c, t in feedback_docs],
]

# -------- 프롬프트 --------
SYSTEM_PROMPT = dedent("""
    너는 디지털 교육회사 M-Core의 내부 문서 저자이다.
    독자: '대리(실무 리더/관리)'.
    금지: 회사 전략/재무·민감 수치/계약 조건/미공개 로드맵/고객 식별정보/개인정보/내부 비공개 URL.
    문서는 팀 관리/프로젝트 조율 관점에서 실행 가능한 단계·체크리스트 중심으로 작성한다.
    출력은 평문 텍스트로만 한다.
""").strip()

def make_user_prompt(category: str, title: str, today: str) -> str:
    base = f"""{title}
(분류: {category}) | 회사: M-Core | 버전: v1.0 | 작성일: {today}
{"-"*70}
작성 지침:
- 언어: 한국어, 평문 텍스트(마크다운/표 금지)
- 분량: A4 1장(약 550~750단어) 내외
- 대리 수준에서 필요한 정보만 포함 (전략/재무/고객 식별정보 제외)
- 실행 단계/체크리스트/검증 포인트 포함
- 문서 끝에 '다음 개정 제안' 2~3줄
"""
    if category == "프로젝트 관리 문서":
        body = dedent("""
            포함 섹션:
            1) 개요(프로젝트명, 목적, 범위)
            2) 진행 현황(마일스톤, 완료율, 주요 산출물)
            3) 일정 관리(간트 차트 요약, 지연/차질 요인)
            4) 리스크/이슈(발생 현황, 영향도, 대응 계획)
            5) 협업/의사결정 사항(결정 내용, 근거, 후속 조치)
            6) 다음 단계 및 요청사항(내부/외부 의존성 포함)
            7) 개정 이력(v1.0 — 오늘)
        """).strip()
    elif category == "팀 성과 자료":
        body = dedent("""
            포함 섹션:
            1) 개요(팀/기간/지표 정의)
            2) KPI 달성 현황(지표별 목표 대비 실적, 해석/주요 인사이트)
            3) 주요 성과 요약(성과 포인트/베스트 사례)
            4) 개선 필요 영역(미달성 원인, 개선 과제 및 담당/기한)
            5) 팀 협업/기여도 분석(의존성, 업무 분장 적정성)
            6) 향후 액션 플랜(2주/분기 단위 체크리스트)
            7) 개정 이력(v1.0 — 오늘)
        """).strip()
    else:  # 내부 평가/피드백 문서
        body = dedent("""
            포함 섹션:
            1) 평가 개요(대상/기간/평가자/평가 기준 요약)
            2) 근무 태도(협업/책임감/규율 준수: 사례 기반)
            3) 성과 요약(업무 목표 달성도, 기여 사례)
            4) 강점 분석(재현 가능한 행동/스킬)
            5) 개선/보완 필요 영역(행동 지표와 측정 방법)
            6) 피드백 요약 및 후속 조치(코칭 플랜/점검 일정)
            7) 개정 이력(v1.0 — 오늘)
        """).strip()

    footer = dedent("""
        주의:
        - 전략/재무/내부 링크/고객 실명/민감 개인정보는 쓰지 말 것.
        - 대리가 팀 관리 및 조율에 활용할 수 있도록 구체적인 단계와 체크리스트 작성.
    """).strip()

    return f"{base}\n{body}\n\n{footer}"

def safe_slug(text: str) -> str:
    keep = []
    for ch in text:
        if ch.isalnum() or ch in " ._-()[]{}&":
            keep.append(ch)
        else:
            keep.append("_")
    slug = "".join(keep).strip().replace("  ", " ")
    return "_".join(slug.split())

def generate_and_write_docs():
    client = OpenAI(api_key=API_KEY)

    today = dt.date.today().isoformat()
    index_lines = []
    for idx, spec in enumerate(DOC_SPECS, start=1):
        category, title = spec["category"], spec["title"]
        user_prompt = make_user_prompt(category, title, today)

        completion = client.chat.completions.create(
            model=MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = completion.choices[0].message.content.strip()

        prefix = f"{idx:02d}"
        filename = f"{prefix}_{safe_slug(category)}__{safe_slug(title)}.txt"
        out_path = DOCS_DIR / filename

        header = (
            f"===== {category} | {title} =====\n"
            f"작성일: {today}\n"
            f"회사: M-Core | 대상: 대리(실무 리더/관리)\n"
            f"{'-'*70}\n"
        )
        out_path.write_text(header + content + "\n", encoding="utf-8")

        index_lines.append(f"{prefix}. {category} - {title} -> {filename}")

    # 인덱스 파일 작성
    (DOCS_DIR / "INDEX.txt").write_text(
        "M-Core 사내문서(대리용) — 생성 결과 목록\n" +
        "\n".join(index_lines) + "\n",
        encoding="utf-8"
    )

    print(f"[완료] docs/ 폴더에 {len(DOC_SPECS)}개 문서를 저장했습니다.")
    print("목록: docs/INDEX.txt 를 확인하세요.")

if __name__ == "__main__":
    generate_and_write_docs()