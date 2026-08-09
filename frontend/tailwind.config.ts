import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#07080D",
        panel: "#0D111C",
        line: "rgba(255, 255, 255, 0.12)",
        signal: "#FF6B00",
        neon: "#FF3D00",
        blue: "#0066FF",
        cyan: "#00F0FF",
        amber: "#F4B75A",
      },
      fontFamily: {
        sans: ["Outfit", "sans-serif"],
        display: ["Space Grotesk", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;