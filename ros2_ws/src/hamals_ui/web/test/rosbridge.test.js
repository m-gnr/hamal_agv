import test from 'node:test'
import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { useRosbridge } from '../src/composables/useRosbridge.js'

function setup(t) {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'], now: 100000 })
  const clients = [], topics = [], sent = []
  class Ros extends EventEmitter {
    constructor() { super(); clients.push(this); this.isConnected = false }
    close() { this.isConnected = false; this.emit('close') }
  }
  class Topic {
    constructor(options) { Object.assign(this, options); topics.push(this) }
    subscribe(cb) { this.cb = cb }
    unsubscribe() { this.cb = null }
    publish(msg) { sent.push({ topic: this.name, msg }) }
  }
  class Message { constructor(data) { Object.assign(this, data) } }
  const bridge = useRosbridge('ws://test', { Ros, Topic, Message })
  t.after(() => bridge.disconnect())
  bridge.connect()
  const connect = () => { clients.at(-1).isConnected = true; clients.at(-1).emit('connection') }
  const receiveMode = mode => topics.findLast(x => x.name === '/switch/mode').cb({ data: mode })
  const receiveState = (mode = 'manual', ts = Date.now() / 1000) => topics.findLast(x => x.name === '/ui/state').cb({ data: JSON.stringify({ meta: { mode: 'live', ts, sources: { '/switch/mode': { age_s: 0 } } }, switch: { mode } }) })
  return { bridge, clients, topics, sent, connect, receiveMode, receiveState }
}
test('direct mode opens manual controls without /ui/state and gates teleop and fork', t => {
  const f = setup(t); f.connect()
  assert.equal(f.bridge.physicalMode.value, 'unknown')
  assert.equal(f.bridge.sendCmd({ type: 'teleop', payload: { linear: 0.1, angular: 0 } }), false)
  assert.equal(f.topics.filter(x => x.name === '/switch/mode').length, 1)
  f.connect()
  assert.equal(f.topics.filter(x => x.name === '/switch/mode').length, 1)
  f.receiveMode('manual')
  assert.equal(f.bridge.state.value.meta.stale, true)
  assert.equal(f.bridge.physicalMode.value, 'manual')
  assert.equal(f.bridge.sendCmd({ type: 'teleop', payload: { linear: 0.1, angular: 0 } }), true)
  assert.equal(f.sent.at(-1).topic, '/cmd_vel/manual_teleop')
  assert.deepEqual(f.sent.at(-1).msg.linear, { x: 0.1, y: 0, z: 0 })
  assert.equal(f.topics.find(x => x.name === '/cmd_vel/manual_teleop').messageType, 'geometry_msgs/msg/Twist')
  assert.equal(f.bridge.sendCmd({ type: 'lift', payload: { action: 'up' } }), true)
  assert.equal(f.sent.at(-1).topic, '/mcu/fork_cmd')
  assert.equal(f.sent.at(-1).msg.data, 'UP')
  assert.equal(f.topics.find(x => x.name === '/mcu/fork_cmd').messageType, 'std_msgs/msg/String')
  f.receiveMode('auto')
  assert.equal(f.bridge.physicalMode.value, 'auto')
  assert.equal(f.sent.at(-1).topic, '/cmd_vel/manual_teleop')
  assert.equal(f.sent.at(-1).msg.linear.x, 0)
  assert.equal(f.bridge.sendCmd({ type: 'teleop', payload: { linear: 0.1, angular: 0 } }), false)
  assert.equal(f.bridge.sendCmd({ type: 'lift', payload: { action: 'down' } }), false)
  assert.equal(f.bridge.sendCmd({ type: 'teleop', payload: { linear: 0, angular: 0 } }), true)
})
test('disconnect clears mode, reconnect waits for a new direct mode event', t => {
  const f = setup(t); f.connect(); f.receiveMode('manual')
  const oldModeCallback = f.topics.find(x => x.name === '/switch/mode').cb
  f.clients[0].close()
  assert.equal(f.bridge.state.value.meta.stale, true)
  assert.equal(f.bridge.physicalMode.value, 'unknown')
  oldModeCallback({ data: 'manual' })
  assert.equal(f.bridge.physicalMode.value, 'unknown')
  assert.equal(f.bridge.sendCmd({ type: 'teleop', payload: { linear: 0.1 } }), false)
  t.mock.timers.tick(3000); assert.equal(f.clients.length, 2)
  f.connect(); assert.equal(f.bridge.physicalMode.value, 'unknown')
  assert.equal(f.bridge.sendCmd({ type: 'teleop', payload: { linear: 0.1, angular: 0 } }), false)
  f.receiveMode('manual'); assert.equal(f.bridge.physicalMode.value, 'manual')
  t.mock.timers.tick(3000); assert.equal(f.clients.length, 2)
  assert.equal(f.topics.filter(x => x.name === '/ui/state').length, 2)
  assert.equal(f.topics.filter(x => x.name === '/switch/mode').length, 2)
})
test('repeated or malformed frames do not keep stale state live', t => {
  const f = setup(t); f.connect(); f.receiveMode('manual'); f.receiveState()
  t.mock.timers.tick(2100); f.receiveState('manual', 100)
  assert.equal(f.bridge.state.value.meta.stale, true)
  assert.equal(f.bridge.physicalMode.value, 'manual')
  f.receiveMode('bogus'); assert.equal(f.bridge.physicalMode.value, 'manual')
  f.topics.find(x => x.name === '/ui/state').cb({ data: '{bad' })
  assert.equal(f.bridge.state.value.meta.stale, true)
})
test('unmount disconnect sends best-effort zero and never reconnects', t => {
  const f = setup(t); f.connect(); f.receiveMode('manual'); f.bridge.disconnect()
  assert.equal(f.sent.at(-1).topic, '/cmd_vel/manual_teleop')
  assert.deepEqual({ ...f.sent.at(-1).msg }, { linear: { x: 0, y: 0, z: 0 }, angular: { x: 0, y: 0, z: 0 } })
  t.mock.timers.tick(10000); assert.equal(f.clients.length, 1)
})
test('live dispatcher rejects local mode and E-STOP commands', t => {
  const f = setup(t); f.connect(); f.receiveMode('manual')
  for (const type of ['estop', 'estop_ack', 'switch_mode']) assert.equal(f.bridge.sendCmd({ type }), false)
  assert.equal(f.sent.length, 0)
})
