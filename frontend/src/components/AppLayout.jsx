/**
 * AppLayout — wraps every protected page with the Navbar and a main content area.
 */

import { Outlet } from 'react-router-dom';
import Navbar from './Navbar';

export default function AppLayout() {
  return (
    <div className="app-layout">
      <Navbar />
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
