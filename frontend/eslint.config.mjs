import nextPlugin from "eslint-config-next";

export default [
  ...nextPlugin,
  {
    ignores: [".next/**", "node_modules/**"],
  },
];
