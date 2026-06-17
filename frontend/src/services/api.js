const API_BASE = '/api'

function safeResponse(data, fallbackError = '响应数据格式异常') {
  if (data == null) {
    return { success: false, error: fallbackError }
  }
  if (typeof data !== 'object') {
    return { success: false, error: `返回数据类型异常: ${typeof data}` }
  }
  if (typeof data.success !== 'boolean') {
    return {
      success: false,
      error: data.error || fallbackError,
      ...data,
    }
  }
  return data
}

async function request(url, options = {}) {
  const defaultHeaders = {
    'Content-Type': 'application/json',
  }
  try {
    const response = await fetch(`${API_BASE}${url}`, {
      ...options,
      headers: {
        ...defaultHeaders,
        ...(options.headers || {}),
      },
    })

    let data
    try {
      data = await response.json()
    } catch (parseErr) {
      const text = await response.text().catch(() => '')
      return {
        success: false,
        error: `服务器返回非 JSON 响应 (HTTP ${response.status})${text ? ': ' + text.slice(0, 200) : ''}`,
        httpStatus: response.status,
      }
    }

    if (!response.ok) {
      const safe = safeResponse(data, `请求失败 (HTTP ${response.status})`)
      if (!safe.error) safe.error = `请求失败 (HTTP ${response.status})`
      safe.httpStatus = response.status
      return safe
    }

    return safeResponse(data)
  } catch (err) {
    return {
      success: false,
      error: `网络请求失败: ${err?.message || String(err)}`,
    }
  }
}

export const api = {
  getHealth: () => request('/health'),

  getTopology: () => request('/topology'),

  getNodes: () => request('/nodes'),

  getConnections: () => request('/connections'),

  submitGasReading: (data) =>
    request('/gas-readings', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  submitBatchReadings: (readings) =>
    request('/gas-readings/batch', {
      method: 'POST',
      body: JSON.stringify({ readings }),
    }),

  getNodeReadings: (nodeId, limit = 10) =>
    request(`/gas-readings/${nodeId}?limit=${limit}`),

  getLatestReadings: () => request('/gas-readings/latest'),

  calculateRoute: (startId, endId) =>
    request(`/route?start_id=${encodeURIComponent(startId)}&end_id=${encodeURIComponent(endId)}`),

  getThresholds: () => request('/thresholds'),
}
