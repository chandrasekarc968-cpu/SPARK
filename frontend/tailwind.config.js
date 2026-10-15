/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        scada: {
          bg: '#070A12',
          surface: '#0E1322',
          card: '#141B30',
          border: '#1F2942',
          accent: '#06B6D4',     // Cyan
          success: '#10B981',    // Emerald
          warning: '#F59E0B',    // Amber
          danger: '#EF4444',     // Crimson
          purple: '#8B5CF6',     // Violet
        }
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', 'Consolas', 'monospace'],
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow-cyan': '0 0 20px -3px rgba(6, 182, 212, 0.45)',
        'glow-danger': '0 0 20px -3px rgba(239, 68, 68, 0.45)',
        'glow-emerald': '0 0 20px -3px rgba(16, 185, 129, 0.45)',
        'glow-amber': '0 0 20px -3px rgba(245, 158, 11, 0.45)',
      }
    },
  },
  plugins: [],
}
