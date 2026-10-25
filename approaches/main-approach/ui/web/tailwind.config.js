/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ["Manrope", "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      colors: {
        ink: { 950: "#03060d", 900: "#060b16", 850: "#08101f", 800: "#0b1528", 700: "#111d36", 600: "#1a2a4a" },
      },
      keyframes: {
        // ends on `none`: a leftover transform would turn the element into the containing block of fixed children
        "fade-up": { "0%": { opacity: "0", transform: "translateY(12px)" }, "100%": { opacity: "1", transform: "none" } },
        "slide-in": { "0%": { transform: "translateX(100%)" }, "100%": { transform: "translateX(0)" } },
        pop: { "0%": { opacity: "0", transform: "scale(0.5)" }, "100%": { opacity: "1", transform: "scale(1)" } },
        float: { "0%, 100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-10px)" } },
        scan: { "0%": { top: "-20%" }, "100%": { top: "105%" } },
        shimmer: { "0%": { backgroundPosition: "200% 0" }, "100%": { backgroundPosition: "-200% 0" } },
        ripple: { "0%": { transform: "scale(0.4)", opacity: "0.9" }, "100%": { transform: "scale(2.8)", opacity: "0" } },
        dash: { to: { strokeDashoffset: "-32" } },
        typing: { "0%, 80%, 100%": { transform: "translateY(0)", opacity: "0.4" }, "40%": { transform: "translateY(-4px)", opacity: "1" } },
      },
      // keyframes used by plain CSS classes (agent mascot, border beam) live in index.css: Tailwind only emits used utilities
      animation: {
        "fade-up": "fade-up 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) both",
        "slide-in": "slide-in 0.35s cubic-bezier(0.2, 0.8, 0.2, 1) both",
        pop: "pop 0.4s cubic-bezier(0.2, 0.8, 0.2, 1.3) both",
        float: "float 6s ease-in-out infinite",
        scan: "scan 2.6s ease-in-out infinite",
        shimmer: "shimmer 2.4s linear infinite",
        ripple: "ripple 2.2s ease-out infinite",
        dash: "dash 1.2s linear infinite",
        typing: "typing 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
