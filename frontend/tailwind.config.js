/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{html,ts}"],
  theme: {
    extend: {
      colors: {
        threat: {
          low: "#16a34a",
          med: "#f59e0b",
          high: "#ef4444",
          critical: "#991b1b",
        },
      },
    },
  },
  plugins: [],
};
