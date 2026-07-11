/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'dark-bg': '#0a0a0a',
        'dark-card': '#1a1a1a',
        'neon-blue': '#00d4ff',
        'neon-green': '#00ff88',
        'neon-red': '#ff4444',
        'neon-purple': '#aa00ff',
        'neon-orange': '#ffaa00',
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
      },
    },
  },
  plugins: [],
}