def print_positions_table(positions):
    """
    보유종목 리스트를 표 형태로 콘솔에 출력
    positions: list of dict (KIS API 잔고 output1)
    """
    if not positions:
        print("보유종목 없음")
        return
    print(f"{'종목명':<12} {'코드':<10} {'수량':>7} {'매입가':>10} {'현재가':>10} {'평가금액':>12} {'평가손익':>12} {'수익률(%)':>10}")
    print("-"*80)
    for item in positions:
        name = item.get('ovrs_item_name', '-')
        code = item.get('ovrs_pdno', '-')
        qty = float(item.get('ovrs_cblc_qty', 0))
        buy = float(item.get('pchs_avg_pric', 0))
        now = float(item.get('ovrs_now_pric', 0))
        eval_amt = float(item.get('evlu_amt', 0))
        eval_pfls = float(item.get('evlu_pfls_amt', 0))
        try:
            eval_rt = float(item.get('evlu_pfls_rt', 0))
        except Exception:
            eval_rt = 0.0
        print(f"{name:<12} {code:<10} {qty:7.2f} {buy:10.2f} {now:10.2f} {eval_amt:12.2f} {eval_pfls:12.2f} {eval_rt:10.2f}") 