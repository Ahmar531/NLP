import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// This file tells Vite how to build the React app.
export default defineConfig({
  plugins: [react()],
})
