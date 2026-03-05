#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论三类买卖点精确识别
基于中枢、背驰、走势类型综合判断
"""

import json
import sys

# 买卖点定义
BUY_POINTS = {
    "一买": {
        "name": "第一类买点",
        "description": "下跌趋势背驰后的第一个底分型",
        "position": "中枢下方",
        "signal": "🔔",
        "risk": "高",
        "condition": "底背驰 + 创出新低"
    },
    "二买": {
        "name": "第二类买点", 
        "description": "回落不破中枢上沿",
        "position": "中枢上沿附近",
        "signal": "⚡",
        "risk": "中",
        "condition": "回调不破中枢高点"
    },
    "三买": {
        "name": "第三类买点",
        "description": "突破中枢后回调不破",
        "position": "中枢上方",
        "signal": "🚀",
        "risk": "中低",
        "condition": "突破后回调不进入中枢"
    },
    "类一买": {
        "name": "类第一类买点",
        "description": "次级别背驰形成的买点",
        "position": "中枢下方或附近",
        "signal": "🔶",
        "risk": "中高",
        "condition": "次级别背驰"
    }
}

SELL_POINTS = {
    "一卖": {
        "name": "第一类卖点",
        "description": "上涨趋势背驰后的第一个顶分型",
        "position": "中枢上方",
        "signal": "⚠️",
        "risk": "高",
        "condition": "顶背驰 + 创出新低"
    },
    "二卖": {
        "name": "第二类卖点",
        "description": "反弹不破中枢下沿",
        "position": "中枢下沿附近",
        "signal": "🛑",
        "risk": "中",
        "condition": "反弹不破中枢低点"
    },
    "三卖": {
        "name": "第三类卖点",
        "description": "跌破中枢后反弹不破",
        "position": "中枢下方",
        "signal": "💔",
        "risk": "中低",
        "condition": "跌破后反弹不进入中枢"
    }
}

def analyze_buy_sell_points_advanced(klines, center, divergence, level_name):
    """精确分析三类买卖点"""
    
    if len(klines) < 30:
        return {"error": "数据不足，无法分析买卖点"}
    
    current = klines[-1]
    current_price = current.get('收盘', current.get('close', 0))
    
    # 获取历史高低点
    highs = [k.get('最高', k.get('high', 0)) for k in klines[-30:]]
    lows = [k.get('最低', k.get('low', 0)) for k in klines[-30:]]
    
    recent_high = max(highs)
    recent_low = min(lows)
    
    result = {
        "level": level_name,
        "current_price": round(current_price, 2),
        "price_range": {"high": round(recent_high, 2), "low": round(recent_low, 2)},
        "buy_points": [],
        "sell_points": [],
        "active_point": None,
        "analysis": []
    }
    
    # 中枢分析
    if center.get('exists'):
        center_high = None
        center_low = None
        
        # 解析中枢区间
        zone = center.get('zone', '')
        if '-' in zone:
            parts = zone.split('-')
            center_low = float(parts[0])
            center_high = float(parts[1])
        
        result["center"] = {
            "exists": True,
            "zone": zone,
            "high": center_high,
            "low": center_low
        }
        
        # ========== 买点分析 ==========
        
        # 一买：价格在中枢下方 + 底背驰
        if current_price < center_low:
            if divergence.get('status') == '底背驰':
                result["buy_points"].append({
                    "type": "一买",
                    "name": "第一类买点",
                    "price": round(center_low * 0.98, 2),  # 略低于中枢
                    "signal": "🔔 强烈买入",
                    "reason": "底背驰 + 处于中枢下方（背驰段）",
                    "stop_loss": round(center_low, 2),
                    "risk": "较高",
                    "confidence": "80%"
                })
                result["analysis"].append("✅ 存在第一类买点：底背驰+中枢下方")
        
        # 二买：回落不破中枢上沿
        if center_low < current_price < center_high:
            # 检查是否从高位回落
            if recent_high > center_high * 1.02:  # 曾经突破
                result["buy_points"].append({
                    "type": "二买",
                    "name": "第二类买点",
                    "price": round(center_low, 2),
                    "signal": "⚡ 回调买入",
                    "reason": "回落至中枢上沿获得支撑",
                    "stop_loss": round(center_low * 0.95, 2),
                    "risk": "中等",
                    "confidence": "70%"
                })
                result["analysis"].append("✅ 存在第二类买点：回落至中枢上沿")
        
        # 三买：突破中枢后回调不破
        if current_price > center_high:
            # 检查是否从下方突破上来
            pre_center = klines[-20:-10]
            pre_highs = [k.get('最高', k.get('high', 0)) for k in pre_center]
            
            if max(pre_highs) < center_high:  # 之前在中枢内或下方
                result["buy_points"].append({
                    "type": "三买",
                    "name": "第三类买点",
                    "price": round(current_price, 2),
                    "signal": "🚀 突破买入",
                    "reason": "突破中枢后回调不破",
                    "stop_loss": round(center_high, 2),
                    "risk": "较低",
                    "confidence": "75%"
                })
                result["analysis"].append("✅ 存在第三类买点：突破中枢后回调不破")
        
        # ========== 卖点分析 ==========
        
        # 一卖：价格在中枢上方 + 顶背驰
        if current_price > center_high:
            if divergence.get('status') == '顶背驰':
                result["sell_points"].append({
                    "type": "一卖",
                    "name": "第一类卖点",
                    "price": round(center_high * 1.02, 2),
                    "signal": "⚠️ 强烈卖出",
                    "reason": "顶背驰 + 处于中枢上方（背驰段）",
                    "stop_loss": round(center_high, 2),
                    "risk": "较高",
                    "confidence": "80%"
                })
                result["analysis"].append("⚠️ 存在第一类卖点：顶背驰+中枢上方")
        
        # 二卖：反弹不破中枢下沿
        if center_low < current_price < center_high:
            if recent_low < center_low * 0.98:  # 曾经跌破
                result["sell_points"].append({
                    "type": "二卖",
                    "name": "第二类卖点",
                    "price": round(center_high, 2),
                    "signal": "🛑 反弹卖出",
                    "reason": "反弹至中枢下沿遇阻",
                    "stop_loss": round(center_high * 1.05, 2),
                    "risk": "中等",
                    "confidence": "65%"
                })
                result["analysis"].append("⚠️ 存在第二类卖点：反弹至中枢下沿")
        
        # 三卖：跌破中枢后反弹不破
        if current_price < center_low:
            pre_center = klines[-20:-10]
            pre_lows = [k.get('最低', k.get('low', 0)) for k in pre_center]
            
            if min(pre_lows) > center_low:  # 之前在中枢内或上方
                result["sell_points"].append({
                    "type": "三卖",
                    "name": "第三类卖点",
                    "price": round(current_price, 2),
                    "signal": "💔 跌破卖出",
                    "reason": "跌破中枢后反弹不进入",
                    "stop_loss": round(center_low, 2),
                    "risk": "较低",
                    "confidence": "75%"
                })
                result["analysis"].append("⚠️ 存在第三类卖点：跌破中枢后反弹不破")
    
    else:
        # 无中枢时的简化判断
        result["center"] = {"exists": False}
        
        # 底背驰 = 类一买
        if divergence.get('status') == '底背驰':
            result["buy_points"].append({
                "type": "类一买",
                "name": "类第一类买点",
                "price": round(current_price * 0.98, 2),
                "signal": "🔶 关注买入",
                "reason": "底背驰出现",
                "stop_loss": round(current_price * 0.95, 2),
                "risk": "较高",
                "confidence": "60%"
            })
        
        # 顶背驰 = 类一卖
        if divergence.get('status') == '顶背驰':
            result["sell_points"].append({
                "type": "类一卖",
                "name": "类第一类卖点",
                "price": round(current_price * 1.02, 2),
                "signal": "⚠️ 注意卖出",
                "reason": "顶背驰出现",
                "stop_loss": round(current_price * 1.05, 2),
                "risk": "较高",
                "confidence": "60%"
            })
    
    # 确定当前最活跃的买卖点
    if result["buy_points"]:
        # 优先一买 > 三买 > 二买
        priority = {"一买": 3, "三买": 2, "二买": 1, "类一买": 1}
        best = max(result["buy_points"], key=lambda x: priority.get(x["type"], 0))
        result["active_point"] = {
            "type": best["type"],
            "action": "买入",
            "signal": best["signal"],
            "price": best["price"]
        }
        result["recommendation"] = f"关注{best['type']}，目标价 {best['price']}，止损 {best['stop_loss']}"
    
    elif result["sell_points"]:
        priority = {"一卖": 3, "三卖": 2, "二卖": 1, "类一卖": 1}
        best = max(result["sell_points"], key=lambda x: priority.get(x["type"], 0))
        result["active_point"] = {
            "type": best["type"],
            "action": "卖出",
            "signal": best["signal"],
            "price": best["price"]
        }
        result["recommendation"] = f"关注{best['type']}，建议在 {best['price']} 附近减仓"
    
    else:
        result["active_point"] = {"type": "观望", "action": "持有"}
        result["recommendation"] = "无明确买卖点，建议继续观望"
    
    return result

def multi_level_buy_sell_analysis(symbol, levels_data):
    """多级别买卖点综合分析"""
    results = {}
    
    for level_name, klines in levels_data.items():
        if not klines or len(klines) < 30:
            continue
        
        klines = klines[-60:]
        
        # 识别中枢
        center = identify_center(klines)
        
        # 背驰分析
        divergence = identify_divergence(klines)
        
        # 买卖点分析
        bs_result = analyze_buy_sell_points_advanced(klines, center, divergence, level_name)
        results[level_name] = bs_result
    
    # 综合判断
    synthesis = synthesize_buy_sell_points(results)
    
    return {
        "symbol": symbol,
        "levels": results,
        "synthesis": synthesis
    }

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
    
    # 顶背驰
    if recent_high > previous_high:
        vol_ratio = recent_vol / previous_vol if previous_vol > 0 else 1
        if vol_ratio < 1.2:
            return {"status": "顶背驰", "type": "顶背驰"}
    
    # 底背驰
    recent_low = min([k.get('最低', k.get('low', 0)) for k in recent])
    previous_low = min([k.get('最低', k.get('low', 0)) for k in previous])
    
    if recent_low < previous_low:
        vol_ratio = recent_vol / previous_vol if previous_vol > 0 else 1
        if vol_ratio < 1.2:
            return {"status": "底背驰", "type": "底背驰"}
    
    return {"status": "无背驰"}

def synthesize_buy_sell_points(results):
    """综合多级别买卖点"""
    all_buys = []
    all_sells = []
    
    for level, data in results.items():
        if "buy_points" in data:
            all_buys.extend([(level, bp) for bp in data["buy_points"]])
        if "sell_points" in data:
            all_sells.extend([(level, sp) for sp in data["sell_points"]])
    
    synthesis = {
        "total_buy_signals": len(all_buys),
        "total_sell_signals": len(all_sells),
        "buy_signals": [],
        "sell_signals": [],
        "final_recommendation": ""
    }
    
    # 汇总买入信号
    for level, bp in all_buys:
        synthesis["buy_signals"].append({
            "level": level,
            "type": bp["type"],
            "signal": bp["signal"],
            "price": bp["price"],
            "confidence": bp["confidence"]
        })
    
    # 汇总卖出信号
    for level, sp in all_sells:
        synthesis["sell_signals"].append({
            "level": level,
            "type": sp["type"],
            "signal": sp["signal"],
            "price": sp["price"],
            "confidence": sp["confidence"]
        })
    
    # 最终建议
    if len(all_buys) > len(all_sells):
        synthesis["final_recommendation"] = "📈 多级别买入信号共振，建议关注买入机会"
        synthesis["action"] = "买入"
    elif len(all_sells) > len(all_buys):
        synthesis["final_recommendation"] = "⚠️ 多级别卖出信号共振，注意风险"
        synthesis["action"] = "卖出"
    else:
        synthesis["final_recommendation"] = "📊 买卖信号平衡，继续观望"
        synthesis["action"] = "观望"
    
    return synthesis

def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "请输入股票代码"}, ensure_ascii=False))
        return
    
    symbol = sys.argv[1]
    
    # 模拟数据测试（实际使用时替换为真实数据）
    print(json.dumps({
        "symbol": symbol,
        "message": "请提供多级别K线数据进行完整分析",
        "usage": "python multi_level_buy_sell_analysis.py <股票代码> [日线JSON] [30分钟JSON]"
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
