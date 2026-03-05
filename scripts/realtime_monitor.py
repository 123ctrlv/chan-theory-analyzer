#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论实时监控 - 盘中实时买卖点提示
定时检查股票走势，在出现买卖点时发送通知
"""

import json
import sys
import time
import threading
from datetime import datetime, time as dt_time
from collections import defaultdict

# 配置
CONFIG = {
    "check_interval": 300,  # 检查间隔（秒）- 5分钟
    "trading_hours": {  # A股交易时间
        "morning_start": "09:30",
        "morning_end": "11:30",
        "afternoon_start": "13:00",
        "afternoon_end": "15:00"
    },
    "notification": {
        "enabled": False,  # 暂时禁用，需要配置Telegram
        "telegram_token": "",
        "telegram_chat_id": ""
    }
}

def is_trading_time():
    """检查当前是否在交易时间内"""
    now = datetime.now()
    current_time = now.strftime("%H:%M")
    
    # 周末不交易
    if now.weekday() >= 5:
        return False
    
    # 检查交易时间
    morning_start = CONFIG["trading_hours"]["morning_start"]
    morning_end = CONFIG["trading_hours"]["morning_end"]
    afternoon_start = CONFIG["trading_hours"]["afternoon_start"]
    afternoon_end = CONFIG["trading_hours"]["afternoon_end"]
    
    if morning_start <= current_time <= morning_end:
        return True
    if afternoon_start <= current_time <= afternoon_end:
        return True
    
    return False

def get_realtime_data(symbol):
    """获取实时行情"""
    try:
        import akshare as ak
        
        # 处理股票代码
        if symbol.startswith('6'):
            ts_code = 'sh' + symbol
        elif symbol.startswith('0') or symbol.startswith('3'):
            ts_code = 'sz' + symbol
        
        # 获取实时数据
        df = ak.stock_zh_a_spot_em()
        
        # 找到对应股票
        stock = df[df['代码'] == symbol]
        
        if stock.empty:
            return None
        
        row = stock.iloc[0]
        
        return {
            "symbol": symbol,
            "name": row['名称'],
            "price": row['最新价'],
            "change": row['涨跌幅'],
            "volume": row['成交量'],
            "amount": row['成交额'],
            "high": row['最高'],
            "low": row['最低'],
            "open": row['今开'],
            "prev_close": row['昨收'],
            "time": row['时间']
        }
    except Exception as e:
        return {"error": str(e)}

def get_historical_data(symbol, days=60):
    """获取历史数据用于分析"""
    try:
        import akshare as ak
        
        if symbol.startswith('6'):
            ts_code = 'sh' + symbol
        elif symbol.startswith('0') or symbol.startswith('3'):
            ts_code = 'sz' + symbol
        
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                start_date="20250101", adjust="qfq")
        
        return df.tail(days).to_dict(orient='records')
    except Exception as e:
        return {"error": str(e)}

def analyze_realtime(symbol, realtime_data, historical_data):
    """实时分析买卖点"""
    
    if not historical_data or len(historical_data) < 30:
        return {"status": "数据不足", "alerts": []}
    
    klines = historical_data[-60:]  # 最近60天
    
    # 添加实时数据
    if realtime_data:
        klines.append({
            "日期": realtime_data.get("time", datetime.now().strftime("%Y-%m-%d")),
            "开盘": realtime_data.get("open", realtime_data.get("price")),
            "收盘": realtime_data.get("price"),
            "最高": realtime_data.get("high", realtime_data.get("price")),
            "最低": realtime_data.get("low", realtime_data.get("price")),
            "成交量": realtime_data.get("volume", 0)
        })
    
    current_price = realtime_data.get("price") if realtime_data else klines[-1].get('收盘')
    
    # 识别中枢
    center = identify_center(klines)
    
    # 背驰分析
    divergence = identify_divergence(klines)
    
    # 均线
    ma = calculate_ma(klines)
    
    # 检测买卖点
    alerts = []
    
    if center.get('exists'):
        center_high = center.get('high')
        center_low = center.get('low')
        
        # ========== 买点 ==========
        
        # 一买：底背驰 + 中枢下方
        if current_price < center_low:
            if divergence.get('type') == '底背驰':
                alerts.append({
                    "type": "一买",
                    "signal": "🔔 强烈买入",
                    "price": round(center_low * 0.98, 2),
                    "reason": "底背驰+中枢下方",
                    "urgency": "high",
                    "action": "建议立即建仓"
                })
        
        # 二买：回落至中枢上沿
        if center_low <= current_price <= center_high * 1.02:
            alerts.append({
                "type": "二买",
                "signal": "⚡ 回调买入",
                "price": round(current_price, 2),
                "reason": "回落至中枢上沿附近",
                "urgency": "medium",
                "action": "可考虑分批建仓"
            })
        
        # 三买：突破中枢
        if current_price > center_high:
            pre = klines[-20:-10]
            pre_highs = [k.get('最高', 0) for k in pre]
            if max(pre_highs) < center_high:
                alerts.append({
                    "type": "三买",
                    "signal": "🚀 突破买入",
                    "price": round(current_price, 2),
                    "reason": "突破中枢后回调不破",
                    "urgency": "medium",
                    "action": "等待回调后买入"
                })
        
        # ========== 卖点 ==========
        
        # 一卖：顶背驰 + 中枢上方
        if current_price > center_high:
            if divergence.get('type') == '顶背驰':
                alerts.append({
                    "type": "一卖",
                    "signal": "⚠️ 强烈卖出",
                    "price": round(center_high * 1.02, 2),
                    "reason": "顶背驰+中枢上方",
                    "urgency": "high",
                    "action": "建议立即减仓"
                })
        
        # 二卖：反弹至中枢下沿
        if center_high * 0.98 <= current_price <= center_low:
            alerts.append({
                "type": "二卖",
                "signal": "🛑 反弹卖出",
                "price": round(current_price, 2),
                "reason": "反弹至中枢下沿",
                "urgency": "medium",
                "action": "可考虑减仓"
            })
        
        # 三卖：跌破中枢
        if current_price < center_low:
            pre = klines[-20:-10]
            pre_lows = [k.get('最低', 0) for k in pre]
            if min(pre_lows) > center_low:
                alerts.append({
                    "type": "三卖",
                    "signal": "💔 跌破卖出",
                    "price": round(current_price, 2),
                    "reason": "跌破中枢后反弹不进入",
                    "urgency": "high",
                    "action": "建议立即止损"
                })
    
    # 均线系统信号
    ma_signal = check_ma_signal(ma, current_price)
    if ma_signal:
        alerts.append(ma_signal)
    
    return {
        "status": "ok",
        "symbol": symbol,
        "current_price": current_price,
        "change": realtime_data.get("change") if realtime_data else 0,
        "center": center,
        "divergence": divergence,
        "ma": ma,
        "alerts": alerts
    }

def identify_center(klines):
    """识别中枢"""
    if len(klines) < 20:
        return {"exists": False}
    
    start = len(klines) // 3
    end = len(klines) * 2 // 3
    mid = klines[start:end]
    
    highs = [k.get('最高', 0) for k in mid]
    lows = [k.get('最低', 0) for k in mid]
    
    high = min(highs)
    low = max(lows)
    
    if high > low:
        return {
            "exists": True,
            "zone": f"{round(low, 2)}-{round(high, 2)}",
            "high": high,
            "low": low
        }
    return {"exists": False}

def identify_divergence(klines):
    """背驰分析"""
    if len(klines) < 20:
        return {"type": None}
    
    recent = klines[-10:]
    previous = klines[-20:-10]
    
    recent_high = max([k.get('最高', 0) for k in recent])
    previous_high = max([k.get('最高', 0) for k in previous])
    
    recent_vol = sum([k.get('成交量', 0) for k in recent])
    previous_vol = sum([k.get('成交量', 0) for k in previous])
    
    # 顶背驰
    if recent_high > previous_high:
        if previous_vol > 0 and recent_vol < previous_vol * 1.2:
            return {"type": "顶背驰", "signal": "⚠️"}
    
    # 底背驰
    recent_low = min([k.get('最低', 0) for k in recent])
    previous_low = min([k.get('最低', 0) for k in previous])
    
    if recent_low < previous_low:
        if previous_vol > 0 and recent_vol < previous_vol * 1.2:
            return {"type": "底背驰", "signal": "📈"}
    
    return {"type": None}

def calculate_ma(klines):
    """计算均线"""
    closes = [k.get('收盘', 0) for k in klines]
    
    ma5 = sum(closes[-5:]) / 5 if len(closes) >= 5 else 0
    ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else 0
    ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else 0
    
    return {
        "MA5": round(ma5, 2),
        "MA10": round(ma10, 2),
        "MA20": round(ma20, 2)
    }

def check_ma_signal(ma, current_price):
    """均线系统信号"""
    if not ma.get("MA5"):
        return None
    
    # 均线多头排列
    if ma["MA5"] > ma["MA10"] > ma["MA20"]:
        return {
            "type": "均线金叉",
            "signal": "📈 均线多头",
            "reason": "MA5>MA10>MA20，多头排列",
            "urgency": "low",
            "action": "持有待涨"
        }
    
    # 均线空头排列
    if ma["MA5"] < ma["MA10"] < ma["MA20"]:
        return {
            "type": "均线死叉",
            "signal": "📉 均线空头",
            "reason": "MA5<MA10<MA20，空头排列",
            "urgency": "low",
            "action": "观望为主"
        }
    
    return None

def format_alert_message(analysis):
    """格式化告警消息"""
    symbol = analysis["symbol"]
    price = analysis["current_price"]
    change = analysis.get("change", 0)
    
    msg = []
    msg.append(f"📊 实时监控 - {symbol}")
    msg.append(f"💰 当前价格: {price} ({change:+.2f}%)")
    msg.append("")
    
    # 中枢
    center = analysis.get("center", {})
    if center.get("exists"):
        msg.append(f"📍 中枢区间: {center['zone']}")
    else:
        msg.append("📍 中枢: 无")
    
    # 背驰
    div = analysis.get("divergence", {})
    if div.get("type"):
        msg.append(f"⚡ 背驰状态: {div['type']}")
    
    # 均线
    ma = analysis.get("ma", {})
    if ma.get("MA5"):
        msg.append(f"📈 均线: MA5={ma['MA5']} MA10={ma['MA10']} MA20={ma['MA20']}")
    
    msg.append("")
    msg.append("🚨 实时信号:")
    
    alerts = analysis.get("alerts", [])
    if not alerts:
        msg.append("  无明确信号，继续观望")
    else:
        for alert in alerts:
            urgency_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(alert.get("urgency", "low"), "⚪")
            msg.append(f"  {urgency_emoji} {alert['signal']}")
            msg.append(f"      类型: {alert['type']} | 操作: {alert['action']}")
    
    return '\n'.join(msg)

def send_notification(message):
    """发送通知"""
    if not CONFIG["notification"]["enabled"]:
        print(message)
        return
    
    # Telegram通知
    try:
        import requests
        token = CONFIG["notification"]["telegram_token"]
        chat_id = CONFIG["notification"]["telegram_chat_id"]
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {"chat_id": chat_id, "text": message}
        
        requests.post(url, json=data, timeout=10)
    except Exception as e:
        print(f"通知发送失败: {e}")

def monitor_stock(symbol, continuous=False):
    """监控单只股票"""
    print(f"\n{'='*60}")
    print(f"开始监控: {symbol}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # 检查是否交易时间
    if not is_trading_time():
        print("⚠️ 当前非交易时间，仅进行数据分析")
    
    # 获取数据
    print(f"\n获取实时数据...")
    realtime = get_realtime_data(symbol)
    
    print(f"获取历史数据...")
    historical = get_historical_data(symbol, 60)
    
    if isinstance(historical, dict) and "error" in historical:
        print(f"❌ 获取数据失败: {historical['error']}")
        return
    
    # 分析
    print(f"\n分析走势...")
    analysis = analyze_realtime(symbol, realtime, historical)
    
    # 输出结果
    message = format_alert_message(analysis)
    print(message)
    
    # 发送通知
    alerts = analysis.get("alerts", [])
    if alerts:
        send_notification(message)
    
    return analysis

def continuous_monitor(symbols, interval=300):
    """持续监控多只股票"""
    print(f"\n启动持续监控模式")
    print(f"监控股票: {', '.join(symbols)}")
    print(f"检查间隔: {interval}秒")
    print(f"按 Ctrl+C 停止")
    print(f"{'='*60}")
    
    alert_history = defaultdict(list)  # 避免重复告警
    
    try:
        while True:
            # 检查是否交易时间
            if is_trading_time():
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 检查交易信号...")
                
                for symbol in symbols:
                    analysis = monitor_stock(symbol)
                    
                    # 检查新信号
                    if analysis and analysis.get("alerts"):
                        for alert in analysis["alerts"]:
                            alert_key = f"{symbol}_{alert['type']}"
                            
                            # 5分钟内不重复告警
                            recent_alerts = alert_history[alert_key]
                            now = datetime.now()
                            
                            if not recent_alerts or (now - recent_alerts[-1]).seconds > 300:
                                send_notification(format_alert_message(analysis))
                                alert_history[alert_key].append(now)
            
            # 等待下次检查
            time.sleep(interval)
    
    except KeyboardInterrupt:
        print("\n\n监控已停止")

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python realtime_monitor.py <symbol>           # 单次检查")
        print("  python realtime_monitor.py <symbol> -c        # 持续监控")
        print("  python realtime_monitor.py <symbol1> <symbol2> # 多只股票")
        print("  python realtime_monitor.py <symbol> -c -i 60  # 持续监控，60秒间隔")
        return
    
    # 解析参数
    symbols = []
    continuous = False
    interval = CONFIG["check_interval"]
    
    for arg in sys.argv[1:]:
        if arg == "-c":
            continuous = True
        elif arg == "-i" and len(sys.argv) > sys.argv.index(arg) + 1:
            interval = int(sys.argv[sys.argv.index(arg) + 1])
        elif not arg.startswith("-"):
            symbols.append(arg)
    
    if not symbols:
        print("请输入股票代码")
        return
    
    if continuous:
        continuous_monitor(symbols, interval)
    else:
        for symbol in symbols:
            monitor_stock(symbol)

if __name__ == "__main__":
    main()
