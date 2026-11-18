-- TEST-ONLY mock: run brace_probe.lua against a fake memreader to exercise every line format.
local mem = {}  -- addr -> byte
local function rdb(a) return mem[a] or 0 end
local function wr(a, s) for i = 1, #s do mem[a + i - 1] = s:byte(i) end end
local function P(n) return { n = n } end
local function addr(p, o) return (type(p) == "table" and p.n or p) + (o or 0) end
local function rd(p, o, n) local t = {} for i = 0, n - 1 do t[#t+1] = string.char(rdb(addr(p, o) + i)) end return table.concat(t) end
local function le(s) local v = 0 for i = #s, 1, -1 do v = v * 256 + s:byte(i) end return v end
local function f32(v) -- encode float roughly via string.pack absence: store as int scaled in a side table
  return v end
local floats = {}
mr = {
  read = function(p, o, n) return rd(p, o, n) end,
  read_pointer = function(p, o) local v = le(rd(p, o, 8)); return P(v) end,
  read_int32 = function(p, o) local v = le(rd(p, o, 4)); if v >= 2^31 then v = v - 2^32 end return v end,
  read_float = function(p, o) return floats[addr(p, o)] or 0 end,
  is_null = function(p) return addr(p) == 0 end,
  tostring = function(p) return string.format("%016X", addr(p)) end,
  ud_topointer = function(u) return P(u.ptr) end,
  write = function(p, o, s) wr(addr(p, o), s) end,
  uint32 = function(v) return string.char(v % 256, math.floor(v/256)%256, math.floor(v/65536)%256, math.floor(v/16777216)%256) end,
  game_alloc = function(n) return P(0x10000000) end,
  patcher = function(owner) return { sites = function(self, entries, cb)
      return { found = function() return true end, why = function() return "" end, cave_value = function() return nil end,
               install_feature = function() return true end } end } end,
}
_G.memreader_plus = mr
local function setp(a, v) wr(a, mr.uint32(v % 2^32) .. mr.uint32(math.floor(v / 2^32))) end
-- unit obj at 0x2000: +0xa4 count, +0xa8 data -> 0x3000 list of models
local function mkunit(uptr, models)
  wr(uptr + 0xa4, mr.uint32(#models)); setp(uptr + 0xa8, uptr + 0x800)
  for i, m in ipairs(models) do setp(uptr + 0x800 + (i-1)*8, m) end
end
-- flyer: model 0x50000 riding? no: single entity with +0x128 non-null
setp(0x50000 + 0x128, 0x9999); wr(0x50000 + 0x104, mr.uint32(0)); wr(0x50000 + 0x26c, mr.uint32(33)); wr(0x50000 + 0x6c, mr.uint32(0x10000))
floats[0x50000 + 0x88] = 1; floats[0x50000 + 0x90] = 1; floats[0x50000 + 0xe8] = -10
setp(0x50000 + 0x330, 0x143ADE800); setp(0x50000 + 0x368, 0x60000)
mkunit(0x2000, { 0x50000 })
local sold = {}
for i = 0, 5 do local s = 0x60000 + i * 0x1000; sold[#sold+1] = s; floats[s + 0x88] = 1 + i; floats[s + 0x90] = 0; wr(s + 0x68, string.char(8)); wr(s + 0x6c, mr.uint32(0x10000)); floats[s + 0xbc] = 4 end
mkunit(0x4000, sold)
-- refl ring entry
local site = dofile("brace_probe_site.lua")
local L = site.layout
local base = 0x10000000
local cbs, phase = {}, {}
local function units(list) return { count = function() return #list end, item = function(_, i) return list[i] end } end
local u1 = { ptr = 0x7000, unique_ui_id = function() return 1002 end }
local u2 = { ptr = 0x7100, unique_ui_id = function() return 1006 end }
setp(0x7000 + 8, 0x2000); setp(0x7100 + 8, 0x4000)
local all = units({ { armies = function() return units({ { units = function() return units({ u1 }) end } }) end },
                     { armies = function() return units({ { units = function() return units({ u2 }) end } }) end } })
local t = 0
bm = { is_multiplayer = function() return false end, alliances = function() return all end,
  time_elapsed_ms = function() return t end,
  register_phase_change_callback = function(_, n, f) phase[n] = f end,
  repeat_callback = function(_, f) cbs[1] = f end, remove_callback = function() end }
package.preload["script/ld_brace_probe/brace_probe_site"] = function() return site end
dofile("brace_probe.lua")
phase.Deployed()
-- fake one refl + one act entry
wr(base + L.refl_count_at, mr.uint32(1)); setp(base + L.refl_ring_at, 0x60000); setp(base + L.refl_ring_at + 8, 0x50000)
for i = 1, 3 do t = t + 1100; cbs[1]() end
phase.Complete()
