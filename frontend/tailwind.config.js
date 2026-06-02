/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "mst-dark": "#0a0d14",
        "mst-darker": "#070a10",
        "mst-cyan": "#00D4FF",
        "mst-navy": "#0f1729",
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "Cascadia Code", "Consolas", "ui-monospace", "monospace"],
      },
      animation: {
        bounce: "bounce 0.8s infinite",
      },
    },
  },
  plugins: [
    require("@tailwindcss/typography"),
  ],
};
