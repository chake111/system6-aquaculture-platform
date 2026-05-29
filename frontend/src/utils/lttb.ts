export interface Point {
  x: string
  y: number
}

/**
 * Largest Triangle Three Buckets downsampling.
 * Uses index as x-axis for area calculation (suitable for time-series).
 */
export function lttb(data: Point[], threshold: number): Point[] {
  if (data.length <= threshold || threshold < 3) return data

  const result: Point[] = [data[0]!]
  const bucketSize = (data.length - 2) / (threshold - 2)

  let prevIndex = 0

  for (let i = 1; i < threshold - 1; i++) {
    const bucketStart = Math.floor((i - 1) * bucketSize) + 1
    const bucketEnd = Math.min(Math.floor(i * bucketSize) + 1, data.length - 1)
    const nextBucketStart = Math.floor(i * bucketSize) + 1
    const nextBucketEnd = Math.min(Math.floor((i + 1) * bucketSize) + 1, data.length - 1)

    // average of next bucket
    let avgX = 0
    let avgY = 0
    let nextCount = 0
    for (let j = nextBucketStart; j < nextBucketEnd; j++) {
      avgX += j
      avgY += data[j]!.y
      nextCount++
    }
    if (nextCount > 0) {
      avgX /= nextCount
      avgY /= nextCount
    }

    // pick point in current bucket with largest triangle area
    const prevY = data[prevIndex]!.y
    let maxArea = -1
    let maxIndex = bucketStart

    for (let j = bucketStart; j < bucketEnd; j++) {
      const area = Math.abs(
        (prevIndex - avgX) * (data[j]!.y - prevY) - (prevIndex - j) * (avgY - prevY),
      )
      if (area > maxArea) {
        maxArea = area
        maxIndex = j
      }
    }

    result.push(data[maxIndex]!)
    prevIndex = maxIndex
  }

  result.push(data[data.length - 1]!)
  return result
}
