/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        // Certivity sets Roobert (commercial); Hanken Grotesk is the closest free grotesk
        sans: ["Hanken Grotesk", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
      colors: {
        // certivity.io palette
        mint: {
          50: "#f0fdfa",
          100: "#cafdf2",
          200: "#96f9e5",
          300: "#79f2de",
          400: "#27dac2",
          500: "#0ebea9",
          600: "#08998b",
          700: "#0b7a70",
          800: "#0c635b",
          900: "#11504b",
          950: "#02312f",
        },
        flat: { white: "#f0f0f0", black: "#151516" },
      },
      fontSize: {
        huge: ["clamp(2.25rem, 1.4rem + 3.2vw, 4rem)", { lineHeight: "1.05", letterSpacing: "-0.02em" }],
      },
      boxShadow: {
        card: "0 1px 2px rgba(2, 49, 47, 0.04), 0 8px 24px -16px rgba(2, 49, 47, 0.18)",
        lift: "0 2px 4px rgba(2, 49, 47, 0.05), 0 24px 48px -24px rgba(2, 49, 47, 0.35)",
      },
      keyframes: {
        // ends on `none`: a leftover transform would turn the element into the containing block of fixed children
        "fade-up": { "0%": { opacity: "0", transform: "translateY(10px)" }, "100%": { opacity: "1", transform: "none" } },
        "slide-in": { "0%": { transform: "translateX(100%)" }, "100%": { transform: "translateX(0)" } },
        scan: { "0%": { top: "-20%" }, "100%": { top: "105%" } },
        shimmer: { "0%": { backgroundPosition: "200% 0" }, "100%": { backgroundPosition: "-200% 0" } },
        dash: { to: { strokeDashoffset: "-32" } },
        typing: { "0%, 80%, 100%": { transform: "translateY(0)", opacity: "0.4" }, "40%": { transform: "translateY(-4px)", opacity: "1" } },
      },
      // keyframes used by plain CSS classes (agent mascot, ripples) live in index.css: Tailwind only emits used utilities
      animation: {
        "fade-up": "fade-up 0.45s cubic-bezier(0.2, 0.8, 0.2, 1) both",
        "slide-in": "slide-in 0.3s cubic-bezier(0.2, 0.8, 0.2, 1) both",
        scan: "scan 2.6s ease-in-out infinite",
        shimmer: "shimmer 2.4s linear infinite",
        dash: "dash 1.2s linear infinite",
        typing: "typing 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
