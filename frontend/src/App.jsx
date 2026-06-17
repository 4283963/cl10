import React, { useState, useEffect, useMemo } from 'react'
import TopologyCanvas from './components/TopologyCanvas.jsx'
import { api } from './services/api.js'

function App() {
  const [nodes, setNodes] = useState([])
  const [connections, setConnections] = useState([])
  const [routeData, setRouteData] = useState(null)
  const [compromiseRouteData, setCompromiseRouteData] = useState(null)
  const [startId, setStartId] = useState('WELL-A')
  const [endId, setEndId] = useState('WELL-B')
  const [loading, setLoading] = useState(false)
  const [calculating, setCalculating] = useState(false)
  const [error, setError] = useState(null)
  const [successMsg, setSuccessMsg] = useState(null)
  const [selectedNode, setSelectedNode] = useState(null)
  const [healthStatus, setHealthStatus] = useState('检查中...')
  const [thresholds, setThresholds] = useState({ h2s: 10, ch4: 1 })
  const [activeRouteTab, setActiveRouteTab] = useState('safe')

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
    setCompromiseRouteData(null)
    try {
      const res = await api.calculateRoute(startId, endId)

      if (!res || typeof res !== 'object') {
        setError('服务端返回空数据，请稍后重试')
        return
      }

      const safeRoute = res.safe_route
      const compRoute = res.compromise_route
      let msgs = []

      if (safeRoute && safeRoute.success && Array.isArray(safeRoute.path) && safeRoute.path.length > 0) {
        setRouteData(safeRoute)
        msgs.push(`✅ 安全路线：${safeRoute.path.length} 个节点，距离 ${safeRoute.total_distance}m`)
        if (activeRouteTab !== 'both') setActiveRouteTab('safe')
      }

      if (compRoute && compRoute.success && Array.isArray(compRoute.path) && compRoute.path.length > 0) {
        setCompromiseRouteData(compRoute)
        msgs.push(`⚠️ 妥协路线：${compRoute.path.length} 个节点，含 ${compRoute.danger_count || 0} 个超标点，预计 ${compRoute.walking_time_minutes || '?'} 分钟`)
        if (!safeRoute && activeRouteTab !== 'both') setActiveRouteTab('compromise')
      }

      if (msgs.length > 0) {
        setSuccessMsg(msgs.join('\n'))
      } else if (!res.success) {
        let msg = res.error || '路线规划失败'
        if (safeRoute && !safeRoute.success) msg += `\n安全路线：${safeRoute.error}`
        if (compRoute && !compRoute.success) msg += `\n妥协路线：${compRoute.error}`
        setError(msg)
      } else {
        setError('路线规划结果异常')
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
    setCompromiseRouteData(null)
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

  const routeInfo = useMemo(() => {
    if (activeRouteTab === 'compromise') return compromiseRouteData
    if (activeRouteTab === 'both') return routeData || compromiseRouteData
    return routeData
  }, [activeRouteTab, routeData, compromiseRouteData])

  const displayRouteData = useMemo(() => {
    if (activeRouteTab === 'compromise') return null
    return routeData
  }, [activeRouteTab, routeData])

  const displayCompromiseData = useMemo(() => {
    if (activeRouteTab === 'safe') return null
    return compromiseRouteData
  }, [activeRouteTab, compromiseRouteData])

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

            {(routeData || compromiseRouteData) && (
              <div style={{ marginTop: 14, display: 'flex', gap: 4, background: '#1a2538', borderRadius: 6, padding: 3 }}>
                <button
                  onClick={() => setActiveRouteTab('safe')}
                  style={{
                    flex: 1,
                    padding: '8px 6px',
                    background: activeRouteTab === 'safe' || activeRouteTab === 'both' ? '#ef5350' : 'transparent',
                    border: 'none',
                    borderRadius: 4,
                    color: activeRouteTab === 'safe' || activeRouteTab === 'both' ? '#fff' : '#90a4be',
                    fontSize: 12,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    fontWeight: 500,
                  }}
                >
                  🔴 安全路线
                </button>
                <button
                  onClick={() => setActiveRouteTab('compromise')}
                  style={{
                    flex: 1,
                    padding: '8px 6px',
                    background: activeRouteTab === 'compromise' || activeRouteTab === 'both' ? '#ffa726' : 'transparent',
                    border: 'none',
                    borderRadius: 4,
                    color: activeRouteTab === 'compromise' || activeRouteTab === 'both' ? '#fff' : '#90a4be',
                    fontSize: 12,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    fontWeight: 500,
                  }}
                  disabled={!compromiseRouteData}
                >
                  🟠 咬牙路线
                </button>
                <button
                  onClick={() => setActiveRouteTab('both')}
                  style={{
                    flex: 1,
                    padding: '8px 6px',
                    background: activeRouteTab === 'both' ? '#1976d2' : 'transparent',
                    border: 'none',
                    borderRadius: 4,
                    color: activeRouteTab === 'both' ? '#fff' : '#90a4be',
                    fontSize: 12,
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    fontWeight: 500,
                  }}
                >
                  🔀 对比
                </button>
              </div>
            )}

            {error && <div className="error-message">❌ {error}</div>}
            {successMsg && <div className="success-message" style={{ whiteSpace: 'pre-line' }}>✅ {successMsg}</div>}
          </div>

          {routeInfo && (
            <div className="panel-section">
              <div className="panel-title">
                📊 {routeInfo.route_type === 'compromise' ? '⚠️ 妥协（咬牙）路线' : '✅ 安全巡检路线'}分析报告
              </div>

              {routeInfo.route_type === 'compromise' && routeInfo.recommendation && (
                <div style={{
                  background: 'rgba(255, 167, 38, 0.12)',
                  border: '1px solid rgba(255, 167, 38, 0.4)',
                  borderRadius: 6,
                  padding: '10px 12px',
                  marginBottom: 14,
                  fontSize: 12,
                  color: '#ffb74d',
                  lineHeight: 1.7,
                  whiteSpace: 'pre-line',
                }}>
                  {routeInfo.recommendation}
                </div>
              )}

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
                  {routeInfo.route_type === 'compromise' ? (
                    <>
                      <div className="metric">
                        <div className="metric-label">预计时间</div>
                        <div className={`metric-value ${routeInfo.time_acceptable ? 'safe' : 'danger'}`}>
                          {routeInfo.walking_time_minutes} 分钟
                        </div>
                      </div>
                      <div className="metric">
                        <div className="metric-label">超标节点</div>
                        <div className="metric-value danger">{routeInfo.danger_count || 0} 个</div>
                      </div>
                      <div className="metric">
                        <div className="metric-label">预警节点</div>
                        <div className="metric-value warning">{routeInfo.warning_count || 0} 个</div>
                      </div>
                    </>
                  ) : (
                    <>
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
                    </>
                  )}
                  {routeInfo.route_type === 'compromise' && (
                    <>
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
                    </>
                  )}
                </div>
              </div>

              <div className="route-path-list">
                {(routeInfo.nodes || []).map((node, idx) => {
                  const isStart = idx === 0
                  const isEnd = idx === routeInfo.nodes.length - 1
                  const nodeStatus = node.status || 'safe'
                  return (
                    <div
                      key={`route-${idx}-${node.id}`}
                      className={`path-item ${isStart ? 'start' : ''} ${isEnd ? 'end' : ''}`}
                      style={{
                        borderLeftColor: nodeStatus === 'danger' ? '#ef5350'
                          : nodeStatus === 'warning' ? '#ffa726'
                          : isStart ? '#66bb6a' : isEnd ? '#ef5350' : '#1976d2'
                      }}
                    >
                      <div className="index" style={{
                        background: nodeStatus === 'danger' ? 'rgba(239, 83, 80, 0.2)'
                          : nodeStatus === 'warning' ? 'rgba(255, 167, 38, 0.2)' : '#2d3b55',
                        color: nodeStatus === 'danger' ? '#ef5350'
                          : nodeStatus === 'warning' ? '#ffa726' : '#90a4be',
                      }}>{idx + 1}</div>
                      <div className="info">
                        <div className="name">
                          {node.name}
                          {isStart && <span style={{ color: '#66bb6a', marginLeft: 6 }}>（起点）</span>}
                          {isEnd && <span style={{ color: '#ef5350', marginLeft: 6 }}>（终点）</span>}
                          {nodeStatus === 'danger' && <span style={{ color: '#ef5350', marginLeft: 6 }}>⚠️超标</span>}
                          {nodeStatus === 'warning' && <span style={{ color: '#ffa726', marginLeft: 6 }}>⚡预警</span>}
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
                <span>超标节点</span>
              </div>
              <div style={{ height: 6 }} />
              <div className="legend-item">
                <div className="legend-marker line normal" />
                <span>普通管网连接</span>
              </div>
              <div className="legend-item">
                <div className="legend-marker line route" />
                <span>安全路线 (粗红线)</span>
              </div>
              <div className="legend-item">
                <div className="legend-marker line compromise" />
                <span>咬牙路线 (闪烁橙线)</span>
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
            routeData={displayRouteData}
            compromiseRouteData={displayCompromiseData}
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
