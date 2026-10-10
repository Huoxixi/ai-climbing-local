const JPEG_DATA_URL = /^data:(image\/jpeg);base64,([A-Za-z0-9+/=]+)$/

export async function photoSampleFile(source, name, fetchImpl = globalThis.fetch) {
  const inline = JPEG_DATA_URL.exec(source)
  if (inline) {
    const bytes = Uint8Array.from(atob(inline[2]), character => character.charCodeAt(0))
    return new File([bytes], `${name}.jpg`, { type:inline[1] })
  }

  if (typeof source !== 'string' || !source || typeof fetchImpl !== 'function') {
    throw new Error('Invalid photo sample source')
  }

  const response = await fetchImpl(source, { cache:'force-cache' })
  if (!response.ok) throw new Error(`Photo sample unavailable (${response.status})`)
  let blob = await response.blob()
  if (blob.type === 'image/svg+xml') {
    const objectUrl = URL.createObjectURL(blob)
    const bitmap = new Image()
    try {
      await new Promise((resolve, reject) => {
        bitmap.onload = resolve
        bitmap.onerror = () => reject(new Error('Synthetic sample unavailable'))
        bitmap.src = objectUrl
      })
    } finally { URL.revokeObjectURL(objectUrl) }
    const canvas = document.createElement('canvas')
    canvas.width = bitmap.width
    canvas.height = bitmap.height
    canvas.getContext('2d').drawImage(bitmap, 0, 0)
    blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', .92))
    if (!blob) throw new Error('Synthetic sample conversion failed')
  }
  if (blob.type && blob.type !== 'image/jpeg') throw new Error('Invalid photo sample type')
  return new File([blob], `${name}.jpg`, { type:'image/jpeg' })
}
