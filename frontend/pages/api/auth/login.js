/**
 * POST /api/auth/login
 *
 * Authenticates an existing user against the Azure PostgreSQL `users` table.
 *
 * Request body:
 *   { email: string, password: string }
 *
 * Success (200):
 *   { user: { id, name, email } }
 *   + Sets HTTP-only session cookie
 *
 * Error responses:
 *   400 — Validation failure
 *   401 — Invalid credentials (intentionally vague to prevent enumeration)
 *   500 — Server / database error
 */

import bcrypt from 'bcryptjs';
import { query, initDb } from '@/lib/db';
import { createToken, setSessionCookie } from '@/lib/auth';

const normaliseEmail = (raw) => raw.trim().toLowerCase();

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { email: rawEmail, password } = req.body || {};

  // ── Validation ────────────────────────────────────────────────
  if (!rawEmail || typeof rawEmail !== 'string') {
    return res.status(400).json({ error: 'Email is required.' });
  }
  if (!password || typeof password !== 'string') {
    return res.status(400).json({ error: 'Password is required.' });
  }

  const email = normaliseEmail(rawEmail);

  try {
    await initDb();

    // ── Lookup user ───────────────────────────────────────────────
    const result = await query(
      'SELECT id, name, email, password_hash FROM users WHERE email = $1',
      [email]
    );

    // Use a timing-safe comparison even when user doesn't exist to prevent
    // timing-based email enumeration attacks.
    const DUMMY_HASH = '$2b$12$invalidhashfortimingnormalisation000000000000000000000';
    const user = result.rows[0] || null;
    const storedHash = user ? user.password_hash : DUMMY_HASH;

    const passwordMatch = await bcrypt.compare(password, storedHash);

    if (!user || !passwordMatch) {
      // Return the same error regardless of whether email exists or password wrong.
      return res.status(401).json({ error: 'Incorrect email or password.' });
    }

    // ── Issue session ─────────────────────────────────────────────
    const token = await createToken({ id: user.id, name: user.name, email: user.email });
    setSessionCookie(res, token);

    return res.status(200).json({
      user: {
        id:    user.id,
        name:  user.name,
        email: user.email,
      },
    });
  } catch (err) {
    console.error('[/api/auth/login] Error:', err);
    return res.status(500).json({ error: 'An unexpected error occurred. Please try again.' });
  }
}
