// The feed keeps large OccupancyGrid arrays outside Vue's reactive graph.
export function createMapFeed() {
  let latest = null
  let receivedAt = null
  const listeners = new Set()
  return {
    get latest() { return latest },
    get receivedAt() { return receivedAt },
    push(message) {
      const { width, height, resolution } = message?.info || {}
      if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0 ||
          !Number.isFinite(resolution) || resolution <= 0 || message?.data?.length !== width * height) return
      latest = message
      receivedAt = Date.now()
      for (const listener of listeners) listener(message, receivedAt)
    },
    listen(listener) {
      listeners.add(listener)
      if (latest) listener(latest, receivedAt)
      return () => listeners.delete(listener)
    },
  }
}

export function mapStatus(receivedAt, connected, now = Date.now()) {
  if (!connected) return 'DISCONNECTED'
  if (receivedAt == null) return 'WAITING'
  return now - receivedAt > 300000 ? 'STALE' : 'LIVE'
}

// ROS data is row-major from the bottom left; ImageData starts at the top left.
export function occupancyPixels(message, imageData) {
  const { width, height } = message.info
  const pixels = imageData.data
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const occupancy = message.data[y * width + x]
      const target = ((height - 1 - y) * width + x) * 4
      const shade = occupancy < 0 ? 48 : Math.round(226 - Math.min(100, Math.max(0, occupancy)) * 2.06)
      pixels[target] = occupancy < 0 ? 55 : shade
      pixels[target + 1] = occupancy < 0 ? 65 : shade
      pixels[target + 2] = occupancy < 0 ? 79 : shade
      pixels[target + 3] = 255
    }
  }
  return imageData
}

export function worldToMapCell(message, x, y) {
  const { position, orientation } = message.info.origin
  const q = orientation || { x: 0, y: 0, z: 0, w: 1 }
  const yaw = Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
  const dx = x - position.x, dy = y - position.y
  return { x: (Math.cos(yaw) * dx + Math.sin(yaw) * dy) / message.info.resolution,
    y: (-Math.sin(yaw) * dx + Math.cos(yaw) * dy) / message.info.resolution }
}

export function mapCellToWorld(message, cell) {
  const { position, orientation } = message.info.origin
  const q = orientation || { x: 0, y: 0, z: 0, w: 1 }
  const yaw = Math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
  const dx = cell.x * message.info.resolution, dy = cell.y * message.info.resolution
  return { x: position.x + Math.cos(yaw) * dx - Math.sin(yaw) * dy,
    y: position.y + Math.sin(yaw) * dx + Math.cos(yaw) * dy }
}

export function mapCellToCanvas(message, cell) {
  return { x: cell.x, y: message.info.height - cell.y }
}

export function worldToCanvas(message, x, y) {
  return mapCellToCanvas(message, worldToMapCell(message, x, y))
}
