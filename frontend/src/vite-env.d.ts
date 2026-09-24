/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** RepoPilot API origin, e.g. http://localhost:8000. Empty: same origin (dev/preview proxy). */
  readonly VITE_API_BASE_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
