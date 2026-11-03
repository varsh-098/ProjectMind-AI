import { useEffect, useRef } from 'react'

/**
 * Lightweight animated star band. The canvas is decorative and never captures input.
 */
export default function CosmicStarfield() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d', { alpha: true })
    if (!ctx) return

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    let width = 0, height = 0, dpr = 1, frame = 0
    let stars = []
    const makeStars = () => {
      const count = Math.min(460, Math.max(180, Math.floor(width / 2.8)))
      stars = Array.from({ length: count }, () => {
        const x = Math.random() * width
        const edgeFactor = Math.abs((x / width) - 0.5) * 2
        const y = height * (0.36 + (Math.random() - 0.5) * (0.16 + edgeFactor * 0.20))
        const colorRoll = Math.random()
        return {
          x, y, baseY: y,
          r: Math.random() * 1.15 + 0.2,
          alpha: Math.random() * 0.55 + 0.2,
          phase: Math.random() * Math.PI * 2,
          speed: Math.random() * 0.35 + 0.08,
          drift: (Math.random() - 0.5) * 0.12,
          hue: colorRoll < 0.36 ? 286 : colorRoll < 0.65 ? 195 : colorRoll < 0.82 ? 320 : 220,
          edge: edgeFactor
        }
      })
    }
    const resize = () => {
      width = window.innerWidth
      height = window.innerHeight
      dpr = Math.min(window.devicePixelRatio || 1, 1.6)
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      makeStars()
      if (reduced) draw(0, true)
    }
    const draw = (time, still = false) => {
      ctx.clearRect(0, 0, width, height)
      // Wide, restrained nebula band: brightest toward the sides, cooler through the center.
      const bandY = height * 0.45
      const band = ctx.createLinearGradient(0, bandY - height * 0.15, 0, bandY + height * 0.2)
      band.addColorStop(0, 'rgba(8, 8, 24, 0)')
      band.addColorStop(0.42, 'rgba(37, 21, 70, 0.12)')
      band.addColorStop(0.62, 'rgba(13, 44, 83, 0.13)')
      band.addColorStop(1, 'rgba(4, 6, 18, 0)')
      ctx.fillStyle = band
      ctx.fillRect(0, bandY - height * 0.2, width, height * 0.4)

      for (const s of stars) {
        const t = still ? 0 : time * 0.001
        const twinkle = reduced ? 1 : 0.72 + 0.28 * Math.sin(t * s.speed * 2 + s.phase)
        const x = s.x + (still ? 0 : Math.sin(t * 0.35 + s.phase) * 3)
        const y = s.baseY + (still ? 0 : Math.sin(t * 0.5 + s.phase) * 2)
        const a = s.alpha * twinkle
        ctx.beginPath()
        ctx.fillStyle = `hsla(${s.hue}, 100%, ${s.hue === 195 ? 80 : 78}%, ${a})`
        ctx.shadowBlur = s.r > 0.9 ? 8 : 3
        ctx.shadowColor = `hsla(${s.hue}, 100%, 68%, ${a})`
        ctx.arc(x, y, s.r, 0, Math.PI * 2)
        ctx.fill()
        if (s.r > 1.05 && a > 0.45) {
          ctx.strokeStyle = `hsla(${s.hue}, 100%, 86%, ${a * 0.55})`
          ctx.lineWidth = 0.5
          ctx.beginPath()
          ctx.moveTo(x - 3.2, y); ctx.lineTo(x + 3.2, y)
          ctx.moveTo(x, y - 3.2); ctx.lineTo(x, y + 3.2)
          ctx.stroke()
        }
      }
      ctx.shadowBlur = 0
    }
    const animate = time => {
      draw(time)
      if (!reduced) frame = requestAnimationFrame(animate)
    }
    resize()
    if (!reduced) frame = requestAnimationFrame(animate)
    const onVisibility = () => {
      if (document.hidden) cancelAnimationFrame(frame)
      else if (!reduced) frame = requestAnimationFrame(animate)
    }
    window.addEventListener('resize', resize)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', resize)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return <canvas ref={canvasRef} className="cosmic-starfield" aria-hidden="true" />
}