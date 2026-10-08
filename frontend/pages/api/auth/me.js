/**
 * GET /api/auth/me
 *
 * Returns the currently authenticated user's profile (safe fields only).
 * Used by the frontend to restore session state on page refresh.
 *
 * Success (200):
 *   { user: { id, name, email } }
 *
 * Unauthenticated (401):
 *   { error: 'Not authenticated' }
 */

import { getSession } from '@/lib/auth';
import { query, initDb } from '@/lib/db';

export default async function handler(req, res) {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const session = await getSession(req);
  if (!session) {
    return res.status(401).json({ error: 'Not authenticated' });
  }

  try {
    await initDb();

    // Re-fetch from DB to ensure account still exists (not deleted since token issued)
    const result = await query(
      'SELECT id, name, email, created_at FROM users WHERE id = $1',
      [session.id]
    );

    if (result.rows.length === 0) {
      return res.status(401).json({ error: 'Account no longer exists.' });
    }

    const user = result.rows[0];
    return res.status(200).json({
      user: {
        id:         user.id,
        name:       user.name,
        email:      user.email,
        created_at: user.created_at,
      },
    });
  } catch (err) {
    console.error('[/api/auth/me] Error:', err);
    return res.status(500).json({ error: 'An unexpected error occurred.' });
  }
}
