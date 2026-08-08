import type { Config } from "tailwindcss";
const config: Config = { content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"], theme: { extend: { colors: { ink: "#0a0d11", panel: "#11161c", line: "#28313b", signal: "#ef4d4d", cyan: "#62d5d0", amber: "#f4b75a" }, fontFamily: { sans: ["var(--font-inter)"] } } }, plugins: [] };
export default config;
