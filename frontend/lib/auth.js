/**
 * lib/auth.js — JWT session helpers for Weather Buddy authentication.
 *
 * Uses the `jose` library (edge-compatible, no Node.js crypto issues in Next.js).
 * The JWT secret is read exclusively from the JWT_SECRET environment variable —
 * it is NEVER hardcoded and NEVER exposed to frontend browser code.
 *
 * Token lifecycle:
 *   - Issued as a signed JWT on successful login / signup
 *   - Stored in an HTTP-only, SameSite=Lax cookie named `wx_session`
 *   - Verified server-side on every protected API route call
 *   - Maximum age: 7 days (rolling)
 */

import { SignJWT, jwtVerify } from 'jose';

const COOKIE_NAME = 'wx_session';
const TOKEN_EXPIRY = '7d';

function getSecret() {
  const secret = process.env.JWT_SECRET;
  if (!secret) {
    throw new Error(
      'JWT_SECRET environment variable is not set. ' +
      'Generate one with: node -e "console.log(require(\'crypto\').randomBytes(64).toString(\'hex\'))"'
    );
  }
  return new TextEncoder().encode(secret);
}

/**
 * Create a signed JWT containing only safe (non-sensitive) user fields.
 *
 * @param {{ id: number, name: string, email: string }} user
 * @returns {Promise<string>} Signed JWT string
 */
export async function createToken(user) {
  const secret = getSecret();
  return new SignJWT({ id: user.id, name: user.name, email: user.email })
    .setProtectedHeader({ alg: 'HS256' })
    .setIssuedAt()
    .setExpirationTime(TOKEN_EXPIRY)
    .sign(secret);
}

/**
 * Verify a JWT and return its payload.
 *
 * @param {string} token
 * @returns {Promise<{ id: number, name: string, email: string }>}
 * @throws if token is invalid or expired
 */
export async function verifyToken(token) {
  const secret = getSecret();
  const { payload } = await jwtVerify(token, secret);
  return payload;
}

/**
 * Retrieve and verify the session token from the request cookies.
 *
 * @param {import('next').NextApiRequest} req
 * @returns {Promise<{ id: number, name: string, email: string } | null>}
 */
export async function getSession(req) {
  try {
    const token = req.cookies?.[COOKIE_NAME];
    if (!token) return null;
    return await verifyToken(token);
  } catch {
    return null;
  }
}

/**
 * Attach the session JWT as an HTTP-only cookie on the response.
 *
 * @param {import('next').NextApiResponse} res
 * @param {string} token
 */
export function setSessionCookie(res, token) {
  const isProduction = process.env.NODE_ENV === 'production';
  const cookieOptions = [
    `${COOKIE_NAME}=${token}`,
    'HttpOnly',
    'Path=/',
    'SameSite=Lax',
    `Max-Age=${7 * 24 * 60 * 60}`, // 7 days in seconds
    isProduction ? 'Secure' : '',
  ]
    .filter(Boolean)
    .join('; ');

  res.setHeader('Set-Cookie', cookieOptions);
}

/**
 * Clear the session cookie (used on logout).
 *
 * @param {import('next').NextApiResponse} res
 */
export function clearSessionCookie(res) {
  res.setHeader(
    'Set-Cookie',
    `${COOKIE_NAME}=; HttpOnly; Path=/; SameSite=Lax; Max-Age=0`
  );
}

export { COOKIE_NAME };
