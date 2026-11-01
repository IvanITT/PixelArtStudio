/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#08090d",
          900: "#0c0e14",
          850: "#10131c",
          800: "#151a24",
          750: "#1a202c",
          700: "#222a38",
          600: "#2e394b",
          500: "#41506a",
          400: "#64748b",
          300: "#8b98ad",
          200: "#b6c0d0",
          100: "#dfe5ef",
          50: "#f2f5fa",
        },
      },
      fontFamily: {
        sans: [
          "Segoe UI",
          "system-ui",
          "-apple-system",
          "Inter",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
        mono: ["Cascadia Mono", "Consolas", "SFMono-Regular", "Menlo", "monospace"],
      },
      boxShadow: {
        panel: "0 18px 50px rgba(0,0,0,0.35)",
        glow: "0 0 0 1px rgba(139,92,246,0.35), 0 0 22px rgba(139,92,246,0.18)",
      },
      keyframes: {
        "fade-in": { from: { opacity: "0", transform: "translateY(4px)" }, to: { opacity: "1", transform: "none" } },
        shimmer: { "0%": { backgroundPosition: "200% 0" }, "100%": { backgroundPosition: "-200% 0" } },
      },
      animation: {
        "fade-in": "fade-in 180ms ease-out",
        shimmer: "shimmer 1.5s linear infinite",
      },
    },
  },
  plugins: [],
};
