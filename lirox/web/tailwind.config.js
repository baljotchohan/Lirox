/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        lirox: {
          lion: '#DCAE5B', // A subtle lion-yellow accent
          'lion-light': '#F0CE81',
          'lion-dim': '#B0883D',
          bg: '#0F0F0F', // Very dark background like Cursor
          'bg-card': '#1A1A1A', // Slightly lighter for panels
          'bg-hover': '#242424',
          border: '#2A2A2A',
          'text-primary': '#E0E0E0',
          'text-secondary': '#888888',
          success: '#10b981',
          thinking: '#DCAE5B',
          error: '#ef4444',
          warning: '#f59e0b',
        },
      },
      fontFamily: {
        sans: ['"Inter"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
        serif: ['"ui-serif"', 'Georgia', 'serif'],
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.2s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}
