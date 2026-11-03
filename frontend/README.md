# ProjectMind AI Frontend — Phase 1

A premium dark cosmic homepage starter built with React, Vite, Three.js, and React Three Fiber.

## Included
- Animated 3D cyan/violet/magenta energy planet with orbital rings
- Persistent canvas starfield with a horizontal cosmic band
- Responsive homepage hero and capabilities section
- Basic interactions and placeholder notices for future phases
- Reduced-motion styling and mobile layout

## Run locally
Requires Node.js 18+ (Node.js 20 LTS recommended).

```bash
npm install
npm run dev
```

Open the local URL printed by Vite, usually http://localhost:5173.

To test a production build:

```bash
npm run build
npm run preview
```

## Integration notes
This is the visual frontend foundation only. Login, authentication, real chat calls, and Python backend integration have intentionally not been implemented yet. The `.env.example` file documents the future API base URL setting.

## Add to an existing repository
Copy this folder's contents into a new `frontend/` directory at the root of your existing ProjectMind-AI-main repository. Do not replace the backend, root requirements.txt, or existing project files.
