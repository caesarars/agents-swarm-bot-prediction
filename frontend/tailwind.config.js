/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        upbg: '#10b981',
        downbg: '#ef4444',
        panel: '#0f172a',
        card: '#111827',
        accent: '#22d3ee',
      },
    },
  },
  plugins: [],
}
