#!/usr/bin/env python
"""등기부등본 파싱 + 분석 CLI

사용법:
  python scripts/parse_registry.py --text backend/tests/fixtures/registry_sample_apt.txt
  python scripts/parse_registry.py --pdf /path/to/registry.pdf
"""

import argparse
import sys
from pathlib import Path

# backend를 import path에 추가
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

from app.services.parser.registry_parser import RegistryParser  # noqa: E402
from app.services.parser.registry_analyzer import RegistryAnalyzer  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="등기부등본 파싱 + 권리분석 CLI"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--text", help="텍스트 파일 경로")
    group.add_argument("--pdf", help="PDF 파일 경로")
    args = parser.parse_args()

    reg_parser = RegistryParser()
    analyzer = RegistryAnalyzer()

    # 파싱
    if args.text:
        path = Path(args.text)
        if not path.exists():
            print(f"파일을 찾을 수 없습니다: {path}")
            sys.exit(1)
        text = path.read_text(encoding="utf-8")
        doc = reg_parser.parse_text(text)
    else:
        path = Path(args.pdf)
        if not path.exists():
            print(f"파일을 찾을 수 없습니다: {path}")
            sys.exit(1)
        doc = reg_parser.parse_pdf(str(path))

    # 분석
    result = analyzer.analyze(doc)

    # 출력
    print("=" * 60)
    print("등기부등본 분석 결과")
    print("=" * 60)
    print()
    print(result.summary)
    print()
    print("-" * 60)
    print(f"파싱 신뢰도: {doc.parse_confidence.value}")
    if doc.parse_warnings:
        print(f"파싱 경고: {', '.join(doc.parse_warnings)}")
    print(f"분석 신뢰도: {result.confidence.value}")
    print(f"이벤트 수: 갑구 {len(doc.gapgu_events)} / 을구 {len(doc.eulgu_events)}")
    print(f"소멸: {len(result.extinguished_rights)}건 / "
          f"인수: {len(result.surviving_rights)}건 / "
          f"불확실: {len(result.uncertain_rights)}건")
    print("-" * 60)


if __name__ == "__main__":
    main()
