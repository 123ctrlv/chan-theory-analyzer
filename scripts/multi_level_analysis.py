#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论多级别联立分析
同时分析日线、30分钟、5分钟级别，综合判断走势
"""

import json
import sys

def get_multi_level_data(symbol):
    """获取多级别数据"""
    try:
        import akshare as ak
        
        # 处理股票代码
        if symbol.startswith('6'):
            ts_code = 'sh' + symbol
        elif symbol.startswith('0') or symbol.startswith('3'):
            ts_code = 'sz' + symbol
        
        data = {}
        
        # 日线
        try:
            df_daily = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                          start_date="20250101", adjust="qfq")
            data['日线'] = df_daily.tail(120).to_dict(orient='records')
        except:
            data['日线'] = None
        
        # 30分钟线
        try:
            df_30m = ak.stock_zh_a_hist_min_em(symbol=symbol, period="30", 
                                                 start_date="20250201", adjust="qfq")
            data['30分钟'] = df_30m.tail(200).to_dict(orient='records')
        except:
            data['30分钟'] = None
        
        # 5分钟线
        try:
            df_5m = ak.stock_zh_a_hist_min_em(symbol=symbol, period="5", 
                                               start_date="20250301", adjust="qfq")
            data['5分钟'] = df_5m.tail(200).to_dict(orient='records')
        except:
            data['5分钟'] = None
        
        return data
    except Exception as e:
        return {"error": str(e)}

def analyze_level(klines, level_name):
    """分析单个级别"""
    if not klines or len(klines) < 10:
        return {"level": level_name, "status": "数据不足"}
    
    klines = klines[-60:]  # 取最近60根
    
    # 基础数据
    current = klines[-1]
    current_price = current.get('收盘', current.get('close', 0))
    
    # 1. 分型识别
    fraction = identify_fraction(klines)
    
    # 2. 笔方向
    brush = identify_brush_direction(klines)
    
    # 3. 中枢
    center = identify_center(klines)
    
    # 4. 背驰
    divergence = identify_divergence(klines)
    
    # 5. 均线
    ma = calculate_ma(klines)
    
    return {
        "level": level_name,
        "current_price": round(current_price, 2),
        "fraction": fraction,
        "brush": brush,
        "center": center,
        "divergence": divergence,
        "ma": ma,
        "trend": determine_trend(brush, center, ma)
    }

def identify_fraction(klines):
    """识别分型"""
    if len(klines) < 5:
        return {"type": "无"}
    
    highs = [k.get('最高', k.get('high', 0)) for k in klines[-5:]]
    lows = [k.get('最低', k.get('low', 0)) for k in klines[-5:]]
    
    # 顶分型
    for i in range(1, len(klines) - 2):
        if highs[i] > highs[i-1] and highs[i] > highs[i+1]:
            return {"type": "顶分型", "position": "高位"}
    
    # 底分型
    for i in range(1, len(klines) - 2):
        if lows[i] < lows[i-1] and lows[i] < lows[i+1]:
            return {"type": "底分型", "position": "低位"}
    
    return {"type": "无"}

def identify_brush_direction(klines):
    """识别笔方向"""
    if len(klines) < 5:
        return {"direction": "不确定"}
    
    closes = [k.get('收盘', k.get('close', 0)) for k in klines[-5:]]
    
    if closes[-1] > closes[0]:
        return {"direction": "向上", "strength": "强势" if closes[-1]/closes[0] > 1.03 else "中性"}
    elif closes[-1] < closes[0]:
        return {"direction": "向下", "strength": "弱势" if closes[0]/closes[-1] > 1.03 else "中性"}
    return {"direction": "横盘", "strength": "中性"}

def identify_center(klines):
    """识别中枢"""
    if len(klines) < 20:
        return {"exists": False}
    
    start = len(klines) // 3
    end = len(klines) * 2 // 3
    mid = klines[start:end]
    
    highs = [k.get('最高', k.get('high', 0)) for k in mid]
    lows = [k.get('最低', k.get('low', 0)) for k in mid]
    
    high = min(highs)
    low = max(lows)
    
    if high > low:
        return {
            "exists": True,
            "zone": f"{round(low, 2)}-{round(high, 2)}",
            "mid": round((high + low) / 2, 2)
        }
    return {"exists": False}

def identify_divergence(klines):
    """背驰分析"""
    if len(klines) < 20:
        return {"status": "数据不足"}
    
    recent = klines[-10:]
    previous = klines[-20:-10]
    
    recent_high = max([k.get('最高', k.get('high', 0)) for k in recent])
    previous_high = max([k.get('最高', k.get('high', 0)) for k in previous])
    
    recent_vol = sum([k.get('成交量', k.get('vol', 0)) for k in recent])
    previous_vol = sum([k.get('成交量', k.get('vol', 0)) for k in previous])
    
    if recent_high > previous_high and recent_vol < previous_vol * 1.2:
        return {"status": "顶背驰", "signal": "⚠️"}
    
    recent_low = min([k.get('最低', k.get('low', 0)) for k in recent])
    previous_low = min([k.get('最低', k.get('low', 0)) for k in previous])
    
    if recent_low < previous_low and recent_vol < previous_vol * 1.2:
        return {"status": "底背驰", "signal": "📈"}
    
    return {"status": "无背驰", "signal": "➖"}

def calculate_ma(klines):
    """计算均线"""
    if len(klines) < 5:
        return {}
    
    closes = [k.get('收盘', k.get('close', 0)) for k in klines]
    
    ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else 0
    ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else 0
    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else 0
    
    return {
        "MA5": round(ma5, 2),
        "MA10": round(ma10, 2),
        "MA20": round(ma20, 2),
        "position": "多头" if ma5 > ma10 else "空头"
    }

def determine_trend(brush, center, ma):
    """综合判断趋势"""
    direction = brush.get('direction', "横盘")
    ma_position = ma.get("position", "横盘")
    
    if direction == "向上" and ma_position == "多头":
        return "上涨趋势"
    elif direction == "向下" and ma_position == "空头":
        return "下跌趋势"
    elif direction == "横盘":
        return "横盘整理"
    else:
        return "震荡整理"

def multi_level_synthesis(symbol, levels_data):
    """多级别综合分析"""
    results = {}
    
    # 分析每个级别
    for level_name, klines in levels_data.items():
        if klines:
            results[level_name] = analyze_level(klines, level_name)
    
    # 综合判断
    synthesis = synthesize_levels(results)
    
    return {
        "symbol": symbol,
        "levels": results,
        "synthesis": synthesis,
        "trading_signal": generate_signal(synthesis)
    }

def synthesize_levels(levels):
    """综合各级别分析"""
    if not levels:
        return {"status": "数据获取失败"}
    
    # 统计各级别状态
    trends = [l.get("trend", "") for l in levels.values() if l.get("trend")]
    divergences = [l.get("divergence", {}).get("status", "") for l in levels.values()]
    
    # 方向一致性
    up_count = sum(1 for t in trends if "上涨" in t)
    down_count = sum(1 for t in trends if "下跌" in t)
    
    # 背驰情况
    top_div = "顶背驰" in divergences
    bottom_div = "底背驰" in divergences
    
    synthesis = {
        "trend_consensus": "上涨" if up_count > down_count else ("下跌" if down_count > up_count else "震荡"),
        "divergence_summary": {
            "top_divergence": top_div,
            "bottom_divergence": bottom_div
        },
        "analysis": []
    }
    
    # 添加分析说明
    if top_div:
        synthesis["analysis"].append("⚠️ 高级别出现顶背驰，注意风险")
    if bottom_div:
        synthesis["analysis"].append("📈 高级别出现底背驰，关注机会")
    if up_count > down_count:
        synthesis["analysis"].append("📈 多级别向上共振，看涨")
    elif down_count > up_count:
        synthesis["analysis"].append("⚠️ 多级别向下共振，注意风险")
    
    return synthesis

def generate_signal(synthesis):
    """生成交易信号"""
    trend = synthesis.get("trend_consensus", "")
    div = synthesis.get("divergence_summary", {})
    
    if div.get("bottom_divergence") and trend == "上涨":
        return {"signal": "强烈买入", "action": "建议建仓", "risk": "中等"}
    elif div.get("bottom_divergence") and trend == "震荡":
        return {"signal": "关注买入", "action": "可考虑分批建仓", "risk": "中低"}
    elif div.get("top_divergence") and trend == "下跌":
        return {"signal": "强烈卖出", "action": "建议减仓", "risk": "高"}
    elif div.get("top_divergence") and trend == "震荡":
        return {"signal": "注意风险", "action": "可考虑减仓", "risk": "中高"}
    elif trend == "上涨":
        return {"signal": "持有待涨", "action": "继续持有", "risk": "中"}
    elif trend == "下跌":
        return {"signal": "观望为主", "action": "等待企稳", "risk": "中"}
    else:
        return {"signal": "震荡整理", "action": "高抛低吸", "risk": "中"}

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "请输入股票代码"}, ensure_ascii=False))
        return
    
    symbol = sys.argv[1]
    
    # 获取多级别数据
    data = get_multi_level_data(symbol)
    
    if "error" in data:
        print(json.dumps(data, ensure_ascii=False))
        return
    
    # 多级别分析
    result = multi_level_synthesis(symbol, data)
    
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
