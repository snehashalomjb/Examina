import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    rules: {
      // Every page in this app loads its data on mount and stores it in state; the
      // setState always happens in a promise continuation, not synchronously in the
      // effect body, but the rule traces into the called loader and flags it anyway.
      // Kept as a warning so genuine synchronous-setState mistakes still surface.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
]);

export default eslintConfig;
