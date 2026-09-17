import test from 'node:test'
import assert from 'node:assert/strict'
import { EventEmitter } from 'node:events'
import { useRosbridge } from '../src/composables/useRosbridge.js'

function setup(t) {
  t.mock.timers.enable({ apis: ['setTimeout', 'setInterval', 'Date'], now: 100000 })
  const clients = [], topics = [], sent = [], services = []
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
  class Service {
    constructor(options) { Object.assign(this, options); services.push(this) }
    callService(request, success, failure) { this.request = request; this.success = success; this.failure = failure }
  }
  class ServiceRequest { constructor(data) { Object.assign(this, data) } }
  const bridge = useRosbridge('ws://test', { Ros, Topic, Message, Service, ServiceRequest })
  t.after(() => bridge.disconnect())
  bridge.connect()
  const connect = () => { clients.at(-1).isConnected = true; clients.at(-1).emit('connection') }
  const receiveMode = mode => topics.findLast(x => x.name === '/switch/mode').cb({ data: mode })
  const receiveState = (mode = 'manual', ts = Date.now() / 1000) => topics.findLast(x => x.name === '/ui/state').cb({ data: JSON.stringify({ meta: { mode: 'live', ts, sources: { '/switch/mode': { age_s: 0 } } }, switch: { mode } }) })
  return { bridge, clients, topics, sent, services, connect, receiveMode, receiveState }
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
test('/map subscribes once per connection and survives missing /ui/state', t => {
  const f = setup(t); f.connect()
  const maps = f.topics.filter(x => x.name === '/map')
  assert.equal(maps.length, 1)
  assert.equal(maps[0].messageType, 'nav_msgs/msg/OccupancyGrid')
  const message = { header: { frame_id: 'map' }, info: { width: 1, height: 1, resolution: 0.05 }, data: [100] }
  maps[0].cb(message)
  assert.equal(f.bridge.mapFeed.latest, message)
  assert.equal(f.bridge.state.value.meta.stale, true)
  f.clients[0].close()
  assert.equal(maps[0].cb, null)
  assert.equal(f.bridge.mapFeed.latest, message)
  t.mock.timers.tick(3000); f.connect()
  assert.equal(f.topics.filter(x => x.name === '/map').length, 2)
})

test('save requires a current /map, ignores stale /ui/state, and prevents concurrent calls', async t => {
  const f = setup(t); f.connect()
  assert.equal(f.bridge.mapReady.value, false)
  assert.equal((await f.bridge.saveMap()).success, false)
  assert.equal(f.services.length, 0)
  f.topics.find(x => x.name === '/map').cb({ info: { width: 1, height: 1, resolution: 0.05 }, data: [0] })
  assert.equal(f.bridge.state.value.meta.stale, true)
  assert.equal(f.bridge.mapReady.value, true)
  const pending = f.bridge.saveMap()
  assert.equal(f.bridge.savePending.value, true)
  assert.equal(f.services[0].name, '/map/save')
  assert.equal(f.services[0].serviceType, 'std_srvs/srv/Trigger')
  assert.deepEqual({ ...f.services[0].request }, {})
  assert.equal((await f.bridge.saveMap()).success, false)
  assert.equal(f.services.length, 1)
  f.services[0].success({ success: true, message: 'saved' })
  assert.equal((await pending).success, true)
  assert.equal(f.bridge.savePending.value, false)
  f.clients[0].close()
  assert.equal(f.bridge.mapReady.value, false)
  assert.equal((await f.bridge.saveMap()).success, false)
})

test('save errors and disconnect release the pending state', async t => {
  const f = setup(t); f.connect()
  f.topics.find(x => x.name === '/map').cb({ info: { width: 1, height: 1, resolution: 0.05 }, data: [0] })
  let pending = f.bridge.saveMap()
  f.services[0].success({ success: false, message: 'disk full' })
  assert.deepEqual(await pending, { success: false, message: 'disk full' })
  pending = f.bridge.saveMap()
  f.clients[0].close()
  assert.match((await pending).message, /bağlantısı kesildi/)
  assert.equal(f.bridge.savePending.value, false)
})

test('direct PLC and mission topics have one subscription per connection and ignore stale UI snapshots', t => {
  const f = setup(t); f.connect()
  const plc = f.topics.findLast(x => x.name === '/plc/state')
  const mission = f.topics.findLast(x => x.name === '/mission/state')
  assert.equal(f.topics.filter(x => x.name === '/plc/state').length, 1)
  assert.equal(f.topics.filter(x => x.name === '/mission/state').length, 1)
  assert.equal(plc.messageType, 'hamals_interfaces/msg/PlcState')
  assert.equal(mission.messageType, 'hamals_interfaces/msg/MissionState')
  plc.cb({ connection_state: 2, transport: 'udp', rx_control: 1 })
  mission.cb({ state: 8, phase: 'MOVE_EMPTY' })
  assert.equal(f.bridge.state.value.meta.stale, true)
  assert.equal(f.bridge.plcState.value.rx_control, 1)
  assert.equal(f.bridge.missionState.value.state, 8)
  assert.equal(f.bridge.sendCmd({ type: 'start_mission' }), false)
  const oldPlcCallback = plc.cb
  f.clients[0].close()
  assert.equal(plc.cb, null)
  assert.equal(mission.cb, null)
  assert.equal(f.bridge.plcState.value, null)
  assert.equal(f.bridge.missionState.value, null)
  oldPlcCallback({ connection_state: 2 })
  assert.equal(f.bridge.plcState.value, null)
  t.mock.timers.tick(3000); f.connect()
  assert.equal(f.topics.filter(x => x.name === '/plc/state').length, 2)
  assert.equal(f.topics.filter(x => x.name === '/mission/state').length, 2)
})
