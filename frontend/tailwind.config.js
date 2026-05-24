/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      colors: {
        // Primary brand
        brand: {
          50:  '#eefdf4',
          100: '#d6f9e4',
          200: '#b0f2cc',
          300: '#78e6ab',
          400: '#3fd182',
          500: '#1ab863',
          600: '#0e9650',
          700: '#0d7741',
          800: '#0f5e36',
          900: '#0d4d2e',
        },
        // Dark surface palette
        surface: {
          950: '#080d0f',
          900: '#0d1117',
          800: '#161b22',
          700: '#21262d',
          600: '#2d333b',
          500: '#373e47',
          400: '#444c56',
        },
        // Scope badges
        scope1: { bg: '#431407', text: '#fb923c', border: '#9a3412' },
        scope2: { bg: '#0c1a4f', text: '#60a5fa', border: '#1e40af' },
        scope3: { bg: '#2e1065', text: '#c084fc', border: '#6b21a8' },
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'shimmer': 'shimmer 1.5s infinite',
        'spin-slow': 'spin 2s linear infinite',
      },
      keyframes: {
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp: { from: { opacity: '0', transform: 'translateY(12px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        shimmer: { '0%': { backgroundPosition: '-200% 0' }, '100%': { backgroundPosition: '200% 0' } },
      },
    },
  },
  plugins: [],
}
