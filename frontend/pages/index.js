import React, { useState, useRef, useEffect } from 'react';
import { MessageCircle, Trash2, Volume2, VolumeX } from 'lucide-react';
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
import ComparisonCard from '@/components/ComparisonCard';
import ActivityChips from '@/components/ActivityChips';
import { queryAgent, fetchInstantWeather, synthesizeSpeech } from '@/lib/api';
import { playSpeech, stopSpeech } from '@/lib/speech';
import { skyFor } from '@/lib/skyTheme';

export default function Home({ authUser, onLogout }) {
  const [appState, setAppState] = useState('idle');
  const [userCoords, setUserCoords] = useState(null);
  
  const [weatherData, setWeatherData] = useState(null);
  const [forecastDays, setForecastDays] = useState([]);
  const [forecastHourly, setForecastHourly] = useState([]);
  const [alerts, setAlerts] = useState([]); 
  
  const [messages, setMessages] = useState([]);
  const [latestResponse, setLatestResponse] = useState("");
  // Spoken replies are opt-in: each one costs a TTS call (Polly) or uses free browser voices.
  const [speakEnabled, setSpeakEnabled] = useState(false);
  const [uiMode, setUiMode] = useState("dashboard");
  const [comparisonData, setComparisonData] = useState(null);
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
    try {
      setSpeakEnabled(localStorage.getItem('wb_speak') === '1');
    } catch (e) { /* storage unavailable */ }
  }, []);

  const toggleSpeak = () => {
    const next = !speakEnabled;
    setSpeakEnabled(next);
    if (!next) stopSpeech();
    try {
      localStorage.setItem('wb_speak', next ? '1' : '0');
    } catch (e) { /* storage unavailable */ }
  };

  useEffect(() => {
    // On initial load, try to get the user's location to populate the dashboard
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        async (position) => {
          try {
            setAppState('processing');
            const { latitude, longitude } = position.coords;
            setUserCoords({ lat: latitude, lon: longitude });
            // Need to import fetchInstantWeatherByCoords in the file!
            const { fetchInstantWeatherByCoords } = await import('@/lib/api');
            const data = await fetchInstantWeatherByCoords(latitude, longitude);
            
            setWeatherData(data.weather_data);
            if (data.forecast_data) {
              setForecastDays(data.forecast_data.days || []);
              setForecastHourly(data.forecast_data.hourly || []);
            }
            if (data.alerts) setAlerts(data.alerts);
            setAppState('idle');
            setUiMode('dashboard');
          } catch (err) {
            console.error("Location init error:", err);
            setAppState('idle');
          }
        },
        (error) => {
          console.log("Geolocation permission denied or failed:", error);
        }
      );
    }
  }, []);

  const handleLangChange = async (newLang) => {
    setSelectedLang(newLang);
    if (weatherData?.location) {
      setAppState('processing');
      try {
        const syncData = await fetchInstantWeather(weatherData.location, newLang);
        setWeatherData(syncData.weather_data);
        if (syncData.forecast_data) {
          setForecastDays(syncData.forecast_data.days || []);
          setForecastHourly(syncData.forecast_data.hourly || []);
        }
        if (syncData.alerts) setAlerts(syncData.alerts);
        setAppState('result');
      } catch (e) {
        console.error("Language sync failed", e);
        setAppState('idle');
      }
    }
  };

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
      // Send the visible text history; the server keeps only the last few turns for the model
      // and returns the updated text-only history (never raw tool/reasoning blocks).
      const contextLocation = weatherData?.location || null;
      
      const localTime = new Date().toISOString();
      const payload = {
        text,
        lang: activeLang,
        messages: currentMessages,
        contextLocation,
        userLat: userCoords?.lat || null,
        userLon: userCoords?.lon || null,
        localTime
      };
      
      const response = await queryAgent(payload);
      
      setMessages(response.messages || [...currentMessages, userMsg]);
      
      if (!isSilentLocationUpdate) {
        const fullText = response.response_text || "";
        setLatestResponse(fullText);
        setUiMode(response.ui_mode || "chat");
        setComparisonData(response.comparison_data || null);
        if (response.lang) {
          setSelectedLang(response.lang);
        }
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
        if (speakEnabled && fullText) {
          synthesizeSpeech(fullText, response.lang || activeLang)
            .then(playSpeech)
            .catch((e) => console.warn("Speech synthesis failed", e));
        }
      }
      
      let newLocation = response.weather_data?.location || response.forecast_data?.location;
      
      if (newLocation) {
        try {
          // Sync with the backend to ensure perfectly localized current & forecast data
          const syncData = await fetchInstantWeather(newLocation, activeLang);
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
      const data = await fetchInstantWeather(location, selectedLang);
      
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
    stopSpeech();
    setMessages([]);
    setLatestResponse("");
    setStreamingText("");
  };

  const dock = (
    <div className="max-w-3xl mx-auto w-full px-4 pt-3 pb-4">
      <VoiceInput onTranscript={(text, lang) => handleQuery(text, false, lang)} onError={setErrorMsg} appState={appState} currentLang={selectedLang} />
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
        <button
          onClick={toggleSpeak}
          className={`p-1.5 rounded-lg transition-colors hover:bg-white/[0.06] ${speakEnabled ? 'text-white/80' : 'text-white/30 hover:text-white/60'}`}
          title={speakEnabled ? "Turn off spoken replies" : "Turn on spoken replies"}
          aria-pressed={speakEnabled}
        >
          {speakEnabled
            ? <Volume2 className="w-3.5 h-3.5" strokeWidth={1.75} />
            : <VolumeX className="w-3.5 h-3.5" strokeWidth={1.75} />}
        </button>
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
        
        {/* LEFT COLUMN: Main Weather or Comparison (Hidden in 'chat' mode) */}
        {uiMode !== 'chat' && (
          <div className="flex-1 flex flex-col gap-5 min-w-0">
            {appState === 'processing' && !weatherData && <SkeletonCard />}

            {/* Activity Pills Above Comparison Cards */}
            <ActivityChips onSelect={(text) => handleQuery(text, false)} />

            {uiMode === 'comparison' && comparisonData ? (
              <ComparisonCard data={comparisonData} />
            ) : (
              weatherData && (
                <>
                  <WeatherCard weatherData={weatherData} currentLang={selectedLang} />
                  <HourlyTimeline hours={forecastHourly} currentLang={selectedLang} />
                  <ForecastList days={forecastDays} currentLang={selectedLang} />
                </>
              )
            )}

            {appState === 'idle' && !weatherData && (
              <div className="flex flex-col items-center justify-center min-h-[16rem]
                border border-dashed border-white/[0.08] rounded-[28px]
                bg-white/[0.02] p-8">
                <p className="text-white/35 font-medium mb-4 text-sm">Waiting for location...</p>
              </div>
            )}
          </div>
        )}

        {/* RIGHT COLUMN: Live conversation */}
        <div className={`${uiMode === 'chat' ? 'w-full max-w-2xl mx-auto' : 'w-full lg:w-96 shrink-0'} flex flex-col gap-5 transition-all duration-300 lg:sticky lg:top-2 lg:h-[calc(100vh-8rem)]`}>
          {conversationPanel}
        </div>
      </div>

      <ErrorToast message={errorMsg} onDismiss={() => setErrorMsg("")} />
    </AppShell>
  );
}
