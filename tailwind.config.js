/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        case: {
          bg: '#0B0B0C',
          surface: '#141416',
          'surface-hover': '#1A1A1D',
          border: '#232326',
          'border-strong': '#2E2E32',
          text: '#EDEDEF',
          muted: '#9A9AA2',
          faint: '#5C5C63',
          brass: '#C89B3C',
          'brass-hover': '#DDB158',
          'brass-dim': '#8A6B2A',
        },
      },
      fontFamily: {
        display: ['"Newsreader"', 'serif'],
        sans: ['"Inter"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      letterSpacing: {
        widest2: '0.18em',
      },
      maxWidth: {
        content: '640px',
      },
    },
  },
  plugins: [],
}
