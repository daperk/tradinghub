// eslint-disable-next-line @typescript-eslint/triple-slash-reference
/// <reference path="../.astro/types.d.ts" />
/// <reference types="astro/client" />
/// <reference types="vite/client" />
/// <reference types="../vendor/integration/types.d.ts" />

interface ImportMetaEnv {
  readonly PUBLIC_WEB3FORMS_KEY?: string;
  readonly MAILERLITE_API_KEY?: string;
  readonly MAILERLITE_GROUP_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
