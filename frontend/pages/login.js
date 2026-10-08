import React, { useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Eye, EyeOff, Cloud, LogIn, AlertCircle } from 'lucide-react';
import { DEFAULT_SKY } from '@/lib/skyTheme';

const AUTH_SKY = DEFAULT_SKY;

export default function LoginPage() {
  const router = useRouter();

  const [form, setForm] = useState({ email: '', password: '' });
  const [errors, setErrors] = useState({});
  const [apiError, setApiError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPw, setShowPw] = useState(false);

  // ── Client-side validation ───────────────────────────────────────
  function validate() {
    const e = {};
    if (!form.email.trim()) e.email = 'Email is required.';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()))
      e.email = 'Please enter a valid email address.';
    if (!form.password) e.password = 'Password is required.';
    return e;
  }

  function handleChange(field) {
    return (e) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
      if (errors[field]) setErrors((prev) => ({ ...prev, [field]: '' }));
      if (apiError) setApiError('');
    };
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }

    setLoading(true);
    setApiError('');

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: form.email.trim(), password: form.password }),
      });

      const data = await res.json();

      if (!res.ok) {
        setApiError(data.error || 'Login failed. Please try again.');
        return;
      }

      // Login successful — redirect to existing chat interface (root route)
      window.location.href = '/';
    } catch {
      setApiError('Could not connect to server. Please check your connection.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <Head>
        <title>Log In — Weather Buddy</title>
        <meta name="description" content="Log in to Weather Buddy" />
      </Head>

      {/* Full-screen sky background — mirrors AppShell */}
      <div
        className="min-h-screen w-full text-slate-50 font-sans relative overflow-hidden flex flex-col items-center justify-center px-4 py-8"
        style={{ background: AUTH_SKY.gradient, transition: 'background 900ms cubic-bezier(0.2,0,0,1)' }}
      >
        {/* Celestial glow orb */}
        <div
          className="absolute -top-32 right-[8%] w-[46vw] max-w-[560px] h-[46vw] max-h-[560px] rounded-full pointer-events-none z-0"
          style={{ background: `radial-gradient(circle, ${AUTH_SKY.glow} 0%, transparent 70%)` }}
        />
        {/* Horizon haze */}
        <div
          className="absolute inset-x-0 bottom-0 h-1/3 pointer-events-none z-0"
          style={{ background: 'linear-gradient(0deg, rgba(255,255,255,0.05), transparent)' }}
        />

        {/* Card */}
        <div className="relative z-10 w-full max-w-md animate-fade-in-up">

          {/* Brand header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-white/[0.10] border border-white/[0.14] backdrop-blur-sm mb-4">
              <Cloud className="w-7 h-7 text-white/80" strokeWidth={1.5} />
            </div>
            <h1 className="text-2xl font-semibold tracking-tight text-white">Weather Buddy</h1>
            <p className="text-white/50 text-sm mt-1">Your multilingual weather assistant</p>
          </div>

          {/* Glass form card */}
          <div
            className="rounded-3xl border border-white/[0.10] backdrop-blur-xl p-8"
            style={{
              background: 'rgba(255,255,255,0.06)',
              boxShadow: '0 1px 2px rgba(0,0,0,0.25), 0 8px 32px rgba(0,0,0,0.20), 0 24px 64px rgba(0,0,0,0.12)',
            }}
          >
            <div className="flex items-center gap-2.5 mb-6">
              <LogIn className="w-4 h-4 text-white/60" strokeWidth={1.75} />
              <h2 className="text-lg font-medium text-white">Welcome back</h2>
            </div>

            {/* API-level error */}
            {apiError && (
              <div className="flex items-start gap-2.5 bg-red-500/10 border border-red-400/20 rounded-xl px-4 py-3 mb-5 animate-fade-in-up">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" strokeWidth={1.75} />
                <p className="text-red-300 text-sm leading-snug">{apiError}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} noValidate className="space-y-4">

              {/* Email */}
              <div>
                <label htmlFor="login-email" className="block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide">
                  Email Address
                </label>
                <input
                  id="login-email"
                  type="email"
                  autoComplete="email"
                  value={form.email}
                  onChange={handleChange('email')}
                  placeholder="you@example.com"
                  className={`w-full bg-black/20 border rounded-[14px] py-3 px-4 text-sm text-white placeholder:text-white/30
                    outline-none transition-[border-color,box-shadow] duration-200
                    focus:border-white/30 focus:shadow-[0_0_0_3px_rgba(147,164,212,0.18)]
                    ${errors.email ? 'border-red-400/50' : 'border-white/[0.08]'}`}
                />
                {errors.email && (
                  <p className="text-red-400 text-xs mt-1.5 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" /> {errors.email}
                  </p>
                )}
              </div>

              {/* Password */}
              <div>
                <label htmlFor="login-password" className="block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide">
                  Password
                </label>
                <div className="relative">
                  <input
                    id="login-password"
                    type={showPw ? 'text' : 'password'}
                    autoComplete="current-password"
                    value={form.password}
                    onChange={handleChange('password')}
                    placeholder="Your password"
                    className={`w-full bg-black/20 border rounded-[14px] py-3 px-4 pr-11 text-sm text-white placeholder:text-white/30
                      outline-none transition-[border-color,box-shadow] duration-200
                      focus:border-white/30 focus:shadow-[0_0_0_3px_rgba(147,164,212,0.18)]
                      ${errors.password ? 'border-red-400/50' : 'border-white/[0.08]'}`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw((v) => !v)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-white/35 hover:text-white/60 transition-colors"
                    aria-label={showPw ? 'Hide password' : 'Show password'}
                  >
                    {showPw ? <EyeOff className="w-4 h-4" strokeWidth={1.75} /> : <Eye className="w-4 h-4" strokeWidth={1.75} />}
                  </button>
                </div>
                {errors.password && (
                  <p className="text-red-400 text-xs mt-1.5 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" /> {errors.password}
                  </p>
                )}
              </div>

              {/* Submit */}
              <button
                id="login-submit"
                type="submit"
                disabled={loading}
                className="w-full mt-2 py-3 px-6 rounded-[14px] text-sm font-semibold tracking-wide
                  transition-all duration-200 press-scale
                  disabled:opacity-50 disabled:cursor-not-allowed"
                style={{
                  background: loading
                    ? 'rgba(255,255,255,0.08)'
                    : 'linear-gradient(135deg, rgba(255,255,255,0.18) 0%, rgba(255,255,255,0.10) 100%)',
                  border: '1px solid rgba(255,255,255,0.18)',
                  color: '#fff',
                  boxShadow: loading ? 'none' : '0 4px 16px rgba(0,0,0,0.2)',
                }}
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-1.5 h-1.5 bg-white/70 rounded-full animate-ping" />
                    Logging in…
                  </span>
                ) : (
                  'Log In'
                )}
              </button>
            </form>

            {/* Signup link */}
            <p className="text-center text-sm text-white/40 mt-6">
              Don&apos;t have an account?{' '}
              <Link
                href="/signup"
                className="text-white/75 hover:text-white font-medium transition-colors duration-150"
              >
                Create one
              </Link>
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
