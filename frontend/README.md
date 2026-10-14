# Email Agent — React frontend

Login, registration, and a protected dashboard for the Email Agent backend.
Built with Vite + React + react-router-dom.

## Structure

```
src/
  api/client.js            fetch wrapper + token storage (no React, easy to unit test)
  context/AuthContext.jsx  shared auth state: token, user, login/register/logout
  components/
    ProtectedRoute.jsx     redirects to / if not logged in
    ActivityRail.jsx       the animated "agent activity" panel on the login screen
  pages/
    Login.jsx              login + register (toggle between the two)
    Dashboard.jsx          account info, status, logout
  styles/global.css        design system (colors, type, layout)
```

## Setup

```bash
npm install
cp .env.example .env    # set VITE_API_BASE_URL if the backend isn't on localhost:8000
npm run dev             # http://localhost:5173
```

Make sure the backend's `CORS_ORIGINS` includes whatever origin this app is
served from (`http://localhost:5173` for `npm run dev`, or your deployed
frontend URL in production).

## Build

```bash
npm run build      # outputs to dist/
npm run preview    # serve the production build locally
```

## Notes

- The token is stored in `localStorage` (see `src/api/client.js`). Fine for
  local/dev use; for production, consider an httpOnly cookie instead to
  reduce XSS exposure.
- `AuthContext` fetches `/auth/me` once on load if a token already exists
  (e.g. after a page refresh), so the whole app shares one source of truth
  for the logged-in user instead of every component re-fetching it.
