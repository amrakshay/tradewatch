export function getPresetRange(preset) {
  const today = new Date()
  const fmt = (d) => d.toISOString().slice(0, 10)

  const offsets = {
    '3m': 90,
    '6m': 180,
    '1y': 365,
    '2y': 730,
  }
  const days = offsets[preset]
  if (!days) return null

  const from = new Date(today)
  from.setDate(from.getDate() - days)
  return { from_date: fmt(from), to_date: fmt(today) }
}
