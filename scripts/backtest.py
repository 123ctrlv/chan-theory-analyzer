#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论买卖点历史回测系统
测试历史买卖点的准确率和收益率
"""

import json
import sys
from datetime import datetime, timedelta
from collections import defaultdict

def get_historical_data(symbol, days=250):
    """获取历史数据用于回测"""
    try:
        import akshare as ak
        
        # 处理股票代码
        if symbol.startswith('6'):
            ts_code = 'sh' + symbol
        elif symbol.startswith('0') or symbol.startswith('3'):
            ts_code = 'sz' + symbol
        
        # 获取日线数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days+30)).strftime('%Y%m%d')
        
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                start_date=start_date, end_date=end_date, adjust="qfq")
        
        return df.to_dict(orient='records')
    except Exception as e:
        return {"error": str(e)}

def detect_buy_sells_on_bar(klines, idx):
    """检测特定日期的买卖点信号"""
    if idx < 30:
        return {"buy": None, "sell": None}
    
    # 取足够的历史K线
    history = klines[max(0, idx-60):idx+1]
    
    if len(history) < 30:
        return {"buy": None, "sell": None}
    
    current = history[-1]
    current_price = current.get('收盘', 0)
    
    # 识别中枢
    center = identify_center(history)
    
    # 背驰分析
    divergence = identify_divergence(history)
    
    signals = {"buy": [], "sell": []}
    
    if center.get('exists'):
        center_high = center.get('high')
        center_low = center.get('low')
        
        # 买点判断
        if current_price < center_low:
            if divergence.get('type') == '底背驰':
                signals["buy"].append("一买")
        
        if center_low < current_price < center_high:
            signals["buy"].append("二买")
        
        if current_price > center_high:
            # 检查是否从下方突破
            pre = history[-20:-10]
            pre_highs = [k.get('最高', 0) for k in pre]
            if max(pre_highs) < center_high:
                signals["buy"].append("三买")
        
        # 卖点判断
        if current_price > center_high:
            if divergence.get('type') == '顶背驰':
                signals["sell"].append("一卖")
        
        if center_low < current_price < center_high:
            signals["sell"].append("二卖")
        
        if current_price < center_low:
            pre = history[-20:-10]
            pre_lows = [k.get('最低', 0) for k in pre]
            if min(pre_lows) > center_low:
                signals["sell"].append("三卖")
    
    return signals

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
        return {"exists": True, "high": high, "low": low}
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
            return {"type": "顶背驰"}
    
    # 底背驰
    recent_low = min([k.get('最低', 0) for k in recent])
    previous_low = min([k.get('最低', 0) for k in previous])
    
    if recent_low < previous_low:
        if previous_vol > 0 and recent_vol < previous_vol * 1.2:
            return {"type": "底背驰"}
    
    return {"type": None}

def run_backtest(symbol, data, holding_days=5, profit_target=0.05, loss_stop=0.03):
    """
    运行回测
    
    参数:
    - holding_days: 持有天数
    - profit_target: 止盈目标 (5%)
    - loss_stop: 止损线 (3%)
    """
    
    trades = []
    positions = []
    
    # 遍历每个交易日
    for idx in range(30, len(data) - holding_days):
        current = data[idx]
        date = current.get('日期', '')
        price = current.get('收盘', 0)
        
        # 检测买卖点
        signals = detect_buy_sells_on_bar(data, idx)
        
        # 买入信号
        if signals["buy"] and not positions:
            # 开仓
            position = {
                "entry_date": date,
                "entry_price": price,
                "type": signals["buy"][0],  # 第一个买入信号类型
                "stop_loss": price * (1 - loss_stop),
                "take_profit": price * (1 + profit_target)
            }
            positions.append(position)
        
        # 检查持仓
        for pos in positions[:]:
            # 计算当前收益
            current_price = data[min(idx + 1, len(data) - 1)].get('收盘', 0)
            profit_ratio = (current_price - pos["entry_price"]) / pos["entry_price"]
            
            # 卖出条件
            should_sell = False
            sell_reason = ""
            
            # 1. 达到止盈
            if profit_ratio >= profit_target:
                should_sell = True
                sell_reason = "止盈"
            
            # 2. 达到止损
            elif profit_ratio <= -loss_stop:
                should_sell = True
                sell_reason = "止损"
            
            # 3. 达到持有天数
            elif idx - data.index([d for d in data if d.get('日期') == pos["entry_date"]][0]) >= holding_days:
                should_sell = True
                sell_reason = "到期平仓"
            
            # 4. 出现卖出信号
            future_signals = detect_buy_sells_on_bar(data, idx + 1)
            if future_signals["sell"]:
                should_sell = True
                sell_reason = f"卖出信号-{future_signals['sell'][0]}"
            
            if should_sell:
                # 平仓
                trade = {
                    "entry_date": pos["entry_date"],
                    "exit_date": date,
                    "entry_price": pos["entry_price"],
                    "exit_price": current_price,
                    "type": pos["type"],
                    "profit": profit_ratio * 100,
                    "result": "盈利" if profit_ratio > 0 else "亏损",
                    "sell_reason": sell_reason
                }
                trades.append(trade)
                positions.remove(pos)
    
    return trades

def calculate_metrics(trades):
    """计算回测指标"""
    if not trades:
        return {"error": "无交易记录"}
    
    total = len(trades)
    wins = sum(1 for t in trades if t["profit"] > 0)
    losses = total - wins
    
    win_rate = wins / total * 100 if total > 0 else 0
    
    profits = [t["profit"] for t in trades if t["profit"] > 0]
    losses_abs = [abs(t["profit"]) for t in trades if t["profit"] < 0]
    
    avg_profit = sum(profits) / len(profits) if profits else 0
    avg_loss = sum(losses_abs) / len(losses_abs) if losses_abs else 0
    
    total_profit = sum(t["profit"] for t in trades)
    
    # 盈亏比
    profit_loss_ratio = avg_profit / avg_loss if avg_loss > 0 else 0
    
    # 各类买卖点统计
    by_type = defaultdict(lambda: {"total": 0, "wins": 0, "total_profit": 0})
    for t in trades:
        by_type[t["type"]]["total"] += 1
        if t["profit"] > 0:
            by_type[t["type"]]["wins"] += 1
        by_type[t["type"]]["total_profit"] += t["profit"]
    
    type_stats = {}
    for tp, stats in by_type.items():
        type_stats[tp] = {
            "交易次数": stats["total"],
            "胜利次数": stats["wins"],
            "胜率": f"{stats['wins']/stats['total']*100:.1f}%" if stats["total"] > 0 else "0%",
            "总收益": f"{stats['total_profit']:.2f}%"
        }
    
    return {
        "总交易次数": total,
        "盈利次数": wins,
        "亏损次数": losses,
        "胜率": f"{win_rate:.1f}%",
        "平均盈利": f"{avg_profit:.2f}%",
        "平均亏损": f"-{avg_loss:.2f}%",
        "盈亏比": f"{profit_loss_ratio:.2f}",
        "总收益": f"{total_profit:.2f}%",
        "各类买卖点统计": type_stats
    }

def generate_report(symbol, trades, metrics):
    """生成回测报告"""
    
    report = []
    report.append("=" * 70)
    report.append(f"📊 缠论买卖点历史回测报告 - {symbol}")
    report.append("=" * 70)
    report.append("")
    
    # 总体统计
    report.append("【总体统计】")
    report.append(f"  总交易次数: {metrics.get('总交易次数', 0)}")
    report.append(f"  盈利次数:   {metrics.get('盈利次数', 0)}")
    report.append(f"  亏损次数:   {metrics.get('亏损次数', 0)}")
    report.append(f"  胜率:       {metrics.get('胜率', '0%')}")
    report.append(f"  总收益:     {metrics.get('总收益', '0%')}")
    report.append("")
    
    # 盈亏分析
    report.append("【盈亏分析】")
    report.append(f"  平均盈利:   {metrics.get('平均盈利', '0%')}")
    report.append(f"  平均亏损:   {metrics.get('平均亏损', '0%')}")
    report.append(f"  盈亏比:     {metrics.get('盈亏比', '0')}")
    report.append("")
    
    # 各类买卖点统计
    report.append("【各类买卖点统计】")
    type_stats = metrics.get('各类买卖点统计', {})
    for tp, stats in type_stats.items():
        report.append(f"  {tp}:")
        report.append(f"    交易次数: {stats['交易次数']}")
        report.append(f"    胜率:     {stats['胜率']}")
        report.append(f"    总收益:   {stats['总收益']}")
    report.append("")
    
    # 详细交易记录
    report.append("【最近10笔交易】")
    for i, trade in enumerate(trades[-10:], 1):
        report.append(f"  {i}. {trade['entry_date']} 买入 {trade['type']} @ {trade['entry_price']:.2f} → "
                     f"{trade['exit_date']} 卖出 @ {trade['exit_price']:.2f} | "
                     f"{trade['result']} {trade['profit']:.2f}%")
    report.append("")
    
    # 结论
    report.append("【结论】")
    win_rate = float(metrics.get('胜率', '0%').replace('%', ''))
    pl_ratio = float(metrics.get('盈亏比', '0'))
    
    if win_rate >= 60 and pl_ratio >= 1.5:
        conclusion = "✅ 该买卖点策略效果良好，值得使用"
    elif win_rate >= 50:
        conclusion = "⚠️ 该买卖点策略效果一般，建议优化"
    else:
        conclusion = "❌ 该买卖点策略效果较差，建议重新研究"
    
    report.append(f"  {conclusion}")
    report.append("")
    report.append("=" * 70)
    
    return '\n'.join(report)

def main():
    if len(sys.argv) < 2:
        print("Usage: python backtest.py <symbol> [days] [holding_days]")
        print("  symbol: 股票代码")
        print("  days: 回测天数 (默认250)")
        print("  holding_days: 持有天数 (默认5)")
        return
    
    symbol = sys.argv[1]
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 250
    holding_days = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    
    print(f"正在获取 {symbol} 历史数据...")
    
    # 获取历史数据
    data = get_historical_data(symbol, days)
    
    if isinstance(data, dict) and "error" in data:
        print(f"获取数据失败: {data['error']}")
        print("\n模拟回测示例:")
        # 使用模拟数据进行演示
        data = simulate_data()
    
    print(f"获取到 {len(data) if isinstance(data, list) else 0} 条数据")
    
    # 运行回测
    print(f"\n运行回测 (持有天数: {holding_days})...")
    trades = run_backtest(symbol, data, holding_days)
    
    # 计算指标
    metrics = calculate_metrics(trades)
    
    # 生成报告
    report = generate_report(symbol, trades, metrics)
    print(report)
    
    # 保存详细结果
    output_file = f"backtest_{symbol}.json"
    result = {
        "symbol": symbol,
        "metrics": metrics,
        "trades": trades[-50:]  # 保存最近50笔
    }
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n详细数据已保存到: {output_file}")

def simulate_data():
    """生成模拟数据进行演示"""
    import random
    
    data = []
    base_price = 20.0
    
    for i in range(250):
        date = f"2025-{i//30+1:02d}-{(i%30)+1:02d}"
        change = random.uniform(-0.03, 0.035)
        close = base_price * (1 + change)
        open_p = close * random.uniform(0.98, 1.02)
        high = max(open_p, close) * random.uniform(1.0, 1.02)
        low = min(open_p, close) * random.uniform(0.98, 1.0)
        vol = random.randint(1000000, 5000000)
        
        data.append({
            "日期": date,
            "开盘": round(open_p, 2),
            "收盘": round(close, 2),
            "最高": round(high, 2),
            "最低": round(low, 2),
            "成交量": vol
        })
        
        base_price = close
    
    return data

if __name__ == "__main__":
    main()
