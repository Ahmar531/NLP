/* ─────────────────────────────────────────────────────────────
   main.jsx  —  The React App Entry Point
   ─────────────────────────────────────────────────────────────
   Why this file exists:
     Every React app needs one starting point. This file tells
     React to "mount" (attach) our App component to the HTML page.

   What it is responsible for:
     1. Importing React and ReactDOM.
     2. Importing the global styles from index.css.
     3. Finding the <div id="root"> in index.html.
     4. Rendering the <App /> component inside that div.

   What React.StrictMode does:
     It is a special wrapper that helps find bugs during development.
     It does not change how the app looks or works in production.
     It just shows extra warnings in the browser console.
───────────────────────────────────────────────────────────── */

// React is the core library that lets us write JSX and use components
import React from 'react'

// ReactDOM connects React to the browser's real HTML page
import ReactDOM from 'react-dom/client'

// Import our main App component — this is the whole chat UI
import App from './App'

// Import the global CSS file — this sets fonts, background, etc.
import './index.css'

// Find the <div id="root"> element in index.html and mount React there.
// createRoot is the modern way to start a React 18 app.
ReactDOM.createRoot(document.getElementById('root')).render(
  // StrictMode runs extra checks in development mode only
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
