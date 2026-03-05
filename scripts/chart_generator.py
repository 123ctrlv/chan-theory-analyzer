#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
缠论自动画图功能
生成带买卖点标注的K线图表
"""

import json
import sys
import os

def generate_chart_html(klines, analysis_result, symbol):
    """生成HTML图表"""
    
    # 转换数据格式
    ohlc = []
    volumes = []
    
    for k in klines:
        dt = k.get('日期', k.get('time', ''))
        o = k.get('开盘', k.get('open', 0))
        h = k.get('最高', k.get('high', 0))
        l = k.get('最低', k.get('low', 0))
        c = k.get('收盘', k.get('close', 0))
        v = k.get('成交量', k.get('vol', 0))
        
        ohlc.append([dt, o, h, l, c])
        volumes.append([dt, v])
    
    # 提取买卖点
    buy_points = analysis_result.get('buy_points', [])
    sell_points = analysis_result.get('sell_points', [])
    
    # 构建标注
    annotations = []
    
    for bp in buy_points:
        annotations.append({
            "type": "buy",
            "point_type": bp.get('type', ''),
            "price": bp.get('price', 0),
            "signal": bp.get('signal', '')
        })
    
    for sp in sell_points:
        annotations.append({
            "type": "sell",
            "point_type": sp.get('type', ''),
            "price": sp.get('price', 0),
            "signal": sp.get('signal', '')
        })
    
    # 中枢区间
    center = analysis_result.get('center', {})
    if center.get('exists'):
        annotations.append({
            "type": "center",
            "zone": center.get('zone', ''),
            "high": center.get('high', 0),
            "low": center.get('low', 0)
        })
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>缠论分析 - {symbol}</title>
    <script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.0.0/dist/lightweight-charts.standalone.production.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #fff; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; }}
        .summary {{ background: #16213e; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .buy {{ color: #00ff88; }}
        .sell {{ color: #ff4444; }}
        .center {{ color: #ffd700; }}
        #chart {{ height: 500px; }}
        #volume {{ height: 150px; }}
        .legend {{ display: flex; gap: 20px; margin: 10px 0; }}
        .legend-item {{ display: flex; align-items: center; gap: 5px; }}
        .dot {{ width: 12px; height: 12px; border-radius: 50%; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📈 缠论分析 - {symbol}</h1>
        
        <div class="summary">
            <h3>分析摘要</h3>
            <p><strong>当前价格:</strong> {analysis_result.get('current_price', 'N/A')}</p>
            <p><strong>建议:</strong> {analysis_result.get('recommendation', '观望')}</p>
        </div>
        
        <div class="legend">
            <div class="legend-item"><span class="dot" style="background: #00ff88;"></span> 买点</div>
            <div class="legend-item"><span class="dot" style="background: #ff4444;"></span> 卖点</div>
            <div class="legend-item"><span class="dot" style="background: #ffd700;"></span> 中枢</div>
        </div>
        
        <div id="chart"></div>
        <div id="volume"></div>
        
        <div class="summary">
            <h3>买卖点详情</h3>
            <h4 class="buy">买入信号 ({len(buy_points)}个)</h4>
            {generate_points_html(buy_points, 'buy')}
            <h4 class="sell">卖出信号 ({len(sell_points)}个)</h4>
            {generate_points_html(sell_points, 'sell')}
        </div>
    </div>
    
    <script>
        // K线数据
        const ohlcData = {json.dumps(ohlc[-60:])};
        const volumeData = {json.dumps(volumes[-60:])};
        
        // 解析数据
        const candles = ohlcData.map(d => {{
            return {{
                time: d[0],
                open: d[1],
                high: d[2],
                low: d[3],
                close: d[4]
            }};
        }});
        
        const volumes_ = volumeData.map(d => {{
            return {{
                time: d[0],
                value: d[1],
                color: d[1] >= ohlcData.find(x => x[0] === d[0])[4] ? '#00ff88' : '#ff4444'
            }};
        }});
        
        // 创建图表
        const chart = LightweightCharts.createChart(document.getElementById('chart'), {{
            layout: {{ background: {{ type: 'solid', color: '#1a1a2e' }}, textColor: '#fff' }},
            grid: {{ vertLines: {{ color: '#2a2a4e' }}, horzLines: {{ color: '#2a2a4e' }} }},
            width: document.getElementById('chart').clientWidth,
            height: 500
        }});
        
        const candleSeries = chart.addCandlestickSeries({{
            upColor: '#00ff88',
            downColor: '#ff4444',
            borderUpColor: '#00ff88',
            borderDownColor: '#ff4444',
            wickUpColor: '#00ff88',
            wickDownColor: '#ff4444'
        }});
        
        candleSeries.setData(candles);
        
        // 均线
        const ma5 = candles.map((c, i) => {{
            if (i < 4) return {{ time: c.time, value: null }};
            const sum = candles.slice(i-4, i+1).reduce((a, b) => a + b.close, 0);
            return {{ time: c.time, value: sum / 5 }};
        }}).filter(d => d.value);
        
        const ma10 = candles.map((c, i) => {{
            if (i < 9) return {{ time: c.time, value: null }};
            const sum = candles.slice(i-9, i+1).reduce((a, b) => a + b.close, 0);
            return {{ time: c.time, value: sum / 10 }};
        }}).filter(d => d.value);
        
        const ma20 = candles.map((c, i) => {{
            if (i < 19) return {{ time: c.time, value: null }};
            const sum = candles.slice(i-19, i+1).reduce((a, b) => a + b.close, 0);
            return {{ time: c.time, value: sum / 20 }};
        }}).filter(d => d.value);
        
        chart.addLineSeries({{ color: '#00d4ff', lineWidth: 1 }}).setData(ma5);
        chart.addLineSeries({{ color: '#ffd700', lineWidth: 1 }}).setData(ma10);
        chart.addLineSeries({{ color: '#ff00ff', lineWidth: 1 }}).setData(ma20);
        
        // 成交量
        const volumeChart = LightweightCharts.createChart(document.getElementById('volume'), {{
            layout: {{ background: {{ type: 'solid', color: '#1a1a2e' }}, textColor: '#fff' }},
            grid: {{ vertLines: {{ color: '#2a2a4e' }}, horzLines: {{ color: '#2a2a4e' }} }},
            width: document.getElementById('volume').clientWidth,
            height: 150
        }});
        
        volumeChart.addHistogramSeries({{
            color: '#26a69a',
            priceFormat: {{ type: 'volume' }},
            priceScaleId: '',
        }}).setData(volumes_);
        
        volumeChart.priceScale().applyOptions({{
            scaleMargins: {{ top: 0.8, bottom: 0 }}
        }});
    </script>
</body>
</html>"""
    
    return html

def generate_points_html(points, point_type):
    """生成买卖点HTML"""
    if not points:
        return "<p>无</p>"
    
    html = "<ul>"
    for p in points:
        html += f"<li>{p.get('signal', '')} - {p.get('type', '')} - 价格: {p.get('price', 'N/A')} - 置信度: {p.get('confidence', 'N/A')}</li>"
    html += "</ul>"
    return html

def create_simple_text_chart(klines, analysis_result, symbol):
    """创建简单的文本图表（无需JS）"""
    
    if not klines:
        return "无数据"
    
    # 取最近30根K线
    recent = klines[-30:]
    
    # 找到最高最低用于缩放
    highs = [k.get('最高', k.get('high', 0)) for k in recent]
    lows = [k.get('最低', k.get('low', 0)) for k in recent]
    
    max_price = max(highs) * 1.01
    min_price = min(lows) * 0.99
    
    def price_to_row(price):
        """价格转行号(0-20)"""
        if max_price == min_price:
            return 10
        ratio = (price - min_price) / (max_price - min_price)
        return int(20 - ratio * 20)
    
    # 构建图形
    lines = [[] for _ in range(21)]
    
    for k in recent:
        dt = str(k.get('日期', k.get('time', '')))[-5:]
        o = k.get('开盘', k.get('open', 0))
        c = k.get('收盘', k.get('close', 0))
        h = k.get('最高', k.get('high', 0))
        l = k.get('最低', k.get('low', 0))
        
        o_row = price_to_row(o)
        c_row = price_to_row(c)
        h_row = price_to_row(h)
        l_row = price_to_row(l)
        
        # 填充K线实体
        for r in range(min(o_row, c_row), max(o_row, c_row) + 1):
            if 0 <= r <= 20:
                lines[r].append('█' if c >= o else '▓')
        
        # 上下影线
        for r in range(h_row, l_row + 1):
            if 0 <= r <= 20 and r < min(o_row, c_row) or r > max(o_row, c_row):
                lines[r].append('│')
    
    # 构建输出
    output = []
    output.append(f"\n{'='*60}")
    output.append(f"📈 缠论K线图 - {symbol}")
    output.append(f"当前价格: {analysis_result.get('current_price', 'N/A')}")
    output.append(f"建议: {analysis_result.get('recommendation', '观望')}")
    output.append(f"{'='*60}")
    
    # 价格轴
    price_step = (max_price - min_price) / 20
    
    for i, line in enumerate(lines):
        price = max_price - i * price_step
        bar = ''.join(line) if line else '·'
        output.append(f"{price:>8.2f} │{bar:<31}│")
    
    output.append(f"{'='*60}")
    
    # 买卖点标注
    buy_points = analysis_result.get('buy_points', [])
    sell_points = analysis_result.get('sell_points', [])
    
    if buy_points:
        output.append("\n🟢 买入信号:")
        for bp in buy_points:
            output.append(f"  {bp.get('signal', '')} {bp.get('type', '')} @ {bp.get('price', 'N/A')}")
    
    if sell_points:
        output.append("\n🔴 卖出信号:")
        for sp in sell_points:
            output.append(f"  {sp.get('signal', '')} {sp.get('type', '')} @ {sp.get('price', 'N/A')}")
    
    return '\n'.join(output)

def main():
    if len(sys.argv) < 2:
        print("Usage: python chart_generator.py <symbol> [output_type]")
        print("  output_type: html (default) or text")
        return
    
    symbol = sys.argv[1]
    output_type = sys.argv[2] if len(sys.argv) > 2 else 'text'
    
    # 模拟分析结果
    analysis_result = {
        "current_price": 21.50,
        "recommendation": "关注二买机会",
        "buy_points": [
            {"type": "二买", "price": 20.80, "signal": "⚡ 回调买入", "confidence": "70%"},
            {"type": "三买", "price": 22.00, "signal": "🚀 突破买入", "confidence": "75%"}
        ],
        "sell_points": [],
        "center": {
            "exists": True,
            "zone": "20.50-21.20",
            "high": 21.20,
            "low": 20.50
        }
    }
    
    if output_type == 'html':
        # 生成HTML（需要真实数据）
        html = generate_chart_html([], analysis_result, symbol)
        output_file = f"chan_chart_{symbol}.html"
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"HTML图表已生成: {output_file}")
    else:
        # 文本图表
        chart = create_simple_text_chart([], analysis_result, symbol)
        print(chart)

if __name__ == "__main__":
    main()
