/**
 * 缠论技术分析技能
 * Chan Theory Technical Analysis Skill
 * 
 * 功能：
 * - 分型识别（顶分型/底分型）
 * - 笔分析（向上笔/向下笔）
 * - 线段分析
 * - 中枢识别
 * - 背驰判断
 * - 三类买卖点
 * 
 * 集成：调用 Python 脚本进行专业分析
 */

const { exec } = require('child_process');
const path = require('path');

const SCRIPT_DIR = path.join(__dirname, 'scripts');

/**
 * 调用 Python 脚本进行专业分析
 * @param {string} symbol - 股票代码
 * @returns {Promise<Object>} 分析结果
 */
async function callPythonScript(symbol) {
    return new Promise((resolve, reject) => {
        const scriptPath = path.join(SCRIPT_DIR, 'enhanced_analyze.py');
        
        exec(`python "${scriptPath}" ${symbol}`, 
            { timeout: 60000 },
            (error, stdout, stderr) => {
                if (error) {
                    console.error('Python脚本错误:', stderr);
                    reject(error);
                    return;
                }
                try {
                    const result = JSON.parse(stdout);
                    resolve(result);
                } catch (e) {
                    console.error('JSON解析错误:', stdout);
                    reject(e);
                }
            });
    });
}

/**
 * 获取股票K线数据
 * @param {string} symbol - 股票代码
 * @param {string} period - 周期（日线/30分钟/5分钟）
 * @returns {Promise<Object>} K线数据
 */
async function getKlineData(symbol, period = 'daily') {
    return new Promise((resolve, reject) => {
        const script = `
import akshare as ak
import json

symbol = "${symbol}"
try:
    if symbol.startswith('6'):
        symbol = 'sh' + symbol
    elif symbol.startswith('0') or symbol.startswith('3'):
        symbol = 'sz' + symbol
    
    df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date="20240101", adjust="qfq")
    df = df.tail(100)
    
    result = {
        "code": symbol,
        "data": df.to_dict(orient='records')
    }
    print(json.dumps(result, ensure_ascii=False))
except Exception as e:
    print(json.dumps({"error": str(e)}))
`;
        exec(`python -c "${script.replace(/"/g, '\\"').replace(/\n/g, ';')}"`, 
            { timeout: 30000 },
            (error, stdout, stderr) => {
                if (error) {
                    reject(error);
                    return;
                }
                try {
                    resolve(JSON.parse(stdout));
                } catch (e) {
                    reject(e);
                }
            });
    });
}

/**
 * 识别分型
 * @param {Array} klines - K线数据
 * @returns {Object} 分型结果
 */
function identifyFraction(klines) {
    if (klines.length < 3) {
        return { type: '无', confidence: 0 };
    }
    
    const highs = klines.map(k => k['最高']);
    const lows = klines.map(k => k['最低']);
    
    // 顶分型：中间K线最高
    let topFraction = false;
    for (let i = 1; i < klines.length - 1; i++) {
        if (highs[i] > highs[i-1] && highs[i] > highs[i+1]) {
            topFraction = true;
            break;
        }
    }
    
    // 底分型：中间K线最低
    let bottomFraction = false;
    for (let i = 1; i < klines.length - 1; i++) {
        if (lows[i] < lows[i-1] && lows[i] < lows[i+1]) {
            bottomFraction = true;
            break;
        }
    }
    
    if (topFraction && !bottomFraction) {
        return { type: '顶分型', confidence: 0.7 };
    } else if (bottomFraction && !topFraction) {
        return { type: '底分型', confidence: 0.7 };
    } else if (topFraction && bottomFraction) {
        return { type: '顶底分型', confidence: 0.5 };
    }
    
    return { type: '无', confidence: 0 };
}

/**
 * 判断笔的方向
 * @param {Object} fraction - 分型结果
 * @returns {string} 笔方向
 */
function getBrushDirection(fraction) {
    if (fraction.type === '底分型') {
        return '向上笔';
    } else if (fraction.type === '顶分型') {
        return '向下笔';
    }
    return '不确定';
}

/**
 * 简单的中枢识别
 * @param {Array} klines - K线数据
 * @returns {Object} 中枢信息
 */
function identifyCenter(klines) {
    if (klines.length < 10) {
        return { exists: false };
    }
    
    // 取中间段的数据计算
    const midStart = Math.floor(klines.length * 0.3);
    const midEnd = Math.floor(klines.length * 0.7);
    const midData = klines.slice(midStart, midEnd);
    
    const highs = midData.map(k => k['最高']);
    const lows = midData.map(k => k['最低']);
    
    const centerHigh = Math.min(...highs);
    const centerLow = Math.max(...lows);
    
    if (centerHigh > centerLow) {
        return {
            exists: true,
            high: centerHigh,
            low: centerLow,
            range: centerHigh - centerLow
        };
    }
    
    return { exists: false };
}

/**
 * 背驰判断（简化版）
 * @param {Array} klines - K线数据
 * @returns {Object} 背驰分析
 */
function identifyDivergence(klines) {
    if (klines.length < 20) {
        return { status: '数据不足' };
    }
    
    const recent = klines.slice(-10);
    const previous = klines.slice(-20, -10);
    
    const recentHigh = Math.max(...recent.map(k => k['最高']));
    const previousHigh = Math.max(...previous.map(k => k['最高']));
    
    const recentVolume = recent.reduce((sum, k) => sum + (k['成交量'] || 0), 0);
    const previousVolume = previous.reduce((sum, k) => sum + (k['成交量'] || 0), 0);
    
    // 价格创新高但成交量不配合
    if (recentHigh > previousHigh && recentVolume < previousVolume * 1.2) {
        return {
            status: '可能背驰',
            type: '顶背驰',
            reason: '价格创新高但成交量未放大'
        };
    }
    
    // 价格创新低但成交量不配合
    const recentLow = Math.min(...recent.map(k => k['最低']));
    const previousLow = Math.min(...previous.map(k => k['最低']));
    
    if (recentLow < previousLow && recentVolume < previousVolume * 1.2) {
        return {
            status: '可能背驰',
            type: '底背驰',
            reason: '价格创新低但成交量未放大'
        };
    }
    
    return { status: '未背驰', reason: '量价配合正常' };
}

/**
 * 生成买卖点建议
 * @param {Object} center - 中枢
 * @param {Object} fraction - 分型
 * @param {Object} divergence - 背驰
 * @param {number} currentPrice - 当前价格
 * @returns {Object} 买卖点
 */
function generateSignals(center, fraction, divergence, currentPrice) {
    const signals = [];
    
    // 一买：底背驰 + 底分型
    if (divergence.type === '底背驰' && fraction.type === '底分型') {
        signals.push({
            type: '一买',
            action: '买入',
            confidence: '高',
            reason: '底背驰确认，底分型形成'
        });
    }
    
    // 二买：回落不破中枢下沿
    if (center.exists && currentPrice > center.low * 0.95) {
        signals.push({
            type: '二买',
            action: '买入',
            confidence: '中',
            reason: '回落至中枢上沿附近，可考虑买入'
        });
    }
    
    // 三买：突破中枢后回落不破
    if (center.exists && currentPrice > center.high) {
        signals.push({
            type: '三买',
            action: '观望',
            confidence: '中',
            reason: '已突破中枢，等待回落确认'
        });
    }
    
    // 顶背驰警告
    if (divergence.type === '顶背驰') {
        signals.push({
            type: '风险提示',
            action: '卖出',
            confidence: '高',
            reason: '顶背驰出现，注意风险'
        });
    }
    
    return signals;
}

/**
 * 主分析函数
 * @param {Object} params - 分析参数
 * @returns {Object} 分析结果
 */
async function analyze(params) {
    const { symbol, period = 'daily' } = params;
    
    try {
        // 优先尝试调用 Python 脚本进行专业分析
        console.log('正在调用 Python 脚本分析 ' + symbol + '...');
        
        try {
            const pyResult = await callPythonScript(symbol);
            
            if (pyResult && !pyResult.error) {
                // 转换为友好格式
                return formatAnalysisResult(pyResult);
            }
        } catch (pyError) {
            console.log('Python脚本失败，回退到JS分析:', pyError.message);
        }
        
        // 回退到 JavaScript 简单分析
        console.log('使用 JavaScript 简单分析...');
        const klineData = await getKlineData(symbol, period);
        
        if (klineData.error) {
            return { error: klineData.error };
        }
        
        const klines = klineData.data || [];
        
        if (klines.length < 20) {
            return { error: '数据不足，无法分析' };
        }
        
        // 基础分析
        const currentPrice = klines[klines.length - 1]['收盘'] || klines[klines.length - 1]['close'];
        const fraction = identifyFraction(klines);
        const brushDirection = getBrushDirection(fraction);
        const center = identifyCenter(klines);
        const divergence = identifyDivergence(klines);
        
        // 生成买卖点
        const signals = generateSignals(center, fraction, divergence, currentPrice);
        
        // 构建结果
        const result = {
            symbol: symbol,
            current_price: currentPrice,
            analysis: {
                fraction: fraction,
                brush_direction: brushDirection,
                center: center,
                divergence: divergence,
                signals: signals
            },
            summary: {
                trend: brushDirection,
                momentum: divergence.status,
                recommendation: signals.length > 0 ? signals[0].action : '观望'
            }
        };
        
        return formatAnalysisResult(result);
        
    } catch (error) {
        return { error: error.message };
    }
}

/**
 * 格式化分析结果为友好中文输出
 * @param {Object} result - 原始分析结果
 * @returns {Object} 格式化后的结果
 */
function formatAnalysisResult(result) {
    if (result.error) {
        return {
            content: `❌ 分析失败：${result.error}`,
            raw: result
        };
    }
    
    const symbol = result.symbol || result.current_price;
    const price = result.current_price;
    const change = result.change_pct ? `(${result.change_pct > 0 ? '+' : ''}${result.change_pct}%)` : '';
    
    let content = `📊 缠论分析报告\n\n`;
    content += `🏷️ ${symbol} | 当前价: ¥${price} ${change}\n`;
    content += `━━━━━━━━━━━━━━━━━━━━\n\n`;
    
    // 分型
    if (result.fraction) {
        content += `🔺 分型: ${result.fraction.type || '无'}\n`;
    }
    
    // 笔
    if (result.brush) {
        content += `📈 笔向: ${result.brush.direction || '不确定'}\n`;
        if (result.brush.strength) {
            content += `   强度: ${result.brush.strength}\n`;
        }
    } else if (result.analysis && result.analysis.brush_direction) {
        content += `📈 笔向: ${result.analysis.brush_direction}\n`;
    }
    
    // 中枢
    if (result.center && result.center.exists) {
        content += `\n🏠 中枢区域: ¥${result.center.low} ~ ¥${result.center.high}\n`;
        content += `   振幅: ¥${result.center.range}\n`;
    } else {
        content += `\n🏠 中枢: 暂未形成\n`;
    }
    
    // 背驰
    if (result.divergence) {
        content += `\n⚡ 背驰: ${result.divergence.status || '未背驰'}\n`;
        if (result.divergence.signal) {
            content += `   ${result.divergence.signal}\n`;
        }
    } else if (result.analysis && result.analysis.divergence) {
        content += `\n⚡ 背驰: ${result.analysis.divergence.status || '未背驰'}\n`;
    }
    
    // 买卖点
    const buySell = result.buy_sell_points || result.analysis?.signals;
    if (buySell && Object.keys(buySell).length > 0) {
        content += `\n🎯 买卖点:\n`;
        for (const [key, value] of Object.entries(buySell)) {
            if (value.signal || value.action) {
                content += `   ${key}: ${value.signal || value.action}\n`;
            }
        }
    }
    
    // 建议
    const recommendation = result.recommendation || result.summary?.recommendation;
    if (recommendation) {
        content += `\n💡 操作建议: ${recommendation}\n`;
    }
    
    return {
        content: content,
        raw: result
    };
}

/**
 * 技能入口
 */
module.exports = {
    name: 'chan-theory-analyzer',
    description: '缠论技术分析技能',
    main: async function(params) {
        return await analyze(params);
    },
    // 导出的方法
    analyze,
    identifyFraction,
    identifyCenter,
    identifyDivergence,
    generateSignals
};
