"""
거래기록 CSV 저장 모듈
"""
import csv
import os
from datetime import datetime
import pytz
from typing import Dict, List, Optional

class TransactionLogger:
    def __init__(self, csv_dir: str = "transaction_logs", prefix: str = ""):
        """
        거래기록 CSV 저장기 초기화

        Args:
            csv_dir: CSV 파일 저장 디렉토리
            prefix: 파일명 접두사 (예: "kr" -> "kr_trading_log_...")
        """
        self.csv_dir = csv_dir
        self.prefix = prefix

        # 한국 시장용은 Asia/Seoul, 미국은 US/Eastern
        if prefix == "kr":
            self.tz = pytz.timezone('Asia/Seoul')
        else:
            self.tz = pytz.timezone('US/Eastern')

        # 하위 호환성을 위해 et_tz도 유지
        self.et_tz = self.tz
        
        # 디렉토리 생성
        if not os.path.exists(csv_dir):
            os.makedirs(csv_dir)
        
        # CSV 파일명 (날짜별)
        self.csv_filename = self._get_csv_filename()
        self.csv_path = os.path.join(csv_dir, self.csv_filename)
        
        # CSV 헤더 정의
        self.csv_headers = [
            'timestamp',
            'date',
            'time',
            'action',
            'symbol',
            'quantity',
            'price',
            'total_amount',
            'order_type',
            'status',
            'profit_loss',
            'profit_rate',
            'balance_cash',
            'balance_total',
            'notes'
        ]
        
        # CSV 파일 초기화
        self._init_csv_file()
    
    def _get_csv_filename(self) -> str:
        """현재 날짜로 CSV 파일명 생성"""
        now = datetime.now(self.tz)
        if self.prefix:
            return f"{self.prefix}_trading_log_{now.strftime('%Y%m%d')}.csv"
        return f"trading_log_{now.strftime('%Y%m%d')}.csv"
    
    def _init_csv_file(self):
        """CSV 파일 초기화 (헤더 작성)"""
        # 파일이 없거나 비어있으면 헤더 작성 (BOM 포함 UTF-8로 Excel 호환성 확보)
        if not os.path.exists(self.csv_path) or os.path.getsize(self.csv_path) == 0:
            with open(self.csv_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(self.csv_headers)
    
    def log_transaction(self, 
                       action: str,
                       symbol: str,
                       quantity: int,
                       price: float,
                       order_type: str = "market",
                       status: str = "pending",
                       profit_loss: Optional[float] = None,
                       profit_rate: Optional[float] = None,
                       balance_cash: Optional[float] = None,
                       balance_total: Optional[float] = None,
                       notes: str = ""):
        """
        거래기록을 CSV 파일에 저장
        
        Args:
            action: 거래 유형 (buy, sell, check_balance, etc.)
            symbol: 종목 심볼
            quantity: 수량
            price: 가격
            order_type: 주문 유형 (market, limit)
            status: 주문 상태 (pending, filled, cancelled, failed)
            profit_loss: 손익 금액
            profit_rate: 손익률 (%)
            balance_cash: 예수금
            balance_total: 총 자산
            notes: 추가 메모
        """
        try:
            now = datetime.now(self.tz)

            # 총 거래금액 계산
            total_amount = quantity * price if quantity and price else 0

            # CSV 행 데이터
            row_data = [
                now.isoformat(),  # timestamp
                now.strftime('%Y-%m-%d'),  # date
                now.strftime('%H:%M:%S'),  # time
                action,
                symbol,
                quantity,
                price,
                total_amount,
                order_type,
                status,
                profit_loss,
                profit_rate,
                balance_cash,
                balance_total,
                notes
            ]
            
            # CSV 파일에 기록 (BOM 포함 UTF-8로 Excel 호환성 확보)
            with open(self.csv_path, 'a', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(row_data)
                
        except Exception as e:
            print(f"거래기록 저장 오류: {e}")
    
    def log_balance_check(self, balance_data: Dict):
        """
        잔고 조회 기록
        
        Args:
            balance_data: 잔고 데이터
        """
        try:
            cash = balance_data.get('cash', 0)
            positions = balance_data.get('positions', [])
            total_value = cash + sum(pos.get('current_value', 0) for pos in positions)
            
            # 예수금 기록
            self.log_transaction(
                action="balance_check",
                symbol="CASH",
                quantity=0,
                price=0,
                order_type="check",
                status="completed",
                balance_cash=cash,
                balance_total=total_value,
                notes=f"보유종목: {len(positions)}개"
            )
            
            # 각 보유종목 기록
            for pos in positions:
                symbol = pos.get('symbol', '')
                quantity = pos.get('quantity', 0)
                current_price = pos.get('current_price', 0)
                profit_loss = pos.get('profit_loss', 0)
                profit_rate = pos.get('profit_rate', 0)
                
                if symbol and quantity > 0:
                    self.log_transaction(
                        action="holdings_check",
                        symbol=symbol,
                        quantity=quantity,
                        price=current_price,
                        order_type="check",
                        status="holding",
                        profit_loss=profit_loss,
                        profit_rate=profit_rate * 100 if profit_rate else 0,  # 퍼센트로 변환
                        notes=f"평균단가: {pos.get('avg_price', 0)}"
                    )
                    
        except Exception as e:
            print(f"잔고 기록 저장 오류: {e}")
    
    def log_buy_order(self, symbol: str, quantity: int, price: float, 
                     order_type: str = "market", status: str = "pending",
                     balance_cash: Optional[float] = None, notes: str = ""):
        """매수 주문 기록"""
        self.log_transaction(
            action="buy",
            symbol=symbol,
            quantity=quantity,
            price=price,
            order_type=order_type,
            status=status,
            balance_cash=balance_cash,
            notes=notes
        )
    
    def log_sell_order(self, symbol: str, quantity: int, price: float,
                      profit_loss: float, profit_rate: float,
                      order_type: str = "market", status: str = "pending",
                      notes: str = ""):
        """매도 주문 기록"""
        self.log_transaction(
            action="sell",
            symbol=symbol,
            quantity=quantity,
            price=price,
            order_type=order_type,
            status=status,
            profit_loss=profit_loss,
            profit_rate=profit_rate * 100 if profit_rate else 0,  # 퍼센트로 변환
            notes=notes
        )
    
    def log_strategy_execution(self, strategy_type: str, result: str, notes: str = ""):
        """전략 실행 기록"""
        self.log_transaction(
            action=f"strategy_{strategy_type}",
            symbol="STRATEGY",
            quantity=0,
            price=0,
            order_type="strategy",
            status=result,
            notes=notes
        )
    
    def get_today_logs(self) -> List[Dict]:
        """오늘의 거래기록 조회"""
        logs = []
        try:
            if os.path.exists(self.csv_path):
                with open(self.csv_path, 'r', encoding='utf-8') as csvfile:
                    reader = csv.DictReader(csvfile)
                    for row in reader:
                        logs.append(row)
        except Exception as e:
            print(f"거래기록 조회 오류: {e}")
        
        return logs
    
    def get_summary(self) -> Dict:
        """오늘 거래 요약 (실제 매수/매도만 카운트)"""
        logs = self.get_today_logs()
        summary = {
            'buy_orders': 0,
            'sell_orders': 0,
            'total_profit_loss': 0,
            'successful_trades': 0
        }

        for log in logs:
            action = log.get('action', '')
            status = log.get('status', '')
            profit_loss = float(log.get('profit_loss', 0) or 0)

            if action == 'buy':
                summary['buy_orders'] += 1
            elif action == 'sell':
                summary['sell_orders'] += 1
                summary['total_profit_loss'] += profit_loss
                if status == 'filled':
                    summary['successful_trades'] += 1

        # 실제 매수+매도 건수만 카운트
        summary['total_transactions'] = summary['buy_orders'] + summary['sell_orders']

        return summary 