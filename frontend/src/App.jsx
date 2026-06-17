import React, { useState, useEffect, useMemo } from 'react'
import TopologyCanvas from './components/TopologyCanvas.jsx'
import { api } from './services/api.js'

function App() {
  const [nodes, setNodes] = useState([])
  const [connections, setConnections] = useState([])
  const [routeData, setRouteData] = useState(null)
  const [startId, setStartId] = useState('WELL-A')
  const [endId, setEndId] = useState('WELL-B')
  const [loading, setLoading] = useState(false)
  const [calculating, setCalculating] = useState(false)
  const [error, setError] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [healthStatus, setHealthStatus] = useState('检查中...')
  const [thresholds, setThresholds] = useState({ h2s: 10, ch4: 1 })

  useEffect(() => {
    loadData()
    checkHealth()
    loadThresholds()
  }, [])

  const checkHealth = async () => {
    try {
      const res = await api.getHealth()
      if (res.status === 'ok') {
        setHealthStatus('正常运行')
      } else {
        setHealthStatus('异常')
      }
    } catch {
      setHealthStatus('连接失败')
    }
  }

  const loadThresholds = async () => {
    try {
      const res = await api.getThresholds()
      if (res.success && res.data) {
        setThresholds({
          h2s: res.data.h2s_threshold,
          ch4: res.data.ch4_threshold,
        })
      }
    } catch {}
  }

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      const topoRes = await api.getTopology()
      if (topoRes.success) {
        setNodes(topoRes.data.nodes || [])
        setConnections(topoRes.data.connections || [])
      } else {
        setError(topoRes.error || '加载拓扑数据失败')
      }
    } catch (err) {
      setError('网络错误：无法连接到后端服务')
    } finally {
      setLoading(false)
    }
  }

  const handleCalculateRoute = async () => {
    if (!startId || !endId) {
      setError('请选择起点和终点')
      return
    }
    setCalculating(true)
    setError(null)
    setSuccessMsg(null)
    setRouteData(null)
    try {
      const res = await api.calculateRoute(startId, endId)

      if (!res || typeof res !== 'object') {
        setError('服务端返回空数据，请稍后重试')
        return
      }

      if (res.success) {
        if (!Array.isArray(res.path) || res.path.length === 0) {
          setError('路线规划结果异常：路径数据为空')
          return
        }
        setRouteData(res)
        setSuccessMsg(`路线规划成功！共经过 ${res.path.length} 个节点`)
      } else {
        let msg = res.error || '路线规划失败'
        if (Array.isArray(res.blocked_nodes) && res.blocked_nodes.length > 0) {
          const list = res.blocked_nodes
            .slice(0, 5)
            .map(b => `${b.name || b.id}(H₂S=${b.h2s}, CH₄=${b.ch4})`)
            .join('；')
          msg += `\n当前超标节点 (共${res.blocked_nodes.length}个): ${list}${res.blocked_nodes.length > 5 ? '...' : ''}`
        }
        if (typeof res.safe_node_count === 'number' && typeof res.total_node_count === 'number') {
          msg += `\n管网安全节点数: ${res.safe_node_count}/${res.total_node_count}`
        }
        setError(msg)
      }
    } catch (err) {
      setError(`网络错误：${err?.message || '无法获取路线规划'}`)
    } finally {
      setCalculating(false)
    }
  }

  const handleRefresh = async () => {
    await loadData()
    setRouteData(null)
    setError(null)
    setSuccessMsg('数据已刷新')
    setTimeout(() => setSuccessMsg(null), 3000)
  }

  const wellheadOptions = useMemo(() => {
    return nodes.filter(n => n.node_type === 'wellhead' || n.node_type === 'monitor')
  }, [nodes])

  const stats = useMemo(() => {
    const safe = nodes.filter(n => n.status === 'safe').length
    const warning = nodes.filter(n => n.status === 'warning').length
    const danger = nodes.filter(n => n.status === 'danger').length
    return { total: nodes.length, safe, warning, danger }
  }, [nodes])

  const routeInfo = routeData || null

  const handleNodeSelect = (node) => {
    setSelectedNode(node.id)
  }

  const getValueClass = (val, threshold) => {
    const ratio = val / threshold
    if (ratio >= 1) return 'danger'
    if (ratio >= 0.5) return 'warning'
    return 'safe'
  }

  return (
    <div className="app-container">
      <header className="app-header">
        <div className="app-title">
          <div className="header-logo">🕳️</div>
          <div>
            <h1>地下管网智能巡检系统</h1>
            <div className="subtitle">安全路线规划 · 有害气体实时监测</div>
          </div>
        </div>
        <div className="header-info">
          <div className="info-item">
            <span className="status-dot" />
            <span>服务状态：<span className="value">{healthStatus}</span></span>
          </div>
          <div className="info-item">
            <span>节点总数：<span className="value">{stats.total}</span></span>
          </div>
          <div className="info-item">
            <span>安全：<span className="value" style={{ color: '#66bb6a' }}>{stats.safe}</span></span>
          </div>
          <div className="info-item">
            <span>预警：<span className="value" style={{ color: '#ffa726' }}>{stats.warning}</span></span>
          </div>
          <div className="info-item">
            <span>超标：<span className="value" style={{ color: '#ef5350' }}>{stats.danger}</span></span>
          </div>
        </div>
      </header>

      <div className="app-main">
        <aside className="left-panel">
          <div className="panel-section">
            <div className="panel-title">🗺️ 路线规划</div>

            <div className="form-group">
              <label>起点（井口）</label>
              <select value={startId} onChange={(e) => setStartId(e.target.value)}>
                {wellheadOptions.map(n => (
                  <option key={n.id} value={n.id} disabled={n.status === 'danger'}>
                    {n.name} ({n.id}) {n.status === 'danger' ? ' ⚠️超标' : ''}
                  </option>
                ))}
                <optgroup label="全部节点">
                  {nodes.map(n => (
                    <option key={`all-${n.id}`} value={n.id}>
                      {n.name} ({n.id}) {n.status === 'danger' ? ' ⚠️超标' : ''}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>

            <div className="form-group">
              <label>终点（井口）</label>
              <select value={endId} onChange={(e) => setEndId(e.target.value)}>
                {wellheadOptions.map(n => (
                  <option key={n.id} value={n.id} disabled={n.status === 'danger'}>
                    {n.name} ({n.id}) {n.status === 'danger' ? ' ⚠️超标' : ''}
                  </option>
                ))}
                <optgroup label="全部节点">
                  {nodes.map(n => (
                    <option key={`all-${n.id}`} value={n.id}>
                      {n.name} ({n.id}) {n.status === 'danger' ? ' ⚠️超标' : ''}
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>

            <button
              className="btn-primary"
              onClick={handleCalculateRoute}
              disabled={calculating}
            >
              {calculating ? '规划中...' : '🔍 计算安全巡检路线'}
            </button>

            <button className="btn-secondary" onClick={handleRefresh} disabled={loading}>
              🔄 刷新数据
            </button>

            {error && <div className="error-message">❌ {error}</div>}
            {successMsg && <div className="success-message">✅ {successMsg}</div>}
          </div>

          {routeInfo && (
            <div className="panel-section">
              <div className="panel-title">📊 路线分析报告</div>

              <div className="route-summary">
                <div style={{ fontSize: 12, color: '#90a4be', marginBottom: 4 }}>
                  {routeInfo.nodes?.[0]?.name} → {routeInfo.nodes?.[routeInfo.nodes.length - 1]?.name}
                </div>
                <div style={{ fontSize: 15, fontWeight: 600, color: '#e8ecf3' }}>
                  共 {routeInfo.path?.length} 个节点
                </div>
                <div className="route-metrics">
                  <div className="metric">
                    <div className="metric-label">总距离</div>
                    <div className="metric-value">{routeInfo.total_distance} m</div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">综合风险分</div>
                    <div className={`metric-value ${
                      routeInfo.total_risk_score > (routeInfo.path?.length || 1) * 0.8 ? 'warning' : 'safe'
                    }`}>
                      {routeInfo.total_risk_score}
                    </div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">平均 H₂S</div>
                    <div className={`metric-value ${getValueClass(routeInfo.avg_h2s || 0, thresholds.h2s)}`}>
                      {routeInfo.avg_h2s} ppm
                    </div>
                  </div>
                  <div className="metric">
                    <div className="metric-label">平均 CH₄</div>
                    <div className={`metric-value ${getValueClass(routeInfo.avg_ch4 || 0, thresholds.ch4)}`}>
                      {routeInfo.avg_ch4} %LEL
                    </div>
                  </div>
                </div>
              </div>

              <div className="route-path-list">
                {(routeInfo.nodes || []).map((node, idx) => {
                  const isStart = idx === 0
                  const isEnd = idx === routeInfo.nodes.length - 1
                  return (
                    <div
                      key={`route-${idx}-${node.id}`}
                      className={`path-item ${isStart ? 'start' : ''} ${isEnd ? 'end' : ''}`}
                    >
                      <div className="index">{idx + 1}</div>
                      <div className="info">
                        <div className="name">
                          {node.name}
                          {isStart && <span style={{ color: '#66bb6a', marginLeft: 6 }}>（起点）</span>}
                          {isEnd && <span style={{ color: '#ef5350', marginLeft: 6 }}>（终点）</span>}
                        </div>
                        <div className="gas-info">
                          <span style={{
                            color: getValueClass(node.h2s || 0, thresholds.h2s) === 'danger' ? '#ef5350'
                              : getValueClass(node.h2s || 0, thresholds.h2s) === 'warning' ? '#ffa726' : '#7a8ba6'
                          }}>
                            H₂S {node.h2s?.toFixed(2)}
                          </span>
                          <span style={{
                            color: getValueClass(node.ch4 || 0, thresholds.ch4) === 'danger' ? '#ef5350'
                              : getValueClass(node.ch4 || 0, thresholds.ch4) === 'warning' ? '#ffa726' : '#7a8ba6'
                          }}>
                            CH₄ {node.ch4?.toFixed(3)}
                          </span>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}

          <div className="panel-section">
            <div className="panel-title">📖 图例说明</div>
            <div className="legend">
              <div className="legend-item">
                <div className="legend-marker well" />
                <span>井口/出入口</span>
              </div>
              <div className="legend-item">
                <div className="legend-marker safe" />
                <span>安全节点 (未超标)</span>
              </div>
              <div className="legend-item">
                <div className="legend-marker warning" />
                <span>预警节点 (≥50%阈值)</span>
              </div>
              <div className="legend-item">
                <div className="legend-marker danger" />
                <span>超标节点 (不可通行)</span>
              </div>
              <div style={{ height: 6 }} />
              <div className="legend-item">
                <div className="legend-marker line normal" />
                <span>普通管网连接</span>
              </div>
              <div className="legend-item">
                <div className="legend-marker line route" />
                <span>安全巡检路线 (粗红线)</span>
              </div>
            </div>
            <div style={{ marginTop: 14, fontSize: 11, color: '#506687', lineHeight: 1.7 }}>
              阈值标准：<br />
              · H₂S 硫化氢 ≥ {thresholds.h2s} ppm → 超标<br />
              · CH₄ 甲烷 ≥ {thresholds.ch4} %LEL → 超标
            </div>
          </div>
        </aside>

        <main className="right-panel">
          {loading && (
            <div className="loading-overlay">
              <div className="loading-content">
                <div className="loading-spinner" />
                <div className="loading-text">正在加载管网拓扑数据...</div>
              </div>
            </div>
          )}
          <TopologyCanvas
            nodes={nodes}
            connections={connections}
            routeData={routeInfo}
            onNodeSelect={handleNodeSelect}
            selectedNode={selectedNode}
            setSelectedNode={setSelectedNode}
          />
        </main>
      </div>
    </div>
  )
}

export default App
