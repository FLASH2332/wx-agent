import React, { useState, useRef, useEffect } from 'react';
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

export default function Home() {
  const [appState, setAppState] = useState('idle');
  
  const [weatherData, setWeatherData] = useState(null);
  const [forecastDays, setForecastDays] = useState([]);
  const [forecastHourly, setForecastHourly] = useState([]);
  const [alerts, setAlerts] = useState([]); 
  
  const [messages, setMessages] = useState([]);
  const [latestResponse, setLatestResponse] = useState("");
  const [latestAudio, setLatestAudio] = useState("");
  
  // Explicit language state (overrides auto-detection for subsequent turns)
  const [selectedLang, setSelectedLang] = useState("en");
  
  const [errorMsg, setErrorMsg] = useState("");
  const endOfChatRef = useRef(null);

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
      setLatestAudio("");
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

  return (
    <AppShell appState={appState}>
      <AlertBanner alerts={alerts} />
      
      <TopBar 
        currentLang={selectedLang} 
        onLangChange={setSelectedLang} 
        onLocationSearch={handleManualLocation} 
      />

      {/* DASHBOARD - MULTI-COLUMN LAYOUT */}
      <div className="flex flex-col lg:flex-row gap-6 lg:gap-8 flex-1 pb-56">
        
        {/* LEFT COLUMN: Main Weather */}
        <div className="flex-1 flex flex-col gap-5">
          {appState === 'processing' && !weatherData && <SkeletonCard />}
          
          {weatherData && (
            <>
              <WeatherCard weatherData={weatherData} currentLang={selectedLang} />
              <HourlyTimeline hours={forecastHourly} currentLang={selectedLang} />
            </>
          )}
          
          {appState === 'idle' && !weatherData && (
            <div className="flex flex-col items-center justify-center h-64 
              border border-dashed border-white/[0.08] rounded-[28px] 
              bg-white/[0.02] p-6">
              <p className="text-white/35 font-medium mb-4 text-sm">Ask Weather Buddy for a forecast…</p>
              <SuggestionChips onSelect={(text) => handleQuery(text, false)} />
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: Sidebar */}
        <div className="w-full lg:w-80 flex flex-col gap-5">
          {weatherData && <ForecastList days={forecastDays} currentLang={selectedLang} />}
        </div>
      </div>

      {/* FIXED BOTTOM DOCK */}
      <div className="fixed bottom-0 left-0 w-full 
        bg-gradient-to-t from-slate-950 via-slate-950/95 to-transparent 
        pt-10 pb-6 px-4 z-40 pointer-events-none">
        <div className="max-w-4xl mx-auto w-full flex flex-col items-center pointer-events-auto relative">
          
          {/* Chat log — outer 24px */}
          {(messages.length > 0 || appState === 'processing') && (
            <div className="w-full max-w-2xl bg-slate-900/90 backdrop-blur-xl 
              border border-slate-700/50 rounded-[24px] p-4 mb-4 
              shadow-[0_4px_16px_rgba(0,0,0,0.3),0_12px_40px_rgba(0,0,0,0.2)]
              max-h-48 flex flex-col">
              <div className="overflow-y-auto hide-scrollbar flex-1 pr-2">
                <ChatHistory messages={messages} currentLang={selectedLang} />
                {appState === 'processing' && (
                  <div className="flex justify-start my-2">
                    <div className="bg-white/[0.06] text-white/60 px-4 py-2.5 
                      rounded-[16px] rounded-tl-[4px] border border-white/[0.06] 
                      text-sm animate-pulse flex items-center gap-2">
                      <div className="w-1.5 h-1.5 bg-blue-400/80 rounded-full animate-ping" />
                      <span>Weather Buddy is thinking…</span>
                    </div>
                  </div>
                )}
                <div ref={endOfChatRef} className="h-2" />
              </div>
            </div>
          )}
          
          <div className="flex flex-col items-center w-full max-w-2xl relative z-50">
            <AudioPlayer audioBase64={latestAudio} autoPlay={true} />
            <VoiceInput onTranscript={(text, lang) => handleQuery(text, false, lang)} appState={appState} currentLang={selectedLang} />
          </div>
        </div>
      </div>

      <ErrorToast message={errorMsg} onDismiss={() => setErrorMsg("")} />
    </AppShell>
  );
}
