"""LLM 기반 리스크 설명 생성

LLM은 오직 '설명'만 한다.
입력: 룰 엔진 결과 (RuleResult)
출력: 자연어 설명 문자열

금지 표현 처리:
- config/banned_phrases.json 기준
- 금지 표현 발견 시 '삭제'가 아닌 '재작성' 프롬프트 실행
"""
