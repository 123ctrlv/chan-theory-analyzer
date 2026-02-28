#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论快速分析脚本
使用AKShare获取数据，进行基础缠论分析
"""

import akshare as ak
import json
import sys

def get_stock_data(symbol):
    """获取股票数据"""
    try:
        # 处理股票代码
        if symbol.startswith('6'):
            symbol = 'sh' + symbol
        elif symbol.startswith('0') or symbol.startswith('3'):
            symbol = 'sz' + symbol
        
        # 获取日线数据
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                 start_date="20240101", adjust="qfq")
        df = df.tail(60)  # 取最近60天
        return df
    except Exception as e:
        return {"error": str(e)}

def identify_fraction(klines):
    """识别分型"""
    if len(klines) < 3:
        return {"type": "无", "confidence": 0}
    
    highs = [k['最高'] for k in klines]
    lows = [k['最低'] for k in klines]
    
    # 顶分型
    for i in range(1, len(klines) - 1):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            return {"type": "顶分型", "confidence": 0.7}
    
    # 底分型
    for i in range(1, len(klines) - 1):
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            return {"type": "底分型", "confidence": 0.7}
    
    return {"type": "无", "confidence": 0}

def identify_center(klines):
    """识别中枢"""
    if len(klines) < 10:
        return {"exists": False}
    
    mid = klines[len(klines)//3: len(klines)*2//3]
    highs = [k['最高'] for k in mid]
    lows = [k['最低'] for k in mid]
    
    high = min(highs)
    low = max(lows)
    
    if high > low:
        return {
            "exists": True,
            "high": round(high, 2),
            "low": round(low, 2),
            "range": round(high - low, 2)
        }
    return {"exists": False}

def check_divergence(klines):
    """检查背驰"""
    if len(klines) < 20:
        return {"status": "数据不足"}
    
    recent = klines[-10:]
    previous = klines[-20:-10]
    
    recent_high = max([k['最高'] for k in recent])
    previous_high = max([k['最高'] for k in previous])
    
    recent_vol = sum([k['成交量'] for k in recent])
    previous_vol = sum([k['成交量'] for k in previous])
    
    # 顶背驰
    if recent_high > previous_high and recent_vol < previous_vol * 1.2:
        return {
            "status": "可能背驰",
            "type": "顶背驰",
            "reason": "价格创新高但成交量未放大"
        }
    
    recent_low = min([k['最低'] for k in recent])
    previous_low = min([k['最低'] for k in previous])
    
    # 底背驰
    if recent_low < previous_low and recent_vol < previous_vol * 1.2:
        return {
            "status": "可能背驰",
            "type": "底背驰",
            "reason": "价格创新低但成交量未放大"
        }
    
    return {"status": "未背驰"}

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "请输入股票代码"}, ensure_ascii=False))
        return
    
    symbol = sys.argv[1]
    
    df = get_stock_data(symbol)
    
    if "error" in df:
        print(json.dumps(df, ensure_ascii=False))
        return
    
    klines = df.to_dict(orient='records')
    
    current_price = klines[-1]['收盘']
    
    result = {
        "symbol": symbol,
        "current_price": current_price,
        "fraction": identify_fraction(klines),
        "center": identify_center(klines),
        "divergence": check_divergence(klines)
    }
    
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
