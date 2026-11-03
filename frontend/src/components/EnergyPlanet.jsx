import { useMemo, useRef } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

/**
 * Glass energy orb with fluid ribbons and natural, wispy orbital trails.
 * The trails are intentionally incomplete, irregular, tapered arcs—not closed torus rings.
 */

function FlowingRibbon({
  radius = 0.78,
  color = '#ff70dc',
  secondaryColor = '#64eaff',
  phase = 0,
  speed = 0.16,
  thickness = 0.014,
  vertical = 0.24,
  wave = 0.055,
}) {
  const meshRef = useRef()
  const geometry = useMemo(() => {
    const points = []
    const count = 300
    for (let i = 0; i <= count; i++) {
      const t = (i / count) * Math.PI * 2
      const r = radius + Math.sin(t * 3 + phase) * wave * 0.5
      points.push(new THREE.Vector3(
        Math.cos(t + phase * 0.16) * r,
        Math.sin(t * 2 + phase) * vertical + Math.sin(t * 3.5 + phase) * 0.045,
        Math.sin(t + phase * 0.16) * r
      ))
    }
    return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points, true, 'centripetal'), 300, thickness, 8, true)
  }, [radius, phase, thickness, vertical, wave])

  const material = useMemo(() => new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: {
      uTime: { value: 0 },
      uColorA: { value: new THREE.Color(color) },
      uColorB: { value: new THREE.Color(secondaryColor) },
      uPhase: { value: phase },
      uWave: { value: wave },
    },
    vertexShader: `
      uniform float uTime;
      uniform float uPhase;
      uniform float uWave;
      varying vec3 vNormal;
      varying vec3 vPosition;
      varying float vFlow;
      void main() {
        vec3 p = position;
        float a = sin(p.x * 7.0 + p.z * 4.0 + uTime * 1.5 + uPhase);
        float b = sin(p.y * 9.0 - uTime * 1.1 + uPhase * 1.7);
        float c = sin((p.x + p.z) * 11.0 + uTime * 0.8);
        p += normal * ((a * 0.55 + b * 0.3 + c * 0.15) * uWave);
        vNormal = normalize(normalMatrix * normal);
        vPosition = p;
        vFlow = 0.5 + 0.5 * sin(uTime * 0.75 + p.x * 3.5 + p.z * 2.0 + uPhase);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform vec3 uColorA;
      uniform vec3 uColorB;
      varying vec3 vNormal;
      varying vec3 vPosition;
      varying float vFlow;
      void main() {
        float edge = pow(1.0 - abs(normalize(vNormal).z), 1.6);
        float flow = 0.5 + 0.5 * sin(uTime * 1.8 + vPosition.x * 5.0 - vPosition.y * 3.0);
        vec3 color = mix(uColorA, uColorB, clamp(flow * 0.7 + vFlow * 0.3, 0.0, 1.0));
        gl_FragColor = vec4(color * (0.72 + edge * 0.7), 0.52 + flow * 0.38);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }
    `,
  }), [color, secondaryColor, phase, wave])

  useFrame((_, delta) => {
    material.uniforms.uTime.value += delta
    if (meshRef.current) {
      meshRef.current.rotation.y += delta * speed
      meshRef.current.rotation.x += delta * speed * 0.21
    }
  })

  return <mesh ref={meshRef} geometry={geometry} material={material} />
}

/** An incomplete, slightly lopsided orbital stream with a tapered glow. */
function NaturalOrbit({ radius, color, phase, speed, tilt, arc = 1.62, thickness = 0.006, opacity = 0.72 }) {
  const ref = useRef()
  const materialRef = useRef()

  const geometry = useMemo(() => {
    const points = []
    const count = 230
    const start = phase
    const span = Math.PI * 2 * arc
    for (let i = 0; i <= count; i++) {
      const u = i / count
      const t = start + span * u
      // Uneven radius and a shallow vertical wave stop the path looking like a perfect torus.
      const wobble = 1 + 0.11 * Math.sin(t * 1.7 + phase) + 0.045 * Math.sin(t * 4.3 + phase * 1.4)
      const x = Math.cos(t) * radius * wobble
      const z = Math.sin(t) * radius * (0.74 + 0.13 * Math.sin(t * 1.3 + phase))
      const y = 0.27 * Math.sin(t * 1.15 + phase) + 0.12 * Math.sin(t * 2.4 + phase * 0.7)
      points.push(new THREE.Vector3(x, y, z))
    }
    return new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points, false, 'centripetal'), 230, thickness, 6, false)
  }, [radius, phase, arc, thickness])

  const material = useMemo(() => new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: {
      uColor: { value: new THREE.Color(color) },
      uOpacity: { value: opacity },
      uTime: { value: 0 },
    },
    vertexShader: `
      varying vec2 vUv;
      varying vec3 vNormal;
      void main() {
        vUv = uv;
        vNormal = normalize(normalMatrix * normal);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 uColor;
      uniform float uOpacity;
      uniform float uTime;
      varying vec2 vUv;
      varying vec3 vNormal;
      void main() {
        float endFade = smoothstep(0.0, 0.13, vUv.x) * (1.0 - smoothstep(0.84, 1.0, vUv.x));
        float softEdge = 0.68 + 0.32 * abs(normalize(vNormal).z);
        float shimmer = 0.70 + 0.30 * sin(vUv.x * 28.0 - uTime * 1.6);
        float alpha = endFade * softEdge * shimmer * uOpacity;
        gl_FragColor = vec4(uColor * (0.85 + shimmer * 0.6), alpha);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }
    `,
  }), [color, opacity])

  useFrame((state, delta) => {
    material.uniforms.uTime.value += delta
    if (!ref.current) return
    ref.current.rotation.y += delta * speed
    ref.current.rotation.z += delta * speed * 0.19
    ref.current.rotation.x += ((tilt[0] + state.pointer.y * 0.07) - ref.current.rotation.x) * 0.018
    ref.current.rotation.y += ((tilt[1] + state.pointer.x * 0.08) - ref.current.rotation.y) * 0.018
  })

  return (
    <group ref={ref} rotation={tilt}>
      {/* Soft broad underglow, then the fine luminous strand. */}
      <mesh geometry={geometry}>
        <meshBasicMaterial color={color} transparent opacity={opacity * 0.12} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>
      <mesh geometry={geometry} material={material} />
    </group>
  )
}

function GlassOrb() {
  const root = useRef()
  const shell = useRef()
  const coreGlow = useRef()

  useFrame((state, delta) => {
    if (!root.current) return
    const { pointer, clock } = state
    root.current.rotation.y += delta * 0.105
    root.current.rotation.x += ((-pointer.y * 0.13) - root.current.rotation.x) * 0.035
    root.current.rotation.z += ((pointer.x * 0.055) - root.current.rotation.z) * 0.025
    root.current.position.x += (pointer.x * 0.10 - root.current.position.x) * 0.025
    root.current.position.y += (pointer.y * 0.07 - root.current.position.y) * 0.025

    if (shell.current) {
      shell.current.rotation.y -= delta * 0.065
      shell.current.rotation.x = Math.sin(clock.elapsedTime * 0.22) * 0.025
    }
    if (coreGlow.current) {
      coreGlow.current.material.opacity = 0.12 + (Math.sin(clock.elapsedTime * 1.25) + 1) * 0.025
    }
  })

  return (
    <group ref={root}>
      <pointLight position={[1.8, 1.5, 2.2]} intensity={2.7} color="#68eaff" distance={5} />
      <pointLight position={[-1.7, -0.8, 1.8]} intensity={2.6} color="#b85cff" distance={5} />
      <pointLight position={[0.3, 1.7, -1.8]} intensity={2.0} color="#ff63d8" distance={5} />
      <pointLight position={[0.4, -1.4, 1.2]} intensity={1.0} color="#ff9b58" distance={4} />

      <mesh>
        <sphereGeometry args={[0.83, 96, 96]} />
        <meshPhysicalMaterial color="#08051e" metalness={0.48} roughness={0.19} clearcoat={1} clearcoatRoughness={0.08} emissive="#281064" emissiveIntensity={0.38} />
      </mesh>

      <mesh ref={shell} scale={1.025}>
        <sphereGeometry args={[0.83, 96, 96]} />
        <meshPhysicalMaterial color="#8171ff" metalness={0.08} roughness={0.11} transmission={0.62} thickness={0.22} ior={1.28} transparent opacity={0.30} clearcoat={1} clearcoatRoughness={0.06} emissive="#6c31ff" emissiveIntensity={0.25} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>

      <mesh scale={1.012}>
        <sphereGeometry args={[0.83, 72, 72]} />
        <meshBasicMaterial color="#8b70ff" wireframe transparent opacity={0.045} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>

      <mesh ref={coreGlow} scale={0.77}>
        <sphereGeometry args={[0.83, 48, 48]} />
        <meshBasicMaterial color="#4c23b8" transparent opacity={0.15} blending={THREE.AdditiveBlending} depthWrite={false} />
      </mesh>

      <FlowingRibbon radius={0.80} color="#50eaff" secondaryColor="#a3dfff" phase={0.2} speed={0.11} thickness={0.017} vertical={0.27} wave={0.075} />
      <FlowingRibbon radius={0.72} color="#e95cff" secondaryColor="#ff8fe9" phase={2.0} speed={-0.13} thickness={0.014} vertical={0.33} wave={0.085} />
      <FlowingRibbon radius={0.66} color="#ff7a50" secondaryColor="#ffc078" phase={4.0} speed={0.09} thickness={0.012} vertical={0.24} wave={0.07} />
      <FlowingRibbon radius={0.84} color="#9b69ff" secondaryColor="#54dfff" phase={5.1} speed={-0.075} thickness={0.009} vertical={0.36} wave={0.06} />

      {/* Natural orbit trails: partial arcs, variable paths, tapered ends, varied depth and speed. */}
      <NaturalOrbit radius={1.02} color="#f08bfa" phase={0.25} speed={0.12} tilt={[1.02, 0.22, 0.24]} arc={0.34} thickness={0.0048} opacity={0.70} />
      <NaturalOrbit radius={1.16} color="#67eaff" phase={2.1} speed={-0.082} tilt={[0.70, -0.32, -0.17]} arc={0.29} thickness={0.0038} opacity={0.62} />
      <NaturalOrbit radius={1.25} color="#a58aff" phase={4.15} speed={0.052} tilt={[1.08, 0.14, 0.08]} arc={0.37} thickness={0.0032} opacity={0.53} />
      <NaturalOrbit radius={1.09} color="#ffad7b" phase={5.25} speed={-0.061} tilt={[0.55, 0.47, 0.32]} arc={0.25} thickness={0.0028} opacity={0.43} />
    </group>
  )
}

function OrbScene() {
  const parallax = useRef()
  useFrame((state) => {
    if (!parallax.current) return
    parallax.current.rotation.y += (state.pointer.x * 0.025 - parallax.current.rotation.y) * 0.02
    parallax.current.rotation.x += (-state.pointer.y * 0.018 - parallax.current.rotation.x) * 0.02
  })
  return (
    <>
      <ambientLight intensity={0.35} />
      <group ref={parallax}>
        <GlassOrb />
      </group>
    </>
  )
}

export default function EnergyPlanet({ className = '' }) {
  return (
    <div className={`energy-planet ${className}`}>
      <div className="planet-aura" />
      <Canvas camera={{ position: [0, 0, 3.65], fov: 40 }} dpr={[1, 1.5]} gl={{ alpha: true, antialias: true, powerPreference: 'high-performance' }} fallback={<div className="planet-fallback" aria-label="Glass energy orb" />}>
        <OrbScene />
      </Canvas>
    </div>
  )
}
