/**
 * POST /api/auth/logout
 *
 * Clears the session cookie, effectively logging the user out.
 * JWTs are stateless — no server-side revocation needed for this app tier.
 *
 * Success (200):
 *   { message: 'Logged out successfully.' }
 */

import { clearSessionCookie } from '@/lib/auth';

export default function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  clearSessionCookie(res);
  return res.status(200).json({ message: 'Logged out successfully.' });
}
