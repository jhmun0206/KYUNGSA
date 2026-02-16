"""애플리케이션 설정

모든 환경변수는 .env 파일에서 관리한다. 절대 하드코딩 금지.
"""

from pathlib import Path

from pydantic_settings import BaseSettings

# 프로젝트 루트: backend/ 의 상위 디렉토리
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """환경변수 로드 설정"""

    # 공공데이터포털 (data.go.kr) — 실거래가, 공시지가, 건축물대장
    PUBLIC_DATA_API_KEY: str = ""

    # CODEF API (등기부등본·공시가격·토지공시지가·시세)
    # CODEF_SERVICE_TYPE: "sandbox" | "demo" | "production" (기본값: sandbox)
    CODEF_SERVICE_TYPE: str = "sandbox"
    CODEF_SANDBOX_CLIENT_ID: str = ""
    CODEF_SANDBOX_CLIENT_SECRET: str = ""
    CODEF_DEMO_CLIENT_ID: str = ""
    CODEF_DEMO_CLIENT_SECRET: str = ""
    CODEF_CLIENT_ID: str = ""
    CODEF_CLIENT_SECRET: str = ""
    CODEF_PUBLIC_KEY: str = ""

    # CODEF 등기부등본 전용
    CODEF_REGISTRY_ENDPOINT: str = "/v1/kr/public/ck/real-estate-register/status"

    # Vworld (국토정보플랫폼)
    VWORLD_API_KEY: str = ""

    # 카카오 개발자
    KAKAO_REST_API_KEY: str = ""

    # 대법원 경매정보 크롤러 (courtauction.go.kr)
    COURT_AUCTION_REQUEST_INTERVAL: float = 3.0  # 요청 간격 (초)
    COURT_AUCTION_MAX_RETRIES: int = 3  # 최대 재시도 횟수
    COURT_AUCTION_TIMEOUT: int = 30  # 요청 타임아웃 (초)

    # 인터넷등기소 비회원 로그인 (CODEF 등기부 열람용)
    IROS_PHONE_NO: str = ""          # 전화번호 (-없이 숫자만), CODEF 'phoneNo'에 매핑
    IROS_PASSWORD: str = ""          # 비회원 비밀번호 (숫자 4자리), CODEF 'password'에 매핑 (RSA 암호화)

    # 전자민원캐시 (등기부 열람 수수료 결제, 건당 700원)
    # https://minwon.cashgate.co.kr
    IROS_EPREPAY_NO: str = ""        # 선불전자지급수단번호 (12자리), CODEF 'ePrepayNo'에 매핑 (평문)
    IROS_EPREPAY_PASS: str = ""      # 선불전자지급수단 비밀번호, CODEF 'ePrepayPass'에 매핑 (평문)

    # OPENAI API (LLM 설명 생성용)
    OPENAI_API_KEY: str = ""

    # DB
    DATABASE_URL: str = "postgresql://kyungsa:password@localhost:5432/kyungsa_db"
    DB_ECHO: bool = False           # SQLAlchemy SQL 로깅
    DB_POOL_SIZE: int = 5           # 커넥션 풀 크기
    DB_MAX_OVERFLOW: int = 10       # 풀 초과 허용 수
    REDIS_URL: str = "redis://localhost:6379/0"
    MONGODB_URL: str = "mongodb://localhost:27017/kyungsa"

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
    }


# 싱글턴 인스턴스
settings = Settings()
