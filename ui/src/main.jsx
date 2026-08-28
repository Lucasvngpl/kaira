import React from 'react';
import { createRoot } from 'react-dom/client';
// Global styles FIRST: component files import their own surface CSS, and in
// bundle order later rules win ties - shared chrome (app.css) must lose to
// surface overrides (session.css etc.), so it has to precede App's imports.
import './styles/tokens.css';
import './styles/app.css';
import App from './App.jsx';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
