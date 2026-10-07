import "@/styles/globals.css";
import Head from "next/head";
import { useEffect, useState } from "react";
import { useRouter } from "next/router";

// Routes that require the user to be authenticated
const PROTECTED_ROUTES = ["/"];
// Routes only accessible to unauthenticated users (redirect to / if already logged in)
const AUTH_ONLY_ROUTES = ["/login", "/signup"];

export default function App({ Component, pageProps }) {
  const router = useRouter();
  const [authState, setAuthState] = useState({
    user: null,
    checked: false, // true once the /api/auth/me call has completed
  });

  useEffect(() => {
    // On every page mount, check whether the session cookie is valid.
    fetch("/api/auth/me")
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        const user = data?.user || null;
        setAuthState({ user, checked: true });
      })
      .catch(() => {
        setAuthState({ user: null, checked: true });
      });
  }, []);

  useEffect(() => {
    if (!authState.checked) return; // Wait until we know auth status

    const path = router.pathname;

    if (!authState.user && PROTECTED_ROUTES.includes(path)) {
      // Unauthenticated user trying to access a protected page → login
      router.replace("/login");
    } else if (authState.user && AUTH_ONLY_ROUTES.includes(path)) {
      // Authenticated user trying to visit login/signup → send to chat
      router.replace("/");
    }
  }, [authState, router.pathname]);

  // Show nothing while we are still determining auth status
  // (avoids flash of wrong content)
  if (!authState.checked) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ background: "linear-gradient(180deg, #33507a 0%, #40608c 55%, #5074a0 100%)" }}
      >
        <span className="w-2 h-2 bg-white/60 rounded-full animate-ping" />
      </div>
    );
  }

  return (
    <>
      <Head>
        <title>Weather Buddy</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>
      <Component
        {...pageProps}
        authUser={authState.user}
        onLogout={async () => {
          await fetch("/api/auth/logout", { method: "POST" });
          setAuthState({ user: null, checked: true });
          router.replace("/login");
        }}
      />
    </>
  );
}
