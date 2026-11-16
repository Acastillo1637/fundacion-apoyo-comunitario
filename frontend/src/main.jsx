import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './styles.css';
import './volunteers/styles.css';
import './activities/styles.css';
import './design/stitch.css';
import './design/pro12.css';
import './accounts/security.css';

createRoot(document.getElementById('root')).render(<React.StrictMode><BrowserRouter><App/></BrowserRouter></React.StrictMode>);
