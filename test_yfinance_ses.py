import yfinance as yf

def test_ses_with_yfinance():
    ticker_symbol = "SES"
    print(f"=== {ticker_symbol} yfinance 테스트 ===")
    
    try:
        ses_data = yf.Ticker(ticker_symbol)
        
        # 현재 가격 조회 (가장 최근 종가)
        try:
            current_price = ses_data.history(period="1d")['Close'].iloc[-1]
            print(f"✅ SES AI Corporation (NYSE:SES) 현재가: ${current_price:.2f}")
            
            # 추가 정보
            info = ses_data.info
            print(f"📊 회사명: {info.get('longName', 'N/A')}")
            print(f"🏢 섹터: {info.get('sector', 'N/A')}")
            print(f"📈 시가총액: {info.get('marketCap', 'N/A')}")
            print(f"💰 거래소: {info.get('exchange', 'N/A')}")
            
        except IndexError:
            print(f"❌ SES AI Corporation (NYSE:SES)의 현재 가격 데이터를 가져올 수 없습니다.")
            print("   데이터가 없거나 지연될 수 있습니다.")
        except Exception as e:
            print(f"❌ 가격 조회 오류: {e}")
        
        # 최근 거래 데이터 확인
        try:
            hist = ses_data.history(period="5d")
            if not hist.empty:
                print(f"\n📈 최근 5일 거래 데이터:")
                print(hist[['Open', 'High', 'Low', 'Close', 'Volume']].tail())
            else:
                print("❌ 거래 데이터가 없습니다.")
        except Exception as e:
            print(f"❌ 거래 데이터 조회 오류: {e}")
            
    except Exception as e:
        print(f"❌ yfinance 연결 오류: {e}")

if __name__ == "__main__":
    test_ses_with_yfinance() 