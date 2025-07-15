import datetime
import pytz
from datetime import datetime, timedelta

def is_us_market_open():
    """
    미국 주식시장이 열려있는지 확인
    미국 동부시간 기준 9:30 AM - 4:00 PM (EST/EDT)
    """
    # 미국 동부시간대 설정
    eastern = pytz.timezone('US/Eastern')
    now_eastern = datetime.now(eastern)
    
    # 현재 요일 확인 (월-금만 거래)
    if now_eastern.weekday() >= 5:  # 토요일(5), 일요일(6)
        return False
    
    # 거래 시간 확인 (9:30 AM - 4:00 PM)
    market_open = now_eastern.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now_eastern.replace(hour=16, minute=0, second=0, microsecond=0)
    
    return market_open <= now_eastern <= market_close

def get_us_market_status():
    """
    미국 시장 상태 정보 반환
    """
    eastern = pytz.timezone('US/Eastern')
    now_eastern = datetime.now(eastern)
    
    # 다음 거래일 계산
    next_trading_day = now_eastern
    while next_trading_day.weekday() >= 5:  # 주말이면 다음 월요일로
        next_trading_day += timedelta(days=1)
    
    # 다음 거래일 오픈 시간
    next_open = next_trading_day.replace(hour=9, minute=30, second=0, microsecond=0)
    
    return {
        'is_open': is_us_market_open(),
        'current_time_est': now_eastern.strftime('%Y-%m-%d %H:%M:%S %Z'),
        'next_trading_day': next_open.strftime('%Y-%m-%d %H:%M:%S %Z')
    }

if __name__ == "__main__":
    status = get_us_market_status()
    print(f"미국 시장 상태: {'열림' if status['is_open'] else '닫힘'}")
    print(f"현재 시간 (EST): {status['current_time_est']}")
    print(f"다음 거래일: {status['next_trading_day']}") 