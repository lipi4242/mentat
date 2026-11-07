import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { INSTANCE_TITLE } from './instance';

document.title = INSTANCE_TITLE;

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
