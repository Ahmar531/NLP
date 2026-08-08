/* ─────────────────────────────────────────────────────────────
   tailwind.config.js
   ─────────────────────────────────────────────────────────────
   Why this file exists:
     This is the configuration file for Tailwind CSS.
     It tells Tailwind which files to scan for class names and
     lets us add custom colours, spacing, or box-shadow values
     that are not in Tailwind by default.

   How it works:
     Tailwind reads every file listed in "content" and only keeps
     the CSS utility classes that are actually used in those files.
     This keeps the final CSS bundle as small as possible.
───────────────────────────────────────────────────────────── */

/** @type {import('tailwindcss').Config} */
export default {
  // Tell Tailwind where to look for class names
  content: ['./index.html', './src/**/*.{js,jsx}'],

  theme: {
    extend: {
      // Custom font family so we can use font-inter in any class
      fontFamily: {
        inter: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },

      // Custom colours used in the dark chat UI
      colors: {
        brand: {
          DEFAULT: '#6366f1', // Indigo-500 — used for the send button and user bubble
          light:   '#818cf8', // Indigo-400 — used for hover states
          dark:    '#4f46e5', // Indigo-600 — used for active states
        },
        surface: {
          DEFAULT: 'rgba(255,255,255,0.05)', // Glass card base
          input:   'rgba(255,255,255,0.08)', // Input field background
          hover:   'rgba(255,255,255,0.10)', // Hover highlight
        },
      },

      // Custom box-shadow values for the glowing card
      boxShadow: {
        glass:   '0 8px 32px rgba(0,0,0,0.4)',
        'input-focus': '0 0 0 2px rgba(99,102,241,0.4)',
      },

      // Custom animation timing
      keyframes: {
        'fade-up': {
          '0%':   { opacity: '0', transform: 'translateY(16px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        'fade-up': 'fade-up 0.3s ease-out forwards',
      },
    },
  },

  plugins: [],
}
