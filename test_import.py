"""
config.py import 테스트
"""
import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from config import KIS_APP_KEY, KIS_APP_SECRET, KIS_BASE_URL, KIS_ACCOUNT_NUMBER
    print("✅ config.py import 성공!")
    print(f"KIS_APP_KEY: {KIS_APP_KEY[:10]}...")
    print(f"KIS_APP_SECRET: {KIS_APP_SECRET[:10]}...")
    print(f"KIS_BASE_URL: {KIS_BASE_URL}")
    print(f"KIS_ACCOUNT_NUMBER: {KIS_ACCOUNT_NUMBER}")
    
except ImportError as e:
    print(f"❌ config.py import 실패: {e}")
    print("현재 디렉토리:", os.getcwd())
    print("Python 경로:", sys.path)

except Exception as e:
    print(f"❌ 기타 오류: {e}") 