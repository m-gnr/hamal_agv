export function createMockMap() {
  const width = 96, height = 72
  const data = new Array(width * height).fill(-1)
  const set = (x, y, value) => { data[y * width + x] = value }
  for (let y = 8; y < 64; y++) for (let x = 10; x < 86; x++) set(x, y, 0)
  for (let x = 10; x < 86; x++) { set(x, 8, 100); set(x, 63, 100) }
  for (let y = 8; y < 64; y++) { set(10, y, 100); set(85, y, 100) }
  for (let y = 19; y < 50; y++) set(38, y, 100)
  for (let x = 54; x < 76; x++) set(x, 39, 100)
  for (let y = 24; y < 31; y++) for (let x = 63; x < 72; x++) set(x, y, 75)
  return {
    header: { frame_id: 'map' },
    info: { width, height, resolution: 0.05,
      origin: { position: { x: -2.4, y: -1.8, z: 0 }, orientation: { x: 0, y: 0, z: 0, w: 1 } } },
    data,
  }
}
