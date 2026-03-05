#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论增强分析脚本 - 使用专业缠论库
功能：自动识别笔、线段、中枢、买卖点、背驰
"""

import json
import sys
import pandas as pd

def get_stock_data(symbol):
    """获取股票数据"""
    try:
        import akshare as ak
        
        # 处理股票代码
        if symbol.startswith('6'):
            symbol = 'sh' + symbol
        elif symbol.startswith('0') or symbol.startswith('3'):
            symbol = 'sz' + symbol
        
        # 获取日线数据
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                 start_date="20240101", adjust="qfq")
        df = df.tail(120)  # 取最近120天
        return df
    except Exception as e:
        return {"error": str(e)}

def analyze_with_czsc(df):
    """使用czsc进行专业分析"""
    try:
        from czsc import CzscTrader
        from czsc.utils import BarGenerator
        
        # 转换数据格式
        bars = []
        for _, row in df.iterrows():
            bar = {
                'dt': row['日期'],
                'open': row['开盘'],
                'high': row['最高'],
                'low': row['最低'],
                'close': row['收盘'],
                'vol': row['成交量']
            }
            bars.append(bar)
        
        # 创建笔分析器
        bg = BarGenerator(base_freq='日线', freqs=['30分钟', '5分钟'])
        for bar in bars:
            bg.update(bar)
        
        # 获取分析结果
        cts = bg.traders.get('日线')
        if cts:
            return {
                "status": "success",
                "bars_count": len(bars),
                "latest_price": bars[-1]['close'] if bars else None,
                "analysis": "使用czsc进行笔/线段/中枢分析"
            }
        return {"status": "no_data"}
        
    except ImportError:
        return {"status": "czsc_not_installed"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def simple_analysis(df):
    """简单分析（不依赖czsc）"""
    klines = df.to_dict(orient='records')
    
    if len(klines) < 3:
        return {"error": "数据不足"}
    
    # 最新价格
    current = klines[-1]
    current_price = current['收盘']
    
    # 1. 分型识别
    fraction = analyze_fraction(klines)
    
    # 2. 笔方向判断
    brush = analyze_brush(klines)
    
    # 3. 中枢识别
    center = analyze_center(klines)
    
    # 4. 背驰判断
    divergence = analyze_divergence(klines)
    
    # 5. 买卖点
    buy_sell = analyze_buy_sell_points(klines, center, divergence)
    
    return {
        "symbol": df.iloc[0]['代码'] if '代码' in df.columns else "Unknown",
        "current_price": current_price,
        "change_pct": round((current_price - klines[-2]['收盘']) / klines[-2]['收盘'] * 100, 2),
        "volume": current['成交量'],
        "fraction": fraction,
        "brush": brush,
        "center": center,
        "divergence": divergence,
        "buy_sell_points": buy_sell,
        "recommendation": generate_recommendation(buy_sell, center, current_price)
    }

def analyze_fraction(klines):
    """识别分型"""
    if len(klines) < 3:
        return {"type": "无", "confidence": 0}
    
    highs = [k['最高'] for k in klines[-5:]]
    lows = [k['最低'] for k in klines[-5:]]
    
    # 顶分型: 中间K线最高
    for i in range(1, len(klines) - 1):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            return {"type": "顶分型", "position": "高位", "confidence": 0.7}
    
    # 底分型: 中间K线最低
    for i in range(1, len(klines) - 1):
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            return {"type": "底分型", "position": "低位", "confidence": 0.7}
    
    return {"type": "无", "confidence": 0}

def analyze_brush(klines):
    """识别笔方向"""
    if len(klines) < 10:
        return {"direction": "不确定", "reason": "数据不足"}
    
    # 简单判断：最近5天收盘价趋势
    recent_closes = [k['收盘'] for k in klines[-5:]]
    if recent_closes[-1] > recent_closes[0]:
        return {"direction": "向上笔", "strength": "强势"}
    elif recent_closes[-1] < recent_closes[0]:
        return {"direction": "向下笔", "strength": "弱势"}
    return {"direction": "横盘整理", "strength": "中性"}

def analyze_center(klines):
    """识别中枢"""
    if len(klines) < 20:
        return {"exists": False, "reason": "数据不足"}
    
    # 取中间30%的K线
    start = len(klines) // 3
    end = len(klines) * 2 // 3
    mid_klines = klines[start:end]
    
    highs = [k['最高'] for k in mid_klines]
    lows = [k['最低'] for k in mid_klines]
    
    high = min(highs)
    low = max(lows)
    
    if high > low:
        return {
            "exists": True,
            "high": round(high, 2),
            "low": round(low, 2),
            "range": round(high - low, 2),
            "mid": round((high + low) / 2, 2)
        }
    return {"exists": False}

def analyze_divergence(klines):
    """背驰分析"""
    if len(klines) < 30:
        return {"status": "数据不足"}
    
    recent = klines[-10:]
    previous = klines[-20:-10]
    
    # 价格
    recent_high = max([k['最高'] for k in recent])
    previous_high = max([k['最高'] for k in previous])
    
    # 成交量
    recent_vol = sum([k['成交量'] for k in recent])
    previous_vol = sum([k['成交量'] for k in previous])
    
    # 顶背驰
    if recent_high > previous_high:
        vol_ratio = recent_vol / previous_vol if previous_vol > 0 else 1
        if vol_ratio < 1.2:
            return {
                "status": "可能顶背驰",
                "type": "顶背驰",
                "price_change": f"+{round((recent_high/previous_high-1)*100, 1)}%",
                "vol_change": f"{round((vol_ratio-1)*100, 1)}%",
                "signal": "⚠️ 风险信号"
            }
    
    # 底背驰
    recent_low = min([k['最低'] for k in recent])
    previous_low = min([k['最低'] for k in previous])
    
    if recent_low < previous_low:
        vol_ratio = recent_vol / previous_vol if previous_vol > 0 else 1
        if vol_ratio < 1.2:
            return {
                "status": "可能底背驰",
                "type": "底背驰",
                "price_change": f"{round((recent_low/previous_low-1)*100, 1)}%",
                "vol_change": f"{round((vol_ratio-1)*100, 1)}%",
                "signal": "📈 机会信号"
            }
    
    return {"status": "未背驰", "signal": "中性"}

def analyze_buy_sell_points(klines, center, divergence):
    """三类买卖点分析"""
    current_price = klines[-1]['收盘']
    points = {}
    
    if center.get('exists'):
        center_high = center['high']
        center_low = center['low']
        
        # 一买：价格在中枢下方，可能底背驰
        if divergence.get('type') == '底背驰':
            points['一买'] = {
                "position": "中枢下方",
                "signal": "🔔 潜在买入点",
                "reason": "底背驰+中枢下方"
            }
        
        # 二买：回落不破中枢上沿
        if current_price > center_low and current_price < center_high:
            points['二买'] = {
                "position": f"中枢区间({center_low}-{center_high})",
                "signal": "⚡ 回调买入点",
                "reason": "回落至中枢上沿附近"
            }
        
        # 三买：突破中枢后回落不破
        if current_price > center_high:
            points['三买'] = {
                "position": f"中枢上方({current_price})",
                "signal": "🚀 突破买入点",
                "reason": "突破中枢上沿"
            }
        
        # 卖点
        if divergence.get('type') == '顶背驰':
            points['一卖'] = {
                "position": "高位",
                "signal": "⚠️ 风险卖点",
                "reason": "顶背驰出现"
            }
    else:
        # 无中枢时简单判断
        if divergence.get('type') == '底背驰':
            points['一买'] = {"signal": "🔔 底背驰买入点"}
        if divergence.get('type') == '顶背驰':
            points['一卖'] = {"signal": "⚠️ 顶背驰卖点"}
    
    return points if points else {"状态": "观望", "signal": "中性"}

def generate_recommendation(buy_sell, center, current_price):
    """生成操作建议"""
    if '一买' in buy_sell:
        return "⚠️ 建议关注买入机会，可考虑分批建仓"
    elif '三买' in buy_sell:
        return "⚡ 突破走势，建议回调企稳后买入"
    elif '二买' in buy_sell:
        return "📍 回调至中枢区间，可考虑买入"
    elif '一卖' in buy_sell:
        return "⚠️ 注意风险，建议减仓或观望"
    else:
        return "📊 建议继续观望，等待明确信号"

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "请输入股票代码"}, ensure_ascii=False))
        return
    
    symbol = sys.argv[1]
    
    print(f"正在获取 {symbol} 数据...", file=sys.stderr)
    df = get_stock_data(symbol)
    
    if isinstance(df, dict) and "error" in df:
        print(json.dumps(df, ensure_ascii=False))
        return
    
    # 尝试使用czsc
    czsc_result = analyze_with_czsc(df)
    
    if czsc_result.get("status") == "success":
        # 使用czsc分析结果
        print(json.dumps(czsc_result, ensure_ascii=False, indent=2))
    else:
        # 使用简单分析
        print("使用基础分析模式", file=sys.stderr)
        result = simple_analysis(df)
        print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
