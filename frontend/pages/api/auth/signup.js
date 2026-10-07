/**
 * POST /api/auth/signup
 *
 * Registers a new user in the Azure PostgreSQL `users` table.
 *
 * Request body:
 *   { name: string, email: string, password: string }
 *
 * Success (201):
 *   { user: { id, name, email, created_at } }
 *
 * Error responses:
 *   400 — Validation failure or email already registered
 *   500 — Server / database error (internal detail is never leaked)
 */

import bcrypt from 'bcryptjs';
import { query, initDb } from '@/lib/db';
import { createToken, setSessionCookie } from '@/lib/auth';

const BCRYPT_ROUNDS = 12;

// Normalise email: lowercase + trim
const normaliseEmail = (raw) => raw.trim().toLowerCase();

// Basic email shape validation
const isValidEmail = (email) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { name, email: rawEmail, password } = req.body || {};

  // ── Validation ────────────────────────────────────────────────
  if (!name || typeof name !== 'string' || name.trim().length === 0) {
    return res.status(400).json({ error: 'Name is required.' });
  }
  if (name.trim().length > 100) {
    return res.status(400).json({ error: 'Name must be 100 characters or fewer.' });
  }
  if (!rawEmail || typeof rawEmail !== 'string') {
    return res.status(400).json({ error: 'Email is required.' });
  }
  const email = normaliseEmail(rawEmail);
  if (!isValidEmail(email)) {
    return res.status(400).json({ error: 'Please enter a valid email address.' });
  }
  if (!password || typeof password !== 'string') {
    return res.status(400).json({ error: 'Password is required.' });
  }
  if (password.length < 8) {
    return res.status(400).json({ error: 'Password must be at least 8 characters long.' });
  }

  try {
    // Ensure table exists (idempotent, cheap after first call)
    await initDb();

    // ── Duplicate email check ─────────────────────────────────────
    const existing = await query('SELECT id FROM users WHERE email = $1', [email]);
    if (existing.rows.length > 0) {
      return res.status(400).json({ error: 'This email is already registered. Please log in.' });
    }

    // ── Secure password hash ──────────────────────────────────────
    const password_hash = await bcrypt.hash(password, BCRYPT_ROUNDS);

    // ── Insert user ───────────────────────────────────────────────
    const result = await query(
      `INSERT INTO users (name, email, password_hash)
       VALUES ($1, $2, $3)
       RETURNING id, name, email, created_at`,
      [name.trim(), email, password_hash]
    );

    const newUser = result.rows[0];

    // ── Issue session token immediately after signup ──────────────
    const token = await createToken(newUser);
    setSessionCookie(res, token);

    return res.status(201).json({
      message: 'Account created successfully.',
      user: {
        id:         newUser.id,
        name:       newUser.name,
        email:      newUser.email,
        created_at: newUser.created_at,
      },
    });
  } catch (err) {
    console.error('[/api/auth/signup] Error:', err);
    // Never expose internal DB errors
    return res.status(500).json({ error: 'An unexpected error occurred. Please try again.' });
  }
}
