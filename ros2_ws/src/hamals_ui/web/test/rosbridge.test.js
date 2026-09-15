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
    publish(msg) { sent.push(msg) }
  }
  class Message { constructor(data) { Object.assign(this, data) } }
  const bridge = useRosbridge('ws://test', { Ros, Topic, Message })
  t.after(() => bridge.disconnect())
  bridge.connect()
  const connect = () => { clients.at(-1).isConnected = true; clients.at(-1).emit('connection') }
  const receive = (mode = 'manual', ts = Date.now() / 1000) => topics.findLast(x => x.name === '/ui/state').cb({ data: JSON.stringify({ meta: { mode: 'live', ts, sources: { '/switch/mode': { age_s: 0 } } }, switch: { mode } }) })
  return { bridge, clients, topics, sent, connect, receive }
}
test('provider sends /ui/cmd with current bridge lease only in manual', t => {
  const f = setup(t); f.connect(); f.receive()
  assert.equal(f.bridge.sendCmd({ type: 'teleop', payload: { linear: 0.1, angular: 0 } }), true)
  assert.equal(JSON.parse(f.sent.at(-1).data).payload.state_ts, 100)
  assert.equal(f.topics.find(x => x.name === '/ui/cmd').reconnect_on_close, false)
  f.receive('auto', 100.1)
  assert.equal(f.bridge.sendCmd({ type: 'teleop', payload: { linear: 0, angular: 0 } }), false)
})
test('disconnect marks stale, reconnect subscribes once and waits for new data', t => {
  const f = setup(t); f.connect(); f.receive()
  f.clients[0].close()
  assert.equal(f.bridge.state.value.meta.stale, true)
  assert.equal(f.bridge.sendCmd({ type: 'teleop', payload: { linear: 0.1 } }), false)
  t.mock.timers.tick(3000); assert.equal(f.clients.length, 2)
  f.connect(); assert.equal(f.bridge.state.value.meta.stale, true)
  f.receive(); assert.equal(f.bridge.state.value.meta.stale, false)
  t.mock.timers.tick(3000); assert.equal(f.clients.length, 2)
  assert.equal(f.topics.filter(x => x.name === '/ui/state').length, 2)
})
test('repeated or malformed frames do not keep stale state live', t => {
  const f = setup(t); f.connect(); f.receive()
  t.mock.timers.tick(2100); f.receive('manual', 100)
  assert.equal(f.bridge.state.value.meta.stale, true)
  f.topics.find(x => x.name === '/ui/state').cb({ data: '{bad' })
  assert.equal(f.bridge.state.value.meta.stale, true)
})
test('unmount disconnect sends best-effort zero and never reconnects', t => {
  const f = setup(t); f.connect(); f.receive(); f.bridge.disconnect()
  assert.deepEqual(JSON.parse(f.sent.at(-1).data).payload, { linear: 0, angular: 0, state_ts: 100 })
  t.mock.timers.tick(10000); assert.equal(f.clients.length, 1)
})
test('live dispatcher rejects local mode and E-STOP commands', t => {
  const f = setup(t); f.connect(); f.receive()
  for (const type of ['estop', 'estop_ack', 'switch_mode']) assert.equal(f.bridge.sendCmd({ type }), false)
  assert.equal(f.sent.length, 0)
})
