/**
 * scripts/db-migrate.js
 *
 * Standalone migration script — creates all required tables in Azure PostgreSQL.
 * Run with:  npm run db:migrate
 *
 * Reads credentials from environment variables (or a .env.local file).
 * Safe to re-run — all CREATE TABLE / CREATE TRIGGER statements use IF NOT EXISTS.
 */

// Load .env.local for local development
const path = require('path');
const fs = require('fs');

// Manually load .env.local since this is a plain Node.js script (not Next.js)
const envPath = path.resolve(__dirname, '..', '.env.local');
if (fs.existsSync(envPath)) {
  const lines = fs.readFileSync(envPath, 'utf8').split('\n');
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const idx = trimmed.indexOf('=');
    if (idx === -1) continue;
    const key = trimmed.slice(0, idx).trim();
    const val = trimmed.slice(idx + 1).trim();
    if (!process.env[key]) {
      process.env[key] = val;
    }
  }
  console.log(`[migrate] Loaded environment from ${envPath}`);
}

const { Pool } = require('pg');

async function migrate() {
  const config = process.env.DATABASE_URL
    ? {
        connectionString: process.env.DATABASE_URL,
        ssl: { rejectUnauthorized: false },
      }
    : {
        host:     process.env.DB_HOST,
        port:     parseInt(process.env.DB_PORT || '5432', 10),
        database: process.env.DB_NAME,
        user:     process.env.DB_USER,
        password: process.env.DB_PASSWORD,
        ssl:      { rejectUnauthorized: false },
      };

  if (!config.connectionString && !config.host) {
    console.error('[migrate] ERROR: No database configuration found.');
    console.error('         Set DATABASE_URL or DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD in .env.local');
    process.exit(1);
  }

  const pool = new Pool(config);

  console.log('[migrate] Connecting to Azure PostgreSQL…');

  try {
    await pool.query('SELECT 1'); // Connectivity check
    console.log('[migrate] ✓ Connected successfully.');

    // ── users table ─────────────────────────────────────────────
    console.log('[migrate] Creating users table (if not exists)…');
    await pool.query(`
      CREATE TABLE IF NOT EXISTS users (
        id            SERIAL PRIMARY KEY,
        name          VARCHAR(100)  NOT NULL,
        email         VARCHAR(255)  UNIQUE NOT NULL,
        password_hash TEXT          NOT NULL,
        created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
        updated_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
      );
    `);
    console.log('[migrate] ✓ users table ready.');

    // ── updated_at trigger function ──────────────────────────────
    await pool.query(`
      CREATE OR REPLACE FUNCTION update_updated_at_column()
      RETURNS TRIGGER AS $$
      BEGIN
        NEW.updated_at = NOW();
        RETURN NEW;
      END;
      $$ LANGUAGE plpgsql;
    `);

    // Create trigger only if it doesn't exist yet
    await pool.query(`
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
    console.log('[migrate] ✓ updated_at trigger ready.');

    // ── Index on email for fast lookups ──────────────────────────
    await pool.query(`
      CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    `);
    console.log('[migrate] ✓ Email index ready.');

    console.log('\n[migrate] ✅ Database migration completed successfully.\n');
    console.log('  Table:  users');
    console.log('  Columns: id, name, email, password_hash, created_at, updated_at');
  } catch (err) {
    console.error('[migrate] ✗ Migration failed:', err.message);
    if (err.message.includes('SSL') || err.message.includes('ssl')) {
      console.error('[migrate] Hint: Azure PostgreSQL requires SSL. Ensure ssl: { rejectUnauthorized: false } is set.');
    }
    process.exit(1);
  } finally {
    await pool.end();
  }
}

migrate();
