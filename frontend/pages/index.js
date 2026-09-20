import React, { useState, useRef, useEffect } from 'react';
import AppShell from '@/components/AppShell';
import TopBar from '@/components/TopBar';
import VoiceInput from '@/components/VoiceInput';
import WeatherCard from '@/components/WeatherCard';
import SkeletonCard from '@/components/SkeletonCard';
import HourlyTimeline from '@/components/HourlyTimeline';
import ForecastList from '@/components/ForecastList';
import AlertBanner from '@/components/AlertBanner';
import ResponseBubble from '@/components/ResponseBubble';
import ChatHistory from '@/components/ChatHistory';
import AudioPlayer from '@/components/AudioPlayer';
import ErrorToast from '@/components/ErrorToast';
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

  const handleQuery = async (text, isSilentLocationUpdate = false) => {
    if (!text.trim()) return;
    
    setAppState('processing');
    setErrorMsg("");
    // If it's just a manual location change, we might not clear the old response until the new one arrives
    if (!isSilentLocationUpdate) {
      setLatestResponse("");
      setLatestAudio("");
    }
    
    try {
      const response = await queryAgent(text, selectedLang, messages);
      
      setMessages(response.messages || []);
      
      // If the backend detected a language and we were in 'en', we COULD update it, 
      // but since the user explicitly wants manual selection to drive this, 
      // we won't overwrite their manual dropdown choice if they set one.
      
      if (!isSilentLocationUpdate) {
        setLatestResponse(response.response_text || "");
        setLatestAudio(response.audio_b64 || "");
      }
      
      if (response.weather_data && Object.keys(response.weather_data).length > 0) {
        setWeatherData(response.weather_data);
      }
      
      if (response.forecast_data) {
        setForecastDays(response.forecast_data.days || []);
        setForecastHourly(response.forecast_data.hourly || []);
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
      <div className="flex flex-col lg:flex-row gap-6 lg:gap-8 flex-1 pb-64">
        
        {/* LEFT COLUMN: Main Weather */}
        <div className="flex-1 flex flex-col gap-6">
          {appState === 'processing' && !weatherData && <SkeletonCard />}
          
          {weatherData && (
            <>
              {/* Giant Weather Card on Desktop */}
              <div className="lg:transform lg:scale-105 lg:origin-top-left transition-transform duration-500">
                <WeatherCard weatherData={weatherData} />
              </div>
              <HourlyTimeline hours={forecastHourly} />
            </>
          )}
          
          {appState === 'idle' && !weatherData && (
            <div className="flex items-center justify-center h-64 border-2 border-dashed border-white/10 rounded-3xl glass-panel">
              <p className="text-white/40 font-medium">Ask Weather Buddy for a forecast...</p>
            </div>
          )}
        </div>

        {/* RIGHT COLUMN: Sidebar (Forecast & Details) */}
        <div className="w-full lg:w-80 flex flex-col gap-6">
          {weatherData && <ForecastList days={forecastDays} />}
        </div>
      </div>

      {/* FIXED BOTTOM DOCK (Chat + Voice) */}
      <div className="fixed bottom-0 left-0 w-full bg-gradient-to-t from-[#0f172a] via-[#0f172a]/95 to-transparent pt-12 pb-6 px-4 z-40 pointer-events-none">
        <div className="max-w-4xl mx-auto w-full flex flex-col items-center pointer-events-auto relative">
          
          {/* Chat log wrapper floating above mic */}
          {messages.length > 0 && (
            <div className="w-full max-w-2xl bg-black/40 backdrop-blur-md border border-white/5 rounded-3xl p-4 mb-4 shadow-2xl max-h-[40vh] flex flex-col">
              <div className="overflow-y-auto hide-scrollbar flex-1">
                <ChatHistory messages={messages} />
                <div ref={endOfChatRef} className="h-2" />
              </div>
            </div>
          )}
          
          <div className="flex flex-col items-center w-full max-w-2xl relative z-50">
            <AudioPlayer audioBase64={latestAudio} autoPlay={true} />
            <VoiceInput onTranscript={(text) => handleQuery(text, false)} appState={appState} />
          </div>
        </div>
      </div>

      <ErrorToast message={errorMsg} onDismiss={() => setErrorMsg("")} />
    </AppShell>
  );
}
