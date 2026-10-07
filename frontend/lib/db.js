/**
 * lib/db.js — PostgreSQL connection pool for Azure Database for PostgreSQL.
 *
 * Reads all credentials exclusively from environment variables.
 * Uses a module-level singleton pool to reuse connections across API
 * route invocations in the same Next.js server process.
 *
 * Required environment variables (set in frontend/.env.local):
 *   DB_HOST      — Azure PostgreSQL server hostname
 *   DB_PORT      — PostgreSQL port (default: 5432)
 *   DB_NAME      — Database name  (e.g. wx_agent_db)
 *   DB_USER      — PostgreSQL login user
 *   DB_PASSWORD  — PostgreSQL login password
 *   DATABASE_URL — (alternative) full connection string, overrides the
 *                  individual variables above if present
 */

import { Pool } from 'pg';

let pool;

function getPool() {
  if (pool) return pool;

  const config = process.env.DATABASE_URL
    ? {
        connectionString: process.env.DATABASE_URL,
        // Azure PostgreSQL requires SSL on all connections.
        ssl: { rejectUnauthorized: false },
        max: 10,
        idleTimeoutMillis: 30_000,
        connectionTimeoutMillis: 10_000,
      }
    : {
        host:     process.env.DB_HOST,
        port:     parseInt(process.env.DB_PORT || '5432', 10),
        database: process.env.DB_NAME,
        user:     process.env.DB_USER,
        password: process.env.DB_PASSWORD,
        // Azure PostgreSQL requires SSL on all connections.
        ssl: { rejectUnauthorized: false },
        max: 10,
        idleTimeoutMillis: 30_000,
        connectionTimeoutMillis: 10_000,
      };

  pool = new Pool(config);

  pool.on('error', (err) => {
    console.error('[db] Unexpected error on idle PostgreSQL client:', err);
  });

  return pool;
}

/**
 * Execute a parameterised SQL query.
 *
 * @param {string} text   — SQL statement with $1, $2, … placeholders
 * @param {Array}  params — Bound parameter values
 * @returns {Promise<import('pg').QueryResult>}
 */
export async function query(text, params) {
  const client = getPool();
  return client.query(text, params);
}

/**
 * Initialise the database schema.
 * Creates the `users` table if it does not already exist.
 * Safe to call on every server start (idempotent).
 */
export async function initDb() {
  await query(`
    CREATE TABLE IF NOT EXISTS users (
      id           SERIAL PRIMARY KEY,
      name         VARCHAR(100)  NOT NULL,
      email        VARCHAR(255)  UNIQUE NOT NULL,
      password_hash TEXT         NOT NULL,
      created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
      updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
    );
  `);

  // Trigger to keep updated_at current automatically
  await query(`
    CREATE OR REPLACE FUNCTION update_updated_at_column()
    RETURNS TRIGGER AS $$
    BEGIN
      NEW.updated_at = NOW();
      RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;
  `);

  await query(`
    DO $$
    BEGIN
      IF NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'set_updated_at_users'
      ) THEN
        CREATE TRIGGER set_updated_at_users
        BEFORE UPDATE ON users
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
      END IF;
    END
    $$;
  `);
}

export default { query, initDb };
