"""
주문 관리 및 미체결 처리 시스템
"""
import time
import logging
from datetime import datetime, timedelta
from threading import Thread, Lock
from kis_api import KISAPIClient
from config import *

class OrderManager:
    def __init__(self):
        self.api_client = KISAPIClient()
        self.logger = logging.getLogger(__name__)
        self.pending_orders = {}  # 미체결 주문 추적
        self.orders_lock = Lock()  # 스레드 안전성을 위한 락
    
    def place_order_with_tracking(self, symbol, quantity, price, order_type="buy"):
        """주문 실행 및 추적 시작"""
        order_id = self.api_client.place_order(symbol, quantity, price, order_type)
        
        if order_id:
            with self.orders_lock:
                self.pending_orders[order_id] = {
                    "symbol": symbol,
                    "quantity": quantity,
                    "price": price,
                    "order_type": order_type,
                    "order_time": datetime.now(),
                    "status": "pending"
                }
            
            # 미체결 모니터링 스레드 시작
            monitor_thread = Thread(target=self._monitor_order, args=(order_id,))
            monitor_thread.daemon = True
            monitor_thread.start()
            
            self.logger.info(f"주문 추적 시작: {order_id} ({symbol} {order_type})")
        
        return order_id
    
    def _monitor_order(self, order_id):
        """개별 주문 모니터링"""
        try:
            while True:
                time.sleep(60)  # 1분마다 체크
                
                with self.orders_lock:
                    if order_id not in self.pending_orders:
                        break
                    
                    order_info = self.pending_orders[order_id]
                    order_time = order_info["order_time"]
                
                # 20분 경과 체크
                if datetime.now() - order_time > timedelta(minutes=ORDER_TIMEOUT_MINUTES):
                    self._handle_timeout_order(order_id)
                    break
                
                # 주문 상태 확인
                status = self.api_client.get_order_status(order_id)
                if status:
                    if status["filled_qty"] == status["order_qty"]:
                        # 완전 체결
                        self._handle_filled_order(order_id)
                        break
                    elif status["status"] in ["02", "03"]:  # 취소됨
                        self._handle_cancelled_order(order_id)
                        break
                
        except Exception as e:
            self.logger.error(f"주문 모니터링 오류 {order_id}: {e}")
    
    def _handle_timeout_order(self, order_id):
        """타임아웃된 주문 처리"""
        try:
            with self.orders_lock:
                if order_id in self.pending_orders:
                    order_info = self.pending_orders[order_id]
                    symbol = order_info["symbol"]
                    
                    # 주문 취소 시도
                    if self.api_client.cancel_order(order_id, symbol):
                        self.logger.info(f"타임아웃 주문 취소 완료: {order_id}")
                        order_info["status"] = "cancelled_timeout"
                    else:
                        self.logger.error(f"타임아웃 주문 취소 실패: {order_id}")
                        order_info["status"] = "cancel_failed"
                    
                    # 추적 목록에서 제거
                    del self.pending_orders[order_id]
                    
        except Exception as e:
            self.logger.error(f"타임아웃 주문 처리 오류 {order_id}: {e}")
    
    def _handle_filled_order(self, order_id):
        """체결된 주문 처리"""
        try:
            with self.orders_lock:
                if order_id in self.pending_orders:
                    order_info = self.pending_orders[order_id]
                    self.logger.info(f"주문 체결 완료: {order_id} ({order_info['symbol']} {order_info['order_type']})")
                    
                    order_info["status"] = "filled"
                    # 추적 목록에서 제거
                    del self.pending_orders[order_id]
                    
        except Exception as e:
            self.logger.error(f"체결 주문 처리 오류 {order_id}: {e}")
    
    def _handle_cancelled_order(self, order_id):
        """취소된 주문 처리"""
        try:
            with self.orders_lock:
                if order_id in self.pending_orders:
                    order_info = self.pending_orders[order_id]
                    self.logger.info(f"주문 취소됨: {order_id} ({order_info['symbol']} {order_info['order_type']})")
                    
                    order_info["status"] = "cancelled"
                    # 추적 목록에서 제거
                    del self.pending_orders[order_id]
                    
        except Exception as e:
            self.logger.error(f"취소 주문 처리 오류 {order_id}: {e}")
    
    def get_pending_orders_count(self):
        """미체결 주문 개수 조회"""
        with self.orders_lock:
            return len(self.pending_orders)
    
    def cancel_all_pending_orders(self):
        """모든 미체결 주문 취소"""
        try:
            with self.orders_lock:
                order_ids = list(self.pending_orders.keys())
            
            for order_id in order_ids:
                with self.orders_lock:
                    if order_id in self.pending_orders:
                        order_info = self.pending_orders[order_id]
                        symbol = order_info["symbol"]
                        
                        if self.api_client.cancel_order(order_id, symbol):
                            self.logger.info(f"미체결 주문 취소: {order_id}")
                            del self.pending_orders[order_id]
                        else:
                            self.logger.error(f"미체결 주문 취소 실패: {order_id}")
            
        except Exception as e:
            self.logger.error(f"전체 주문 취소 오류: {e}")
    
    def cleanup_old_orders(self):
        """오래된 주문 정리"""
        try:
            current_time = datetime.now()
            
            with self.orders_lock:
                expired_orders = []
                
                for order_id, order_info in self.pending_orders.items():
                    if current_time - order_info["order_time"] > timedelta(hours=1):
                        expired_orders.append(order_id)
                
                for order_id in expired_orders:
                    self.logger.info(f"오래된 주문 정리: {order_id}")
                    del self.pending_orders[order_id]
                    
        except Exception as e:
            self.logger.error(f"주문 정리 오류: {e}")
    
    def get_order_summary(self):
        """주문 현황 요약"""
        with self.orders_lock:
            summary = {
                "total_pending": len(self.pending_orders),
                "buy_orders": 0,
                "sell_orders": 0,
                "orders": []
            }
            
            for order_id, order_info in self.pending_orders.items():
                if order_info["order_type"] == "buy":
                    summary["buy_orders"] += 1
                else:
                    summary["sell_orders"] += 1
                
                summary["orders"].append({
                    "order_id": order_id,
                    "symbol": order_info["symbol"],
                    "type": order_info["order_type"],
                    "quantity": order_info["quantity"],
                    "price": order_info["price"],
                    "time": order_info["order_time"].strftime("%H:%M:%S"),
                    "status": order_info["status"]
                })
            
            return summary

