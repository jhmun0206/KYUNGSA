# KYUNGSA 서버 배포 가이드

## systemd 서비스 파일 설치

```bash
# 1. 서비스/타이머 파일 복사
sudo cp /home/eric/projects/KYUNGSA/deploy/*.service /etc/systemd/system/
sudo cp /home/eric/projects/KYUNGSA/deploy/*.timer   /etc/systemd/system/

# 2. systemd 데몬 리로드
sudo systemctl daemon-reload

# 3. 배치 수집기 타이머 (기존, 매일 03:00 서울 진행 물건 수집)
sudo systemctl enable kyungsa-batch.timer
sudo systemctl start  kyungsa-batch.timer

# 4. 매각결과 수집 타이머 (신규, 매일 06:00 전국 낙찰 완료 건 수집)
sudo systemctl enable kyungsa-sale-results.timer
sudo systemctl start  kyungsa-sale-results.timer

# 5. 낙찰가 사후 추적 타이머 (신규, 매주 일 07:00)
sudo systemctl enable kyungsa-winning-bids.timer
sudo systemctl start  kyungsa-winning-bids.timer

# 6. 타이머 목록 확인
systemctl list-timers | grep kyungsa
```

## 타이머 스케줄 요약

| 타이머 | 스케줄 | 작업 |
|--------|--------|------|
| kyungsa-batch.timer | 매일 03:00 KST | 서울 5개 법원 진행 물건 수집 (BatchCollector) |
| kyungsa-sale-results.timer | 매일 06:00 KST | 전국 낙찰 완료 건 수집 (SaleResultCollector, ~11분) |
| kyungsa-winning-bids.timer | 매주 일 07:00 KST | 기수집 물건 낙찰가 사후 추적 (WinningBidCollector) |

## 로그 확인

```bash
# 실시간 로그
journalctl -u kyungsa-sale-results.service -f
journalctl -u kyungsa-winning-bids.service -f
journalctl -u kyungsa-batch.service -f

# 최근 실행 결과
journalctl -u kyungsa-sale-results.service -n 100
```

## 수동 실행 (테스트)

```bash
cd /home/eric/projects/KYUNGSA

# 매각결과 수집 dry-run
PYTHONPATH=backend backend/.venv/bin/python scripts/collect_sale_results.py --all-courts --dry-run --limit 50

# 실제 실행
PYTHONPATH=backend backend/.venv/bin/python scripts/collect_sale_results.py --all-courts

# 낙찰가 추적 dry-run
PYTHONPATH=backend backend/.venv/bin/python scripts/collect_winning_bids.py --all-seoul --dry-run --limit 10
```

## timezone 확인

```bash
timedatectl | grep "Time zone"
# Asia/Seoul (KST, +0900) 인지 확인
# 아니면: sudo timedatectl set-timezone Asia/Seoul
```
