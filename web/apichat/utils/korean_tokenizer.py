# korean_tokenizer.py
"""BM25 전용 한국어 형태소 토크나이저.

BM25는 토큰이 글자 그대로 일치해야 점수를 준다.
기본 전처리(text.split())는 띄어쓰기로만 자르기 때문에
    문서 "드라이브에서 파일을 업로드합니다" -> ["드라이브에서", "파일을", "업로드합니다"]
    질의 "드라이브 파일 업로드"            -> ["드라이브", "파일", "업로드"]
겹치는 토큰이 하나도 없어 점수가 0이 된다.

여기서는 형태소 분석으로 조사/어미를 떼고 알맹이만 남긴다.
    문서 -> ["드라이브", "파일", "업로드", ...]
    질의 -> ["드라이브", "파일", "업로드"]

주의: 인덱스를 만들 때와 질의를 자를 때 반드시 같은 함수를 써야 한다.
      이 파일을 수정하면 BM25 인덱스(pkl)를 반드시 다시 만들어야 한다.
"""

from typing import List

from kiwipiepy import Kiwi

# Kiwi 인스턴스는 프로세스당 하나만. 분석 호출은 스레드 안전하므로 락이 필요 없다.
_kiwi = Kiwi()

# 남길 품사
#   NNG 일반명사 / NNP 고유명사 / VV 동사 / VA 형용사
#   SL  영문(projectId, insert 등 코드 식별자) / SN 숫자 / SH 한자
# 조사(JK*), 어미(E*), 접미사(XS*), 기호(S[FPW]) 등은 버린다.
_KEEP = {"NNG", "NNP", "VV", "VA", "SL", "SN", "SH"}


def tokenize(text: str) -> List[str]:
    """문자열을 BM25용 토큰 리스트로 변환한다."""
    if not text:
        return []

    tokens = []
    for t in _kiwi.tokenize(text):
        # 불규칙 활용은 'VA-I'처럼 접미가 붙으므로 앞부분만 본다
        if t.tag.split("-")[0] in _KEEP:
            # 영문은 대소문자를 통일해야 질의와 매칭된다 (BigQuery == bigquery)
            tokens.append(t.form.lower())

    return tokens
