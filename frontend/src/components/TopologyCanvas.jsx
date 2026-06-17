import React, { useState, useRef, useEffect, useMemo } from 'react'

const NODE_RADIUS = {
  wellhead: 22,
  junction: 16,
  monitor: 14,
}

const STATUS_COLORS = {
  safe: '#66bb6a',
  warning: '#ffa726',
  danger: '#ef5350',
}

function TopologyCanvas({ nodes, connections, routeData, compromiseRouteData, onNodeSelect, selectedNode, setSelectedNode }) {
  const containerRef = useRef(null)
  const svgRef = useRef(null)
  const [viewport, setViewport] = useState({ scale: 1, offsetX: 0, offsetY: 0 })
  const [isDragging, setIsDragging] = useState(false)
  const dragStart = useRef({ x: 0, y: 0, offsetX: 0, offsetY: 0 })
  const [tooltip, setTooltip] = useState(null)

  const { width: canvasWidth, height: canvasHeight } = useMemo(() => {
    if (!containerRef.current) return { width: 800, height: 600 }
    const rect = containerRef.current.getBoundingClientRect()
    return { width: rect.width, height: rect.height }
  }, [nodes, connections])

  const { bbox, transformedNodes } = useMemo(() => {
    if (!nodes.length) return { bbox: null, transformedNodes: [] }
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    nodes.forEach(n => {
      if (n.x < minX) minX = n.x
      if (n.x > maxX) maxX = n.x
      if (n.y < minY) minY = n.y
      if (n.y > maxY) maxY = n.y
    })
    const padding = 80
    const bbox = { minX: minX - padding, minY: minY - padding, maxX: maxX + padding, maxY: maxY + padding }
    const dataWidth = bbox.maxX - bbox.minX
    const dataHeight = bbox.maxY - bbox.minY
    const scaleX = canvasWidth / dataWidth
    const scaleY = canvasHeight / dataHeight
    const scale = Math.min(scaleX, scaleY) * 0.9
    const offsetX = (canvasWidth - dataWidth * scale) / 2 - bbox.minX * scale
    const offsetY = (canvasHeight - dataHeight * scale) / 2 - bbox.minY * scale
    const transformedNodes = nodes.map(n => ({
      ...n,
      tx: n.x * scale + offsetX,
      ty: n.y * scale + offsetY,
    }))
    return { bbox, transformedNodes }
  }, [nodes, canvasWidth, canvasHeight])

  const nodeMap = useMemo(() => {
    const m = {}
    transformedNodes.forEach(n => { m[n.id] = n })
    return m
  }, [transformedNodes])

  const routeEdgesSet = useMemo(() => {
    const s = new Set()
    if (routeData && routeData.edges) {
      routeData.edges.forEach(e => {
        s.add(`${e.from}|${e.to}`)
        s.add(`${e.to}|${e.from}`)
      })
    }
    return s
  }, [routeData])

  const routeNodeSet = useMemo(() => {
    const s = new Set()
    if (routeData && routeData.path) {
      routeData.path.forEach(p => s.add(p))
    }
    return s
  }, [routeData])

  const compromiseEdgesSet = useMemo(() => {
    const s = new Set()
    if (compromiseRouteData && compromiseRouteData.edges) {
      compromiseRouteData.edges.forEach(e => {
        s.add(`${e.from}|${e.to}`)
        s.add(`${e.to}|${e.from}`)
      })
    }
    return s
  }, [compromiseRouteData])

  const compromiseNodeSet = useMemo(() => {
    const s = new Set()
    if (compromiseRouteData && compromiseRouteData.path) {
      compromiseRouteData.path.forEach(p => s.add(p))
    }
    return s
  }, [compromiseRouteData])

  const handleMouseDown = (e) => {
    if (e.target.closest('.node-group')) return
    setIsDragging(true)
    dragStart.current = {
      x: e.clientX,
      y: e.clientY,
      offsetX: viewport.offsetX,
      offsetY: viewport.offsetY,
    }
  }

  const handleMouseMove = (e) => {
    if (isDragging) {
      setViewport(v => ({
        ...v,
        offsetX: dragStart.current.offsetX + (e.clientX - dragStart.current.x),
        offsetY: dragStart.current.offsetY + (e.clientY - dragStart.current.y),
      }))
    }
  }

  const handleMouseUp = () => {
    setIsDragging(false)
  }

  const handleWheel = (e) => {
    e.preventDefault()
    const delta = e.deltaY > 0 ? 0.9 : 1.1
    setViewport(v => ({
      ...v,
      scale: Math.max(0.3, Math.min(3, v.scale * delta)),
    }))
  }

  const handleNodeMouseEnter = (e, node) => {
    const rect = containerRef.current.getBoundingClientRect()
    setTooltip({
      node,
      x: e.clientX - rect.left + 14,
      y: e.clientY - rect.top + 14,
    })
  }

  const handleNodeMouseMove = (e) => {
    if (!tooltip) return
    const rect = containerRef.current.getBoundingClientRect()
    setTooltip(t => t && ({
      ...t,
      x: e.clientX - rect.left + 14,
      y: e.clientY - rect.top + 14,
    }))
  }

  const handleNodeMouseLeave = () => {
    setTooltip(null)
  }

  const handleNodeClick = (node) => {
    setSelectedNode(selectedNode === node.id ? null : node.id)
    onNodeSelect && onNodeSelect(node)
  }

  const getStatusLabel = (s) => {
    const map = { safe: '安全', warning: '注意', danger: '超标' }
    return map[s] || '未知'
  }

  const getValueColor = (value, threshold) => {
    const ratio = value / threshold
    if (ratio >= 1) return 'danger'
    if (ratio >= 0.5) return 'warning'
    return ''
  }

  return (
    <div className="canvas-container" ref={containerRef}>
      <svg
        ref={svgRef}
        className="topology-svg"
        viewBox={`${-viewport.offsetX / viewport.scale} ${-viewport.offsetY / viewport.scale} ${canvasWidth / viewport.scale} ${canvasHeight / viewport.scale}`}
        onMouseDown={handleMouseDown}
        onMouseMove={(e) => { handleMouseMove(e); handleNodeMouseMove(e) }}
        onMouseUp={handleMouseUp}
        onMouseLeave={() => { handleMouseUp(); handleNodeMouseLeave() }}
        onWheel={handleWheel}
      >
        <defs>
          <radialGradient id="bgGrid">
            <stop offset="0%" stopColor="#131c2e" />
            <stop offset="100%" stopColor="#0b1220" />
          </radialGradient>
          <filter id="glow-danger" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="glow-route" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id="glow-compromise" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="3" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect x="-10000" y="-10000" width="30000" height="30000" fill="url(#bgGrid)" />

        <g>
          {connections.map(conn => {
            const from = nodeMap[conn.from_node_id]
            const to = nodeMap[conn.to_node_id]
            if (!from || !to) return null
            const key = `${conn.from_node_id}|${conn.to_node_id}`
            const isCompromise = compromiseEdgesSet.has(key) && !routeEdgesSet.has(key)
            const isRoute = routeEdgesSet.has(key)

            if (isCompromise) {
              return (
                <g key={`compromise-${conn.id}`}>
                  <line
                    x1={from.tx}
                    y1={from.ty}
                    x2={to.tx}
                    y2={to.ty}
                    stroke="#ffb74d"
                    strokeWidth="8"
                    strokeLinecap="round"
                    opacity="0.25"
                  />
                  <line
                    x1={from.tx}
                    y1={from.ty}
                    x2={to.tx}
                    y2={to.ty}
                    stroke="#ffa726"
                    strokeWidth="5"
                    strokeLinecap="round"
                    strokeDasharray="12 8"
                    filter="url(#glow-compromise)"
                  >
                    <animate
                      attributeName="stroke-dashoffset"
                      from="0"
                      to="40"
                      dur="1.5s"
                      repeatCount="indefinite"
                    />
                    <animate
                      attributeName="opacity"
                      values="0.5;1;0.5"
                      dur="1.2s"
                      repeatCount="indefinite"
                    />
                  </line>
                </g>
              )
            }

            return (
              <g key={`conn-${conn.id}`}>
                <line
                  x1={from.tx}
                  y1={from.ty}
                  x2={to.tx}
                  y2={to.ty}
                  stroke={isRoute ? '#ef5350' : '#3d4f70'}
                  strokeWidth={isRoute ? 6 : 3}
                  strokeLinecap="round"
                  opacity={isRoute ? 0.3 : 0.6}
                />
                <line
                  x1={from.tx}
                  y1={from.ty}
                  x2={to.tx}
                  y2={to.ty}
                  stroke={isRoute ? '#ef5350' : '#506687'}
                  strokeWidth={isRoute ? 4 : 1.8}
                  strokeLinecap="round"
                  filter={isRoute ? 'url(#glow-route)' : ''}
                />
              </g>
            )
          })}
        </g>

        <g>
          {transformedNodes.map(node => {
            const r = NODE_RADIUS[node.node_type] || 14
            const statusColor = STATUS_COLORS[node.status] || '#506687'
            const isRoute = routeNodeSet.has(node.id)
            const isCompromise = compromiseNodeSet.has(node.id) && !isRoute
            const isSelected = selectedNode === node.id
            return (
              <g
                key={`node-${node.id}`}
                className="node-group"
                transform={`translate(${node.tx}, ${node.ty})`}
                onMouseEnter={(e) => handleNodeMouseEnter(e, node)}
                onMouseLeave={handleNodeMouseLeave}
                onClick={() => handleNodeClick(node)}
                style={{ cursor: 'pointer' }}
              >
                {isRoute && (
                  <circle
                    r={r + 8}
                    fill="none"
                    stroke="#ef5350"
                    strokeWidth="2"
                    strokeDasharray="4 3"
                    opacity="0.7"
                  >
                    <animateTransform
                      attributeName="transform"
                      type="rotate"
                      from="0"
                      to="360"
                      dur="6s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                {isCompromise && (
                  <circle
                    r={r + 6}
                    fill="none"
                    stroke="#ffa726"
                    strokeWidth="2.5"
                    strokeDasharray="6 4"
                    opacity="0.9"
                  >
                    <animate
                      attributeName="stroke-opacity"
                      values="0.4;1;0.4"
                      dur="1.2s"
                      repeatCount="indefinite"
                    />
                  </circle>
                )}
                {isSelected && (
                  <circle
                    r={r + 12}
                    fill="none"
                    stroke="#4fc3f7"
                    strokeWidth="2"
                    opacity="0.8"
                  />
                )}
                {node.node_type === 'wellhead' ? (
                  <g>
                    <rect
                      x={-r - 2}
                      y={-r - 8}
                      width={(r + 2) * 2}
                      height="10"
                      rx="3"
                      fill="#29436a"
                      stroke={statusColor}
                      strokeWidth="1.5"
                    />
                    <circle
                      r={r}
                      fill="#1a2538"
                      stroke={statusColor}
                      strokeWidth={node.status === 'danger' ? 3 : 2}
                      filter={node.status === 'danger' ? 'url(#glow-danger)' : ''}
                    />
                    <path
                      d={`M ${-r * 0.6} 0 Q 0 ${r * 0.6} ${r * 0.6} 0`}
                      fill="none"
                      stroke={statusColor}
                      strokeWidth="2"
                    />
                  </g>
                ) : node.node_type === 'monitor' ? (
                  <g>
                    <circle
                      r={r}
                      fill="#1a2538"
                      stroke={statusColor}
                      strokeWidth={node.status === 'danger' ? 3 : 2}
                      filter={node.status === 'danger' ? 'url(#glow-danger)' : ''}
                    />
                    <rect x={-4} y={-4} width="8" height="8" rx="1" fill={statusColor} opacity="0.8" />
                  </g>
                ) : (
                  <circle
                    r={r}
                    fill="#1a2538"
                    stroke={statusColor}
                    strokeWidth={node.status === 'danger' ? 3 : 2}
                    filter={node.status === 'danger' ? 'url(#glow-danger)' : ''}
                  />
                )}
                <text
                  y={r + 16}
                  textAnchor="middle"
                  fill={isRoute ? '#ef5350' : isCompromise ? '#ffa726' : '#90a4be'}
                  fontSize="11"
                  fontWeight={isRoute || isCompromise ? '600' : '500'}
                  style={{ pointerEvents: 'none', userSelect: 'none' }}
                >
                  {node.name}
                </text>
              </g>
            )
          })}
        </g>
      </svg>

      {tooltip && (
        <div
          className="node-tooltip"
          style={{
            left: Math.min(tooltip.x, canvasWidth - 240),
            top: Math.min(tooltip.y, canvasHeight - 200),
          }}
        >
          <div className="tooltip-title">
            {tooltip.node.name}
            <span className={`tooltip-status ${tooltip.node.status}`} style={{ marginLeft: 8 }}>
              {getStatusLabel(tooltip.node.status)}
            </span>
          </div>
          <div className="tooltip-row">
            <span>节点ID</span>
            <span className="v">{tooltip.node.id}</span>
          </div>
          <div className="tooltip-row">
            <span>节点类型</span>
            <span className="v">{tooltip.node.node_type === 'wellhead' ? '井口' : tooltip.node.node_type === 'monitor' ? '监测点' : '连接点'}</span>
          </div>
          <div className="tooltip-row">
            <span>H₂S 浓度</span>
            <span className={`v ${getValueColor(tooltip.node.h2s, 10)}`}>
              {tooltip.node.h2s?.toFixed(2)} / 10 ppm
            </span>
          </div>
          <div className="tooltip-row">
            <span>CH₄ 浓度</span>
            <span className={`v ${getValueColor(tooltip.node.ch4, 1)}`}>
              {tooltip.node.ch4?.toFixed(3)} / 1 %LEL
            </span>
          </div>
          {tooltip.node.depth != null && (
            <div className="tooltip-row">
              <span>埋设深度</span>
              <span className="v">{tooltip.node.depth.toFixed(1)} m</span>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default TopologyCanvas
