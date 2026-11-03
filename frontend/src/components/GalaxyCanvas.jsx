import { useEffect, useRef } from 'react'

/**
 * Interactive particle galaxy inspired by the supplied video.
 * Pointer movement gently bends the galaxy and influences nearby particles.
 */
export default function GalaxyCanvas({ className = '' }) {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas?.getContext('2d', { alpha: true })
    if (!canvas || !ctx) return

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    const pointer = { x: 0, y: 0, tx: 0, ty: 0, active: false }
    let width = 0, height = 0, dpr = 1, frame = 0, lastTime = 0
    let particles = []
    let centerX = 0, centerY = 0
    const arms = 3
    const TAU = Math.PI * 2

    const makeParticles = () => {
      const count = Math.min(2600, Math.max(1050, Math.floor((width * height) / 520)))
      particles = []
      for (let i = 0; i < count; i++) {
        const arm = i % arms
        const radius = Math.pow(Math.random(), 0.72) * Math.min(width * 0.34, height * 0.52)
        const spin = radius * 0.012
        const angle = (arm / arms) * TAU + spin + (Math.random() - 0.5) * (0.26 + radius * 0.0007)
        const spread = 0.7 + radius * 0.018
        const roll = Math.random()
        particles.push({
          radius,
          angle,
          arm,
          offsetX: (Math.random() - 0.5) * spread,
          offsetY: (Math.random() - 0.5) * spread * 0.72,
          size: Math.random() < 0.06 ? Math.random() * 1.7 + 1 : Math.random() * 0.9 + 0.2,
          alpha: Math.random() * 0.62 + 0.18,
          phase: Math.random() * TAU,
          twinkle: Math.random() * 1.4 + 0.25,
          hue: roll < 0.12 ? 34 : roll < 0.30 ? 205 : roll < 0.43 ? 220 : 0,
          warm: roll < 0.12,
          z: Math.random() * 2 - 1
        })
      }
    }

    const resize = () => {
      width = window.innerWidth
      height = window.innerHeight
      centerX = width * 0.5
      centerY = height * 0.47
      dpr = Math.min(window.devicePixelRatio || 1, width < 700 ? 1.25 : 1.7)
      canvas.width = Math.floor(width * dpr)
      canvas.height = Math.floor(height * dpr)
      canvas.style.width = `${width}px`
      canvas.style.height = `${height}px`
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      makeParticles()
      if (reducedMotion) draw(0, 0.016, true)
    }

    const draw = (time, delta, still = false) => {
      ctx.clearRect(0, 0, width, height)
      const t = still ? 0 : time * 0.00016
      pointer.x += (pointer.tx - pointer.x) * (still ? 0 : 0.045)
      pointer.y += (pointer.ty - pointer.y) * (still ? 0 : 0.045)
      const mouseX = pointer.x * width
      const mouseY = pointer.y * height
      const tiltX = pointer.active ? (pointer.x - 0.5) * 0.15 : 0
      const tiltY = pointer.active ? (pointer.y - 0.5) * 0.10 : 0

      // Soft central nebula and a restrained core glow.
      const coreRadius = Math.min(width, height) * 0.22
      const glow = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, coreRadius)
      glow.addColorStop(0, 'rgba(205, 224, 255, 0.12)')
      glow.addColorStop(0.12, 'rgba(113, 154, 255, 0.09)')
      glow.addColorStop(0.42, 'rgba(68, 89, 173, 0.045)')
      glow.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.fillStyle = glow
      ctx.fillRect(centerX - coreRadius, centerY - coreRadius, coreRadius * 2, coreRadius * 2)

      // Render far stars first, then the denser spiral arms.
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i]
        const spin = t * (p.warm ? 0.2 : 0.13)
        const angle = p.angle + spin * (0.45 + p.radius / Math.min(width, height))
        const depthScale = 0.82 + (p.z + 1) * 0.11
        const spiralR = p.radius * depthScale
        let x = centerX + Math.cos(angle) * spiralR * (1 + tiltX) + p.offsetX
        let y = centerY + Math.sin(angle) * spiralR * (0.58 + tiltY) + p.offsetY

        // Pointer interaction: nearby particles bend away gently, creating a responsive fluid field.
        if (pointer.active && !still) {
          const dx = x - mouseX
          const dy = y - mouseY
          const distSq = dx * dx + dy * dy
          const influence = Math.max(0, 1 - distSq / (155 * 155))
          if (influence > 0) {
            const dist = Math.sqrt(distSq) || 1
            const push = influence * 18
            x += (dx / dist) * push + (dy / dist) * influence * 5
            y += (dy / dist) * push - (dx / dist) * influence * 5
          }
        }

        const twinkle = reducedMotion ? 0.86 : 0.70 + 0.30 * Math.sin(t * p.twinkle * 9 + p.phase)
        const alpha = Math.min(1, p.alpha * twinkle)
        const color = p.warm
          ? `rgba(255, ${190 + Math.floor(40 * twinkle)}, ${145 + Math.floor(50 * twinkle)}, ${alpha})`
          : p.hue === 205
            ? `rgba(130, 205, 255, ${alpha})`
            : p.hue === 220
              ? `rgba(185, 211, 255, ${alpha})`
              : `rgba(235, 241, 255, ${alpha})`
        ctx.beginPath()
        ctx.fillStyle = color
        ctx.shadowBlur = p.size > 1.2 ? 8 : 3
        ctx.shadowColor = p.warm ? 'rgba(255, 181, 125, .8)' : 'rgba(151, 199, 255, .75)'
        ctx.arc(x, y, p.size * (p.warm ? 0.92 : 1), 0, TAU)
        ctx.fill()

        if (p.size > 1.55 && alpha > 0.54) {
          ctx.strokeStyle = p.warm ? `rgba(255, 218, 177, ${alpha * 0.48})` : `rgba(205, 228, 255, ${alpha * 0.42})`
          ctx.lineWidth = 0.55
          ctx.beginPath()
          ctx.moveTo(x - p.size * 2.1, y)
          ctx.lineTo(x + p.size * 2.1, y)
          ctx.moveTo(x, y - p.size * 2.1)
          ctx.lineTo(x, y + p.size * 2.1)
          ctx.stroke()
        }
      }
      ctx.shadowBlur = 0

      // The bright core remains soft, never a hard white disc.
      const core = ctx.createRadialGradient(centerX, centerY, 0, centerX, centerY, Math.min(width, height) * 0.075)
      core.addColorStop(0, 'rgba(245, 249, 255, 0.17)')
      core.addColorStop(0.22, 'rgba(194, 218, 255, 0.09)')
      core.addColorStop(1, 'rgba(110, 145, 255, 0)')
      ctx.fillStyle = core
      ctx.fillRect(centerX - 100, centerY - 100, 200, 200)
    }

    const animate = time => {
      if (!lastTime) lastTime = time
      const delta = Math.min((time - lastTime) / 1000, 0.04)
      lastTime = time
      draw(time, delta)
      if (!reducedMotion && !document.hidden) frame = requestAnimationFrame(animate)
    }

    const onPointerMove = e => {
      pointer.tx = e.clientX / Math.max(1, width)
      pointer.ty = e.clientY / Math.max(1, height)
      pointer.active = true
    }
    const onPointerLeave = () => { pointer.active = false; pointer.tx = 0.5; pointer.ty = 0.5 }
    const onVisibility = () => {
      cancelAnimationFrame(frame)
      if (!document.hidden && !reducedMotion) {
        lastTime = 0
        frame = requestAnimationFrame(animate)
      }
    }

    resize()
    if (!reducedMotion) frame = requestAnimationFrame(animate)
    window.addEventListener('resize', resize)
    window.addEventListener('pointermove', onPointerMove, { passive: true })
    document.documentElement.addEventListener('pointerleave', onPointerLeave)
    document.addEventListener('visibilitychange', onVisibility)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', resize)
      window.removeEventListener('pointermove', onPointerMove)
      document.documentElement.removeEventListener('pointerleave', onPointerLeave)
      document.removeEventListener('visibilitychange', onVisibility)
    }
  }, [])

  return <div className={`galaxy-wrap ${className}`} aria-label="Interactive animated spiral galaxy">
    <canvas ref={canvasRef} className="galaxy-canvas" />
  </div>
}
