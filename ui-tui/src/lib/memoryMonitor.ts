import { type HeapDumpResult, performHeapDump } from './memory.js'

export type MemoryLevel = 'critical' | 'high' | 'normal'

export interface MemorySnapshot {
  heapUsed: number
  level: MemoryLevel
  rss: number
}

export interface MemoryMonitorOptions {
  criticalBytes?: number
  highBytes?: number
  intervalMs?: number
  onCritical?: (snap: MemorySnapshot, dump: HeapDumpResult | null) => void
  onHigh?: (snap: MemorySnapshot, dump: HeapDumpResult | null) => void
}

const GB = 1024 ** 3

// Deferred @hermes/ink import: loading `@hermes/ink` at module top-level
// pulls the full ~414KB Ink bundle (React, renderer, components, hooks) onto
// the critical path before the Python gateway can even be spawned. That
// serialised roughly 150ms of Node work in front of gw.start() on every
// cold `hermes --tui` launch.
//
// evictInkCaches only runs inside `tick()`, which fires on a 10s timer and
// only when heap pressure crosses the high-water mark — by then Ink has
// long since been loaded by the app entry. This dynamic import is a no-op
// on the hot path (module is already in the ESM cache); when a startup
// spike somehow trips the threshold before the app registers its own Ink
// import, we pay the load cost exactly once, inside the tick that needs it.
let _evictInkCaches: ((level: 'all' | 'half') => unknown) | null = null
let _evictInkCachesPromise: Promise<(level: 'all' | 'half') => unknown> | null = null

async function _ensureEvictInkCaches(): Promise<(level: 'all' | 'half') => unknown> {
  if (_evictInkCaches) {
    return _evictInkCaches
  }

  _evictInkCachesPromise ??= import('@hermes/ink')
    .then(mod => {
      _evictInkCaches = mod.evictInkCaches as (level: 'all' | 'half') => unknown

      return _evictInkCaches
    })
    .catch(err => {
      _evictInkCachesPromise = null
      throw err
    })

  return _evictInkCachesPromise
}

export function startMemoryMonitor({
  criticalBytes = 2.5 * GB,
  highBytes = 1.5 * GB,
  intervalMs = 10_000,
  onCritical,
  onHigh
}: MemoryMonitorOptions = {}): () => void {
  const dumped = new Set<Exclude<MemoryLevel, 'normal'>>()
  const inFlight = new Set<Exclude<MemoryLevel, 'normal'>>()

  // Early-warning state (#34095): the silent-death regime is BELOW `high`, so
  // the level machine above never sees it. Track the previous sample and fire
  // onWarn at most once when heap both crosses a modest absolute floor AND is
  // climbing steeply (≥150MB between 10s ticks) — the signature of a render-
  // tree blowup — so the user gets a visible heads-up before Node OOMs under
  // the exit threshold. Re-armed only after heap falls back below the floor.
  // `lastHeap < 0` marks the un-seeded first sample so a cold start that opens
  // already-high can't be mistaken for sudden growth (growth = current - last).
  let lastHeap = -1
  let warned = false
  const WARN_GROWTH_STEP = 150 * MB

  // Cooldown prevents repeated auto dumps when heap oscillates around the
  // threshold (issue #21767). `dumped` alone is not enough — it clears on
  // every transition back to `normal`.
  const cooldownRaw = process.env.HERMES_AUTO_HEAPDUMP_COOLDOWN_MS?.trim()
  const cooldownParsed = cooldownRaw ? Number(cooldownRaw) : NaN
  const cooldownMs = Number.isFinite(cooldownParsed) && cooldownParsed >= 0 ? cooldownParsed : 600_000
  let lastAutoDumpAt = 0

  const tick = async () => {
    const { heapUsed, rss } = process.memoryUsage()
    const level: MemoryLevel = heapUsed >= criticalBytes ? 'critical' : heapUsed >= highBytes ? 'high' : 'normal'

    if (level === 'normal') {
      dumped.clear()
      return
    }

    if (dumped.has(level) || inFlight.has(level)) {
      return
    }

    if (Date.now() - lastAutoDumpAt < cooldownMs) {
      return
    }

    inFlight.add(level)
    lastAutoDumpAt = Date.now()

    // Prune Ink content caches before dump/exit — half on 'high' (recoverable),
    // full on 'critical' (post-dump RSS reduction, keeps user running).
    // Deferred import keeps `@hermes/ink` off the cold-start critical path;
    // by the time a tick fires 10s after launch the app has already loaded
    // the same module, so this resolves instantly from the ESM cache.
    try {
      try {
        const evictInkCaches = await _ensureEvictInkCaches()
        evictInkCaches(level === 'critical' ? 'all' : 'half')
      } catch {
        // Best-effort: if the dynamic import fails for any reason we still
        // continue to the heap dump below so the user gets diagnostics.
      }

      dumped.add(level)
      const dump = await performHeapDump(level === 'critical' ? 'auto-critical' : 'auto-high').catch(() => null)
      const snap: MemorySnapshot = { heapUsed, level, rss }

      ;(level === 'critical' ? onCritical : onHigh)?.(snap, dump)
    } finally {
      inFlight.delete(level)
    }
  }

  const handle = setInterval(() => void tick(), intervalMs)

  handle.unref?.()

  return () => clearInterval(handle)
}
