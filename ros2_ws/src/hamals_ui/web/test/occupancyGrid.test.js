import test from 'node:test'
import assert from 'node:assert/strict'
import { createMapFeed, mapStatus, occupancyPixels, mapCellToWorld, worldToCanvas } from '../src/composables/occupancyGrid.js'
import { createMockMap } from '../src/composables/mockMap.js'

test('row-major ROS cells flip vertically and preserve occupancy shades', () => {
  const message = { info: { width: 2, height: 2 }, data: [0, 100, -1, 50] }
  const image = { data: new Uint8ClampedArray(16) }
  occupancyPixels(message, image)
  const at = (x, y) => [...image.data.slice((y * 2 + x) * 4, (y * 2 + x + 1) * 4)]
  assert.deepEqual(at(0, 0), [55, 65, 79, 255])
  assert.deepEqual(at(1, 0), [123, 123, 123, 255])
  assert.deepEqual(at(0, 1), [226, 226, 226, 255])
  assert.deepEqual(at(1, 1), [20, 20, 20, 255])
})

test('map feed retains a single message independently of dashboard freshness', () => {
  const feed = createMapFeed(), message = createMockMap()
  const received = []
  const stop = feed.listen((value, at) => received.push({ value, at }))
  feed.push(message)
  assert.equal(received.length, 1)
  assert.equal(received[0].value, message)
  assert.equal(mapStatus(feed.receivedAt, true, feed.receivedAt + 300000), 'LIVE')
  assert.equal(mapStatus(feed.receivedAt, true, feed.receivedAt + 300001), 'STALE')
  assert.equal(mapStatus(feed.receivedAt, false), 'DISCONNECTED')
  stop()
  feed.push(message)
  assert.equal(received.length, 1)
  feed.listen(value => received.push({ value }))
  assert.equal(received.length, 2)
})

test('world conversion respects origin yaw and map Y direction', () => {
  const map = createMockMap()
  map.info.origin.position = { x: 1, y: 2, z: 0 }
  map.info.origin.orientation = { x: 0, y: 0, z: Math.SQRT1_2, w: Math.SQRT1_2 }
  const point = worldToCanvas(map, 1, 2.1)
  assert.ok(Math.abs(point.x - 2) < 1e-8)
  assert.ok(Math.abs(point.y - map.info.height) < 1e-8)
  const world = mapCellToWorld(map, { x: 2, y: 0 })
  assert.ok(Math.abs(world.x - 1) < 1e-8)
  assert.ok(Math.abs(world.y - 2.1) < 1e-8)
})
