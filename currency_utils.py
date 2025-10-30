"""
통화 형식 변환 유틸리티
USD/KRW 표시 형식 변환 기능 제공
"""

def format_usd_krw(amount_usd, exchange_rate=1300):
    """
    USD 금액을 USD/KRW 형식으로 표시
    
    Args:
        amount_usd (float): USD 금액
        exchange_rate (float): 환율 (기본값: 1300)
    
    Returns:
        str: 포맷된 문자열 (예: "$1,234.56 (₩1,605,928)")
    """
    if amount_usd is None:
        return "N/A"
    
    amount_krw = amount_usd * exchange_rate
    
    return f"${amount_usd:,.2f} (KRW {amount_krw:,.0f})"