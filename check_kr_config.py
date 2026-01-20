"""
현재 한국 주식 설정 확인
"""
import os
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from kr.strategy import KRStrategy

print("="*80)
print("한국 주식 현재 설정 확인")
print("="*80)

strategy = KRStrategy(enable_filter_check=True)

sectors = strategy.get_sectors()
filter_stocks = strategy.get_filter_stocks()
watch_list = strategy.get_watch_list()

print()
if sectors:
    print(f"[모드] 섹터 OR 로직")
    print(f"[섹터 수] {len(sectors)}개")
    for sector_key, sector_info in sectors.items():
        sector_name = sector_info.get('name', sector_key)
        print(f"  - {sector_name}: {list(sector_info.get('filter_stocks', {}).keys())}")
else:
    print(f"[모드] 기존 AND 로직")
    print(f"[필터 종목] {list(filter_stocks.keys())} ({len(filter_stocks)}종목)")
    print(f"[감시 종목] {watch_list[:5]}... ({len(watch_list)}종목)")
    print()
    print("필터 조건: 모든 필터 종목(005930, 000660, 035420)이 상승해야 매수 가능")

print("="*80)
