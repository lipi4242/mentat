/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Instance title (from the instance file, via `config/instance.mjs render`). */
  readonly VITE_INSTANCE_TITLE?: string;
  readonly VITE_API_URL?: string;
}
