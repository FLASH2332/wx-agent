import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, Trash2 } from 'lucide-react';
import AppShell from '@/components/AppShell';
import TopBar from '@/components/TopBar';
import VoiceInput from '@/components/VoiceInput';
import WeatherCard from '@/components/WeatherCard';
import SkeletonCard from '@/components/SkeletonCard';
import HourlyTimeline from '@/components/HourlyTimeline';
import ForecastList from '@/components/ForecastList';
import AlertBanner from '@/components/AlertBanner';
import ChatHistory from '@/components/ChatHistory';
import ErrorToast from '@/components/ErrorToast';
import SuggestionChips from '@/components/SuggestionChips';
import { queryAgent, fetchInstantWeather } from '@/lib/api';
import { skyFor } from '@/lib/skyTheme';

export default function Home({ authUser, onLogout }) {
  const [appState, setAppState] = useState('idle');
  
  const [weatherData, setWeatherData] = useState(null);
  const [forecastDays, setForecastDays] = useState([]);
  const [forecastHourly, setForecastHourly] = useState([]);
  const [alerts, setAlerts] = useState([]); 
  
  const [messages, setMessages] = useState([]);
  const [latestResponse, setLatestResponse] = useState("");
  const [streamingText, setStreamingText] = useState("");

  // Explicit language state (overrides auto-detection for subsequent turns)
  const [selectedLang, setSelectedLang] = useState("en");

  const [errorMsg, setErrorMsg] = useState("");
  const endOfChatRef = useRef(null);

  // Keep the conversation panel scrolled to the latest message.
  useEffect(() => {
    endOfChatRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, appState]);

  useEffect(() => {
    // On initial load, try to get the user's location to populate the dashboard
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          try {
            setAppState('processing');
            const { latitude, longitude } = position.coords;
            // Need to import fetchInstantWeatherByCoords in the file!
            const { fetchInstantWeatherByCoords } = await import('@/lib/api');
            const data = await fetchInstantWeatherByCoords(latitude, longitude);
            
            setWeatherData(data.weather_data);
            if (data.forecast_data) {
              setForecastDays(data.forecast_data.days || []);
              setForecastHourly(data.forecast_data.hourly || []);
            }
            if (data.alerts) setAlerts(data.alerts);
            
            setAppState('result');
          } catch (e) {
            console.error("Geolocation fetch failed:", e);
            setAppState('idle');
          }
        },
        (error) => {
          console.log("Geolocation permission denied or failed:", error);
        }
      );
    }
  }, []);

  const handleQuery = async (text, isSilentLocationUpdate = false, detectedLang = null) => {
    if (!text.trim()) return;
    
    let activeLang = detectedLang || selectedLang;
    if (detectedLang && detectedLang !== selectedLang) {
      setSelectedLang(detectedLang);
    }
    
    // Create optimistic user message for instant UI render
    const userMsg = { role: 'user', content: [{ text: text.trim() }] };
    const currentMessages = messages;
    
    if (!isSilentLocationUpdate) {
      setMessages([...currentMessages, userMsg]);
      setLatestResponse("");
    }

    setAppState('processing');
    setErrorMsg("");
    
    try {
      // Pass existing messages to backend (Strands agent(text) appends the user turn automatically)
      const contextLocation = weatherData?.location || null;
      const response = await queryAgent(text, activeLang, currentMessages, contextLocation);
      
      setMessages(response.messages || [...currentMessages, userMsg]);
      
      if (!isSilentLocationUpdate) {
        const fullText = response.response_text || "";
        setLatestResponse(fullText);
        // Typewriter reveal — stream words into streamingText so the reply
        // appears progressively rather than popping in all at once.
        setStreamingText("");
        const words = fullText.split(" ");
        let built = "";
        for (let i = 0; i < words.length; i++) {
          built += (i === 0 ? "" : " ") + words[i];
          const snapshot = built;
          setTimeout(() => setStreamingText(snapshot), i * 35);
        }
      }
      
      let newLocation = response.weather_data?.location || response.forecast_data?.location;
      
      if (newLocation) {
        try {
          const syncData = await fetchInstantWeather(newLocation);
          setWeatherData(syncData.weather_data);
          if (syncData.forecast_data) {
            setForecastDays(syncData.forecast_data.days || []);
            setForecastHourly(syncData.forecast_data.hourly || []);
          }
          if (syncData.alerts) setAlerts(syncData.alerts);
        } catch(e) {
          console.warn("Silent sync failed", e);
          if (response.weather_data && Object.keys(response.weather_data).length > 0) {
            setWeatherData(response.weather_data);
          }
          if (response.forecast_data) {
            setForecastDays(response.forecast_data.days || []);
            setForecastHourly(response.forecast_data.hourly || []);
          }
        }
      }
      
      setAppState('result');
    } catch (err) {
      console.error(err);
      setErrorMsg(err.message || "Something went wrong.");
      setAppState('idle');
    }
  };

  const handleManualLocation = async (location) => {
    try {
      setAppState('processing');
      const data = await fetchInstantWeather(location);
      
      setWeatherData(data.weather_data);
      if (data.forecast_data) {
        setForecastDays(data.forecast_data.days || []);
        setForecastHourly(data.forecast_data.hourly || []);
      }
      if (data.alerts) setAlerts(data.alerts);
      
      setAppState('result');
    } catch (e) {
      console.error("Manual search failed:", e);
      setErrorMsg(`Could not fetch weather for "${location}".`);
      setAppState('idle');
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    setLatestResponse("");
    setStreamingText("");
  };

  const dock = (
    <div className="max-w-3xl mx-auto w-full px-4 pt-3 pb-4">
      <VoiceInput onTranscript={(text, lang) => handleQuery(text, false, lang)} appState={appState} currentLang={selectedLang} />
    </div>
  );

  // Persistent conversation panel — lives in the right rail, fills the space,
  // and is where the assistant's replies and audio appear.
  const conversationPanel = (
    <div className="flex-1 min-h-[240px] lg:min-h-0 flex flex-col overflow-hidden
      rounded-[24px] bg-white/[0.06] border border-white/10 backdrop-blur-md">
      <div className="flex items-center gap-2 px-5 py-3.5 border-b border-white/10 shrink-0">
        <MessageCircle className="w-4 h-4 text-white/60" strokeWidth={1.75} />
        <h3 className="text-sm font-medium text-white/70 flex-1">Weather Buddy</h3>
        {messages.length > 0 && (
          <button
            onClick={handleClearChat}
            className="p-1.5 rounded-lg text-white/30 hover:text-white/60 hover:bg-white/[0.06] transition-colors"
            title="Clear conversation"
          >
            <Trash2 className="w-3.5 h-3.5" strokeWidth={1.75} />
          </button>
        )}
      </div>
      <div className="flex-1 overflow-y-auto hide-scrollbar p-4 flex flex-col">
        {messages.length === 0 && appState !== 'processing' ? (
          <p className="m-auto text-center text-white/40 text-sm px-2 leading-relaxed">
            Ask about any place or forecast — by voice or text.<br />
            Your conversation appears here.
          </p>
        ) : (
          <>
            <ChatHistory messages={messages} currentLang={selectedLang} streamingText={streamingText} />
            {appState === 'processing' && (
              <div className="flex justify-start my-1.5">
                <div className="bg-white/[0.06] text-white/60 px-3.5 py-2 rounded-2xl rounded-bl-md
                  text-sm flex items-center gap-2">
                  <span className="w-1.5 h-1.5 bg-white/70 rounded-full animate-ping" />
                  Weather Buddy is thinking…
                </div>
              </div>
            )}
            <div ref={endOfChatRef} className="h-1" />
          </>
        )}
      </div>
    </div>
  );

  return (
    <AppShell
      sky={skyFor(weatherData)}
      banner={alerts.length > 0 ? <AlertBanner alerts={alerts} /> : null}
      footer={dock}
    >
      <TopBar
        currentLang={selectedLang}
        onLangChange={setSelectedLang}
        onLocationSearch={handleManualLocation}
        authUser={authUser}
        onLogout={onLogout}
      />

      {/* DASHBOARD - MULTI-COLUMN LAYOUT */}
      <div className="flex flex-col lg:flex-row gap-6 lg:gap-8 lg:items-stretch">

        {/* LEFT COLUMN: Main Weather */}
        <div className="flex-1 flex flex-col gap-5 min-w-0">
          {appState === 'processing' && !weatherData && <SkeletonCard />}

          {weatherData && (
            <>
              <WeatherCard weatherData={weatherData} currentLang={selectedLang} />
              <HourlyTimeline hours={forecastHourly} currentLang={selectedLang} />
            </>
          )}

          {appState === 'idle' && !weatherData && (
            <div className="flex flex-col items-center justify-center min-h-[16rem]
              border border-dashed border-white/[0.08] rounded-[28px]
              bg-white/[0.02] p-8">
              <p className="text-white/35 font-medium mb-4 text-sm">Ask Weather Buddy for a forecast…</p>
              <SuggestionChips onSelect={(text) => handleQuery(text, false)} />
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: forecast on top, live conversation filling the rest. */}
        <div className="w-full lg:w-96 shrink-0 flex flex-col gap-5">
          {weatherData && <ForecastList days={forecastDays} currentLang={selectedLang} />}
          {conversationPanel}
        </div>
      </div>

      <ErrorToast message={errorMsg} onDismiss={() => setErrorMsg("")} />
    </AppShell>
  );
}
