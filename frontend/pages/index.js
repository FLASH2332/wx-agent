import React, { useState, useRef, useEffect } from 'react';
import { History, X } from 'lucide-react';
import AppShell from '@/components/AppShell';
import TopBar from '@/components/TopBar';
import VoiceInput from '@/components/VoiceInput';
import WeatherCard from '@/components/WeatherCard';
import SkeletonCard from '@/components/SkeletonCard';
import HourlyTimeline from '@/components/HourlyTimeline';
import ForecastList from '@/components/ForecastList';
import AlertBanner from '@/components/AlertBanner';
import ChatHistory from '@/components/ChatHistory';
import AudioPlayer from '@/components/AudioPlayer';
import ErrorToast from '@/components/ErrorToast';
import SuggestionChips from '@/components/SuggestionChips';
import { queryAgent, fetchInstantWeather } from '@/lib/api';
import { skyFor } from '@/lib/skyTheme';

export default function Home() {
  const [appState, setAppState] = useState('idle');
  
  const [weatherData, setWeatherData] = useState(null);
  const [forecastDays, setForecastDays] = useState([]);
  const [forecastHourly, setForecastHourly] = useState([]);
  const [alerts, setAlerts] = useState([]); 
  
  const [messages, setMessages] = useState([]);
  const [latestQuestion, setLatestQuestion] = useState("");
  const [latestResponse, setLatestResponse] = useState("");
  const [latestAudio, setLatestAudio] = useState("");

  // Voice-first: the latest turn shows briefly above the input, then fades.
  const [showBubble, setShowBubble] = useState(false);
  const [showHistory, setShowHistory] = useState(false);

  // Explicit language state (overrides auto-detection for subsequent turns)
  const [selectedLang, setSelectedLang] = useState("en");

  const [errorMsg, setErrorMsg] = useState("");
  const endOfChatRef = useRef(null);

  // Auto-dismiss the latest-turn bubble once the answer has landed.
  useEffect(() => {
    if (appState === 'result' && latestResponse) {
      const t = setTimeout(() => setShowBubble(false), 9000);
      return () => clearTimeout(t);
    }
  }, [appState, latestResponse]);

  useEffect(() => {
    if (showHistory) endOfChatRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, showHistory]);

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
      setLatestQuestion(text.trim());
      setLatestResponse("");
      setLatestAudio("");
      setShowBubble(true);
    }

    setAppState('processing');
    setErrorMsg("");
    
    try {
      // Pass existing messages to backend (Strands agent(text) appends the user turn automatically)
      const contextLocation = weatherData?.location || null;
      const response = await queryAgent(text, activeLang, currentMessages, contextLocation);
      
      setMessages(response.messages || [...currentMessages, userMsg]);
      
      if (!isSilentLocationUpdate) {
        setLatestResponse(response.response_text || "");
        setLatestAudio(response.audio_b64 || "");
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

  const dock = (
    <div className="max-w-3xl mx-auto w-full px-4 pt-3 pb-4">
      {/* Latest turn only — appears above the input, then fades. The real answer
          is the dashboard updating; full transcript lives in the history drawer. */}
      {showBubble && (latestQuestion || appState === 'processing') && (
        <div className="mb-3 flex flex-col gap-1.5 animate-fade-in-up">
          {latestQuestion && (
            <div className="self-end max-w-[80%] bg-white/[0.12] text-white text-sm px-3.5 py-2
              rounded-2xl rounded-br-md">
              {latestQuestion}
            </div>
          )}
          {appState === 'processing' ? (
            <div className="self-start bg-white/[0.06] text-white/60 text-sm px-3.5 py-2
              rounded-2xl rounded-bl-md flex items-center gap-2">
              <span className="w-1.5 h-1.5 bg-white/70 rounded-full animate-ping" />
              Weather Buddy is thinking…
            </div>
          ) : latestResponse ? (
            <div className="self-start max-w-[85%] bg-white/[0.06] border border-white/10
              text-white/90 text-sm px-3.5 py-2.5 rounded-2xl rounded-bl-md">
              {latestResponse}
            </div>
          ) : null}
          {/* Audio only appears with a fresh spoken reply, then fades with the turn */}
          {latestAudio && (
            <div className="self-start">
              <AudioPlayer audioBase64={latestAudio} autoPlay={true} />
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-2 w-full">
        <div className="flex-1 min-w-0 flex flex-col">
          <VoiceInput onTranscript={(text, lang) => handleQuery(text, false, lang)} appState={appState} currentLang={selectedLang} />
        </div>
        {messages.length > 0 && (
          <button
            onClick={() => setShowHistory(true)}
            title="Conversation history"
            aria-label="Open conversation history"
            className="shrink-0 w-12 h-12 flex items-center justify-center rounded-2xl
              bg-white/[0.06] border border-white/10 text-white/70
              hover:bg-white/[0.12] hover:text-white transition-colors"
          >
            <History className="w-5 h-5" strokeWidth={1.75} />
          </button>
        )}
      </div>
    </div>
  );

  const historyDrawer = showHistory && (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={() => setShowHistory(false)}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm animate-fade-in-up" />
      <div
        className="relative w-full max-w-md h-full bg-slate-950/90 backdrop-blur-2xl
          border-l border-white/10 flex flex-col animate-slide-in-right"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 shrink-0">
          <h3 className="font-medium text-white">Conversation</h3>
          <button
            onClick={() => setShowHistory(false)}
            aria-label="Close"
            className="w-8 h-8 flex items-center justify-center rounded-full text-white/60 hover:text-white hover:bg-white/10 transition-colors"
          >
            <X className="w-5 h-5" strokeWidth={1.75} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto hide-scrollbar p-4">
          <ChatHistory messages={messages} currentLang={selectedLang} />
          <div ref={endOfChatRef} className="h-1" />
        </div>
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
      />

      {/* DASHBOARD - MULTI-COLUMN LAYOUT */}
      <div className="flex flex-col lg:flex-row gap-6 lg:gap-8">

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

        {/* RIGHT COLUMN: Sidebar — only present once there's data, so the
            loading skeleton spans the full width and never looks off-center. */}
        {weatherData && (
          <div className="w-full lg:w-80 shrink-0 flex flex-col gap-5">
            <ForecastList days={forecastDays} currentLang={selectedLang} />
          </div>
        )}
      </div>

      <ErrorToast message={errorMsg} onDismiss={() => setErrorMsg("")} />
      {historyDrawer}
    </AppShell>
  );
}
