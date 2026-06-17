const API_BASE = '/api'

async function request(url, options = {}) {
  const defaultHeaders = {
    'Content-Type': 'application/json',
  }
  const response = await fetch(`${API_BASE}${url}`, {
    ...options,
    headers: {
      ...defaultHeaders,
      ...(options.headers || {}),
    },
  })
  const data = await response.json()
  return data
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
