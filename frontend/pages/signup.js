import React, { useState } from 'react';
import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { Eye, EyeOff, Cloud, UserPlus, AlertCircle, CheckCircle } from 'lucide-react';
import { DEFAULT_SKY } from '@/lib/skyTheme';

// The sky used on auth pages — calm dusk blue matching the app's idle state
const AUTH_SKY = DEFAULT_SKY;

export default function SignupPage() {
  const router = useRouter();

  const [form, setForm] = useState({ name: '', email: '', password: '', confirm: '' });
  const [errors, setErrors] = useState({});
  const [apiError, setApiError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  // ── Client-side validation ───────────────────────────────────────
  function validate() {
    const e = {};
    if (!form.name.trim()) e.name = 'Name is required.';
    else if (form.name.trim().length > 100) e.name = 'Name must be 100 characters or fewer.';

    if (!form.email.trim()) e.email = 'Email is required.';
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()))
      e.email = 'Please enter a valid email address.';

    if (!form.password) e.password = 'Password is required.';
    else if (form.password.length < 8) e.password = 'Password must be at least 8 characters.';

    if (!form.confirm) e.confirm = 'Please confirm your password.';
    else if (form.confirm !== form.password) e.confirm = 'Passwords do not match.';

    return e;
  }

  function handleChange(field) {
    return (e) => {
      setForm((prev) => ({ ...prev, [field]: e.target.value }));
      // Clear field error on change
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
      const res = await fetch('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name:     form.name.trim(),
          email:    form.email.trim(),
          password: form.password,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setApiError(data.error || 'Signup failed. Please try again.');
        return;
      }

      // Signup successful — go to chat interface
      window.location.href = '/';
    } catch {
      setApiError('Could not connect to server. Please check your connection.');
    } finally {
      setLoading(false);
    }
  }

  const passwordStrength = (() => {
    const pw = form.password;
    if (!pw) return null;
    let score = 0;
    if (pw.length >= 8) score++;
    if (pw.length >= 12) score++;
    if (/[A-Z]/.test(pw)) score++;
    if (/[0-9]/.test(pw)) score++;
    if (/[^A-Za-z0-9]/.test(pw)) score++;
    if (score <= 1) return { label: 'Weak', color: '#f87171', width: '25%' };
    if (score <= 2) return { label: 'Fair', color: '#fb923c', width: '50%' };
    if (score <= 3) return { label: 'Good', color: '#facc15', width: '75%' };
    return { label: 'Strong', color: '#4ade80', width: '100%' };
  })();

  return (
    <>
      <Head>
        <title>Create Account — Weather Buddy</title>
        <meta name="description" content="Create a new Weather Buddy account" />
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
              <UserPlus className="w-4.5 h-4.5 text-white/60" strokeWidth={1.75} />
              <h2 className="text-lg font-medium text-white">Create your account</h2>
            </div>

            {/* API-level error */}
            {apiError && (
              <div className="flex items-start gap-2.5 bg-red-500/10 border border-red-400/20 rounded-xl px-4 py-3 mb-5 animate-fade-in-up">
                <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" strokeWidth={1.75} />
                <p className="text-red-300 text-sm leading-snug">{apiError}</p>
              </div>
            )}

            <form onSubmit={handleSubmit} noValidate className="space-y-4">

              {/* Name */}
              <div>
                <label htmlFor="signup-name" className="block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide">
                  Full Name
                </label>
                <input
                  id="signup-name"
                  type="text"
                  autoComplete="name"
                  value={form.name}
                  onChange={handleChange('name')}
                  placeholder="Your name"
                  className={`w-full bg-black/20 border rounded-[14px] py-3 px-4 text-sm text-white placeholder:text-white/30
                    outline-none transition-[border-color,box-shadow] duration-200
                    focus:border-white/30 focus:shadow-[0_0_0_3px_rgba(147,164,212,0.18)]
                    ${errors.name ? 'border-red-400/50' : 'border-white/[0.08]'}`}
                />
                {errors.name && (
                  <p className="text-red-400 text-xs mt-1.5 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" /> {errors.name}
                  </p>
                )}
              </div>

              {/* Email */}
              <div>
                <label htmlFor="signup-email" className="block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide">
                  Email Address
                </label>
                <input
                  id="signup-email"
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
                <label htmlFor="signup-password" className="block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide">
                  Password
                </label>
                <div className="relative">
                  <input
                    id="signup-password"
                    type={showPw ? 'text' : 'password'}
                    autoComplete="new-password"
                    value={form.password}
                    onChange={handleChange('password')}
                    placeholder="Min. 8 characters"
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
                {/* Password strength indicator */}
                {passwordStrength && (
                  <div className="mt-2">
                    <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{ width: passwordStrength.width, background: passwordStrength.color }}
                      />
                    </div>
                    <p className="text-xs mt-1" style={{ color: passwordStrength.color }}>
                      {passwordStrength.label}
                    </p>
                  </div>
                )}
                {errors.password && (
                  <p className="text-red-400 text-xs mt-1.5 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" /> {errors.password}
                  </p>
                )}
              </div>

              {/* Confirm Password */}
              <div>
                <label htmlFor="signup-confirm" className="block text-xs font-medium text-white/60 mb-1.5 uppercase tracking-wide">
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    id="signup-confirm"
                    type={showConfirm ? 'text' : 'password'}
                    autoComplete="new-password"
                    value={form.confirm}
                    onChange={handleChange('confirm')}
                    placeholder="Re-enter your password"
                    className={`w-full bg-black/20 border rounded-[14px] py-3 px-4 pr-11 text-sm text-white placeholder:text-white/30
                      outline-none transition-[border-color,box-shadow] duration-200
                      focus:border-white/30 focus:shadow-[0_0_0_3px_rgba(147,164,212,0.18)]
                      ${errors.confirm ? 'border-red-400/50' : 'border-white/[0.08]'}`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm((v) => !v)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-white/35 hover:text-white/60 transition-colors"
                    aria-label={showConfirm ? 'Hide password' : 'Show password'}
                  >
                    {showConfirm ? <EyeOff className="w-4 h-4" strokeWidth={1.75} /> : <Eye className="w-4 h-4" strokeWidth={1.75} />}
                  </button>
                </div>
                {form.confirm && form.confirm === form.password && !errors.confirm && (
                  <p className="text-green-400 text-xs mt-1.5 flex items-center gap-1">
                    <CheckCircle className="w-3 h-3" /> Passwords match
                  </p>
                )}
                {errors.confirm && (
                  <p className="text-red-400 text-xs mt-1.5 flex items-center gap-1">
                    <AlertCircle className="w-3 h-3" /> {errors.confirm}
                  </p>
                )}
              </div>

              {/* Submit */}
              <button
                id="signup-submit"
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
                    Creating account…
                  </span>
                ) : (
                  'Create Account'
                )}
              </button>
            </form>

            {/* Login link */}
            <p className="text-center text-sm text-white/40 mt-6">
              Already have an account?{' '}
              <Link
                href="/login"
                className="text-white/75 hover:text-white font-medium transition-colors duration-150"
              >
                Log in
              </Link>
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
