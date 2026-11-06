/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        municipal: {
          50: '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
        },
        civic: {
          primary: '#2563eb', // blue-600
          accent: '#0d9488',  // teal-600
          success: '#16a34a', // green-600
          warning: '#d97706', // amber-600
          danger: '#dc2626',  // red-600
        }
      },
    },
  },
  plugins: [],
}
